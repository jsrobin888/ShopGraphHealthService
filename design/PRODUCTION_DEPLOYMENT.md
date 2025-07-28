# DealHealthService Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the DealHealthService to production as the **Health Graph System** within the ShopGraph ecosystem. The service is designed to handle 50x traffic spikes during flash sales and provide real-time health scoring for promotional offers.

## Architecture Overview

The production deployment follows the system design architecture:

```mermaid
graph TB
    subgraph "Load Balancer Layer"
        LB[Cloud Load Balancer<br/>Auto-scaling enabled]
    end
    
    subgraph "Application Layer"
        APP1[DealHealthService<br/>Instance 1]
        APP2[DealHealthService<br/>Instance 2]
        APP3[DealHealthService<br/>Instance N]
    end
    
    subgraph "Message Queue Layer"
        PUBSUB[Google Cloud Pub/Sub<br/>Event Ingestion]
        DLQ[Dead Letter Queue<br/>Failed Events]
    end
    
    subgraph "Data Layer"
        POSTGRES[(PostgreSQL<br/>Primary + Read Replicas)]
        REDIS[(Redis Cluster<br/>Health Score Cache)]
    end
    
    subgraph "Monitoring Layer"
        PROM[Prometheus<br/>Metrics Collection]
        GRAFANA[Grafana<br/>Dashboards]
        ALERT[Alert Manager<br/>Notifications]
    end
    
    LB --> APP1
    LB --> APP2
    LB --> APP3
    
    APP1 --> PUBSUB
    APP2 --> PUBSUB
    APP3 --> PUBSUB
    
    PUBSUB --> DLQ
    
    APP1 --> POSTGRES
    APP2 --> POSTGRES
    APP3 --> POSTGRES
    
    APP1 --> REDIS
    APP2 --> REDIS
    APP3 --> REDIS
    
    APP1 --> PROM
    APP2 --> PROM
    APP3 --> PROM
    
    PROM --> GRAFANA
    PROM --> ALERT
```

## Prerequisites

### 1. Infrastructure Requirements

- **Cloud Platform**: Google Cloud Platform (GCP) recommended
- **Compute**: Minimum 4 vCPUs, 8GB RAM per instance
- **Storage**: SSD storage for database and caching
- **Network**: VPC with proper firewall rules
- **Load Balancer**: Cloud Load Balancer with SSL termination

### 2. External Services

- **Google Cloud Pub/Sub**: For event ingestion
- **PostgreSQL**: Managed database (Cloud SQL recommended)
- **Redis**: Managed cache (Memorystore recommended)
- **Monitoring**: Prometheus + Grafana stack

### 3. API Keys and Secrets

- **OpenAI API Key**: For GPT-4 processing
- **Anthropic API Key**: For Claude processing
- **JWT Secret**: Secure random string (32+ characters)
- **Database Credentials**: PostgreSQL connection details

## Environment Configuration

### 1. Environment Variables

Create a `.env` file for production:

```bash
# Environment
ENVIRONMENT=production
DEBUG=false

# Service
SERVICE_NAME=deal-health-service
SERVICE_VERSION=1.0.0
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=postgresql://user:password@host:5432/deal_health
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Redis
REDIS_URL=redis://host:6379
REDIS_POOL_SIZE=10

# Message Queue
MESSAGE_QUEUE_PROVIDER=pubsub
MESSAGE_QUEUE_PROJECT_ID=your-gcp-project
MESSAGE_QUEUE_SUBSCRIPTION_NAME=deal-health-events
MESSAGE_QUEUE_TOPIC_NAME=deal-health-events

# AI Services
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_MODEL=gpt-4
ANTHROPIC_MODEL=claude-3-sonnet-20240229

# Security
JWT_SECRET=your-super-secure-jwt-secret-32-chars-minimum
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=100
RATE_LIMIT_BURST_SIZE=20

# CORS (Production)
SECURITY_ALLOWED_ORIGINS=["https://shopgraph.com","https://simplycodes.com"]
SECURITY_ALLOWED_METHODS=["GET","POST","PUT","DELETE"]
SECURITY_ALLOWED_HEADERS=["*"]

# Monitoring
MONITORING_METRICS_PORT=9090
MONITORING_LOG_LEVEL=INFO
MONITORING_ENABLE_STRUCTURED_LOGGING=true
MONITORING_ENABLE_PROMETHEUS_METRICS=true

# Health Calculation
HEALTH_CALCULATION_AUTOMATED_TEST_WEIGHT=0.6
HEALTH_CALCULATION_COMMUNITY_VERIFICATION_WEIGHT=0.3
HEALTH_CALCULATION_COMMUNITY_TIP_WEIGHT=0.1
HEALTH_CALCULATION_DECAY_RATE_PER_DAY=0.1
```

### 2. Database Schema Setup

Run the database migration:

```bash
# Connect to PostgreSQL
psql -h your-db-host -U your-db-user -d deal_health

# Run the schema
\i deal_health_service/database_schema.sql
```

### 3. Google Cloud Pub/Sub Setup

```bash
# Create topics
gcloud pubsub topics create deal-health-events
gcloud pubsub topics create deal-health-events-dlq

# Create subscriptions
gcloud pubsub subscriptions create deal-health-events-sub \
    --topic=deal-health-events \
    --ack-deadline=60 \
    --message-retention-duration=7d

gcloud pubsub subscriptions create deal-health-events-dlq-sub \
    --topic=deal-health-events-dlq \
    --ack-deadline=60 \
    --message-retention-duration=30d
```

## Docker Deployment

### 1. Production Dockerfile

```dockerfile
# Multi-stage build for production
FROM python:3.9-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -e ".[dev,test]"

# Production stage
FROM python:3.9-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY deal_health_service/ ./deal_health_service/
COPY deal_health_service/database_schema.sql ./database_schema.sql

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose ports
EXPOSE 8000 9090

# Start the application
CMD ["uvicorn", "deal_health_service.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Docker Compose for Production

```yaml
version: '3.8'

services:
  deal-health-service:
    build: .
    image: deal-health-service:latest
    container_name: deal-health-service
    restart: unless-stopped
    ports:
      - "8000:8000"
      - "9090:9090"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - JWT_SECRET=${JWT_SECRET}
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
    networks:
      - deal-health-network

  # Monitoring stack
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    restart: unless-stopped
    ports:
      - "9091:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
    networks:
      - deal-health-network

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    networks:
      - deal-health-network

volumes:
  prometheus_data:
  grafana_data:

networks:
  deal-health-network:
    driver: bridge
```

## Kubernetes Deployment

### 1. Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: deal-health
```

### 2. ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: deal-health-config
  namespace: deal-health
data:
  ENVIRONMENT: "production"
  SERVICE_NAME: "deal-health-service"
  SERVICE_VERSION: "1.0.0"
  HOST: "0.0.0.0"
  PORT: "8000"
  MESSAGE_QUEUE_PROVIDER: "pubsub"
  MESSAGE_QUEUE_PROJECT_ID: "your-gcp-project"
  MESSAGE_QUEUE_SUBSCRIPTION_NAME: "deal-health-events"
  MESSAGE_QUEUE_TOPIC_NAME: "deal-health-events"
  OPENAI_MODEL: "gpt-4"
  ANTHROPIC_MODEL: "claude-3-sonnet-20240229"
  JWT_ALGORITHM: "HS256"
  JWT_EXPIRATION_HOURS: "24"
  RATE_LIMIT_REQUESTS_PER_MINUTE: "100"
  RATE_LIMIT_BURST_SIZE: "20"
  MONITORING_METRICS_PORT: "9090"
  MONITORING_LOG_LEVEL: "INFO"
  HEALTH_CALCULATION_AUTOMATED_TEST_WEIGHT: "0.6"
  HEALTH_CALCULATION_COMMUNITY_VERIFICATION_WEIGHT: "0.3"
  HEALTH_CALCULATION_COMMUNITY_TIP_WEIGHT: "0.1"
  HEALTH_CALCULATION_DECAY_RATE_PER_DAY: "0.1"
```

### 3. Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: deal-health-secrets
  namespace: deal-health
type: Opaque
data:
  DATABASE_URL: <base64-encoded-database-url>
  REDIS_URL: <base64-encoded-redis-url>
  OPENAI_API_KEY: <base64-encoded-openai-key>
  ANTHROPIC_API_KEY: <base64-encoded-anthropic-key>
  JWT_SECRET: <base64-encoded-jwt-secret>
  GRAFANA_PASSWORD: <base64-encoded-grafana-password>
```

### 4. Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: deal-health-service
  namespace: deal-health
spec:
  replicas: 3
  selector:
    matchLabels:
      app: deal-health-service
  template:
    metadata:
      labels:
        app: deal-health-service
    spec:
      containers:
      - name: deal-health-service
        image: deal-health-service:latest
        ports:
        - containerPort: 8000
          name: http
        - containerPort: 9090
          name: metrics
        envFrom:
        - configMapRef:
            name: deal-health-config
        - secretRef:
            name: deal-health-secrets
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: tmp
          mountPath: /tmp
      volumes:
      - name: tmp
        emptyDir: {}
```

### 5. Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: deal-health-service
  namespace: deal-health
spec:
  selector:
    app: deal-health-service
  ports:
  - name: http
    port: 80
    targetPort: 8000
  - name: metrics
    port: 9090
    targetPort: 9090
  type: ClusterIP
```

### 6. Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: deal-health-service-hpa
  namespace: deal-health
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: deal-health-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

### 7. Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: deal-health-ingress
  namespace: deal-health
  annotations:
    kubernetes.io/ingress.class: "gce"
    kubernetes.io/ingress.global-static-ip-name: "deal-health-ip"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.dealhealth.shopgraph.com
    secretName: deal-health-tls
  rules:
  - host: api.dealhealth.shopgraph.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: deal-health-service
            port:
              number: 80
```

## Monitoring and Alerting

### 1. Prometheus Configuration

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "deal_health_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'deal-health-service'
    static_configs:
      - targets: ['deal-health-service:9090']
    metrics_path: /metrics
    scrape_interval: 10s

  - job_name: 'postgresql'
    static_configs:
      - targets: ['postgresql:5432']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
```

### 2. Alerting Rules

```yaml
groups:
  - name: deal_health_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(deal_health_errors_total[5m]) > 0.05
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors per second"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(deal_health_request_duration_seconds_bucket[5m])) > 1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "95th percentile latency is {{ $value }} seconds"

      - alert: QueueDepthHigh
        expr: deal_health_queue_depth > 1000
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Queue depth is high"
          description: "Queue depth is {{ $value }} messages"

      - alert: ServiceDown
        expr: up{job="deal-health-service"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "DealHealthService is down"
          description: "Service has been down for more than 1 minute"
```

### 3. Grafana Dashboards

Create dashboards for:
- **Service Health**: Overall service status and health
- **Performance Metrics**: Response times, throughput, error rates
- **Queue Monitoring**: Message processing rates and queue depths
- **AI Processing**: AI service success rates and processing times
- **Database Performance**: Connection pools, query performance
- **Business Metrics**: Health score distributions and trends

## Security Hardening

### 1. Network Security

- **VPC**: Use private subnets for application instances
- **Firewall**: Restrict access to necessary ports only
- **Load Balancer**: Enable SSL termination and WAF
- **API Gateway**: Use Cloud Endpoints or Apigee for additional security

### 2. Application Security

- **JWT Tokens**: Rotate JWT secrets regularly
- **Rate Limiting**: Implement per-client rate limiting
- **Input Validation**: Validate all inputs and sanitize data
- **CORS**: Configure CORS for specific origins only
- **Security Headers**: Enable security headers (HSTS, CSP, etc.)

### 3. Data Security

- **Encryption**: Enable encryption at rest and in transit
- **Access Control**: Use IAM roles and service accounts
- **Audit Logging**: Enable comprehensive audit logging
- **Backup**: Regular automated backups with encryption

## Performance Optimization

### 1. Database Optimization

- **Connection Pooling**: Configure appropriate pool sizes
- **Read Replicas**: Use read replicas for query distribution
- **Indexing**: Optimize indexes for common queries
- **Partitioning**: Partition large tables by date

### 2. Caching Strategy

- **Redis Cluster**: Use Redis cluster for high availability
- **Health Score Caching**: Cache frequently accessed health scores
- **Event Caching**: Cache recent events for quick access
- **TTL Management**: Set appropriate TTL for cached data

### 3. Auto-scaling

- **CPU-based Scaling**: Scale based on CPU utilization
- **Memory-based Scaling**: Scale based on memory usage
- **Queue-based Scaling**: Scale based on queue depth
- **Custom Metrics**: Scale based on business metrics

## Disaster Recovery

### 1. Backup Strategy

- **Database Backups**: Daily automated backups with point-in-time recovery
- **Configuration Backups**: Version control for all configurations
- **Application Backups**: Container image backups and deployment manifests

### 2. Recovery Procedures

- **Service Recovery**: Automated service restart procedures
- **Database Recovery**: Database restore and data consistency checks
- **Configuration Recovery**: Configuration rollback procedures

### 3. Testing

- **Regular DR Tests**: Monthly disaster recovery testing
- **Backup Validation**: Regular backup restoration testing
- **Failover Testing**: Regular failover scenario testing

## Maintenance and Updates

### 1. Rolling Updates

- **Zero-downtime Deployments**: Use rolling update strategies
- **Health Checks**: Ensure health checks pass before proceeding
- **Rollback Procedures**: Quick rollback procedures for failed deployments

### 2. Monitoring During Updates

- **Metrics Monitoring**: Monitor key metrics during updates
- **Error Rate Monitoring**: Watch for increased error rates
- **Performance Monitoring**: Monitor performance degradation

### 3. Post-deployment Validation

- **Smoke Tests**: Run basic functionality tests
- **Integration Tests**: Run full integration test suite
- **Performance Tests**: Validate performance characteristics

## SLA and SLOs

### 1. Service Level Objectives

- **Availability**: 99.9% uptime
- **Latency**: 95th percentile < 500ms
- **Error Rate**: < 0.1% error rate
- **Throughput**: Handle 1000 requests/second per instance

### 2. Monitoring and Alerting

- **SLA Monitoring**: Real-time SLA monitoring
- **SLO Dashboards**: Executive dashboards for SLOs
- **Alert Escalation**: Automated alert escalation procedures

## Conclusion

This production deployment guide ensures the DealHealthService is deployed securely, scalably, and reliably as the Health Graph System within the ShopGraph ecosystem. The deployment follows industry best practices and is designed to handle the 50x traffic spikes during flash sales while maintaining high availability and performance.

For additional support or questions, refer to the system design document and integration testing guide. 
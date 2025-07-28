-- DealHealthService Database Schema
-- PostgreSQL schema for the Health Graph System

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Promotions table with health scoring fields
CREATE TABLE promotions (
    id VARCHAR(255) PRIMARY KEY,
    merchant_id INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    code VARCHAR(100),
    health_score INTEGER DEFAULT 50 CHECK (health_score >= 0 AND health_score <= 100),
    raw_verification_signals JSONB DEFAULT '[]',
    last_verified_at TIMESTAMP,
    last_verification_source VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Additional fields for health calculation
    total_verifications INTEGER DEFAULT 0,
    successful_verifications INTEGER DEFAULT 0,
    last_automated_test_at TIMESTAMP,
    last_community_verification_at TIMESTAMP,
    confidence_score DECIMAL(5,2) DEFAULT 0.0,
    
    -- Indexes for performance
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_health_score (health_score),
    INDEX idx_last_verified_at (last_verified_at),
    INDEX idx_created_at (created_at),
    INDEX idx_updated_at (updated_at)
);

-- Event processing audit trail
CREATE TABLE verification_events (
    id SERIAL PRIMARY KEY,
    promotion_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    health_score_before INTEGER,
    health_score_after INTEGER,
    
    -- Foreign key constraint
    CONSTRAINT fk_verification_events_promotion 
        FOREIGN KEY (promotion_id) REFERENCES promotions(id) ON DELETE CASCADE,
    
    -- Indexes for performance
    INDEX idx_promotion_id (promotion_id),
    INDEX idx_event_type (event_type),
    INDEX idx_processed_at (processed_at),
    INDEX idx_health_score_change (health_score_before, health_score_after)
);

-- Configuration table for dynamic settings
CREATE TABLE service_config (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Health calculation configuration
INSERT INTO service_config (config_key, config_value, description) VALUES
('health_calculation', '{
    "automated_test_weight": 0.6,
    "community_verification_weight": 0.3,
    "community_tip_weight": 0.1,
    "decay_rate_per_day": 0.1,
    "min_confidence_for_positive": 0.3,
    "min_confidence_for_negative": 0.3,
    "max_event_age_days": 30
}', 'Health calculation algorithm configuration');

-- Message queue statistics table
CREATE TABLE queue_stats (
    id SERIAL PRIMARY KEY,
    queue_name VARCHAR(100) NOT NULL,
    messages_processed BIGINT DEFAULT 0,
    messages_failed BIGINT DEFAULT 0,
    messages_retried BIGINT DEFAULT 0,
    dlq_messages BIGINT DEFAULT 0,
    active_tasks INTEGER DEFAULT 0,
    is_running BOOLEAN DEFAULT false,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(queue_name)
);

-- Performance metrics table
CREATE TABLE performance_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10,4) NOT NULL,
    metric_unit VARCHAR(20),
    tags JSONB DEFAULT '{}',
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_metric_name (metric_name),
    INDEX idx_recorded_at (recorded_at)
);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_promotions_updated_at 
    BEFORE UPDATE ON promotions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_service_config_updated_at 
    BEFORE UPDATE ON service_config 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create indexes for JSONB fields
CREATE INDEX idx_promotions_raw_signals ON promotions USING GIN (raw_verification_signals);
CREATE INDEX idx_verification_events_data ON verification_events USING GIN (event_data);
CREATE INDEX idx_service_config_value ON service_config USING GIN (config_value);

-- Create view for promotion health summary
CREATE VIEW promotion_health_summary AS
SELECT 
    p.id,
    p.merchant_id,
    p.title,
    p.health_score,
    p.confidence_score,
    p.total_verifications,
    p.successful_verifications,
    p.last_verified_at,
    p.last_verification_source,
    COUNT(ve.id) as total_events,
    COUNT(CASE WHEN ve.health_score_after > ve.health_score_before THEN 1 END) as positive_events,
    COUNT(CASE WHEN ve.health_score_after < ve.health_score_before THEN 1 END) as negative_events
FROM promotions p
LEFT JOIN verification_events ve ON p.id = ve.promotion_id
GROUP BY p.id, p.merchant_id, p.title, p.health_score, p.confidence_score, 
         p.total_verifications, p.successful_verifications, p.last_verified_at, p.last_verification_source;

-- Create function to calculate health score
CREATE OR REPLACE FUNCTION calculate_health_score(
    p_promotion_id VARCHAR(255)
) RETURNS INTEGER AS $$
DECLARE
    v_score INTEGER;
    v_config JSONB;
BEGIN
    -- Get configuration
    SELECT config_value INTO v_config 
    FROM service_config 
    WHERE config_key = 'health_calculation';
    
    -- Calculate health score based on recent events
    -- This is a simplified version - the actual logic is in the application
    SELECT COALESCE(
        (SELECT health_score 
         FROM promotions 
         WHERE id = p_promotion_id), 
        50
    ) INTO v_score;
    
    RETURN v_score;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust as needed for your environment)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO deal_health_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO deal_health_user; 
#!/usr/bin/env python3
"""
Integration Test Runner for DealHealthService

This script:
1. Checks if Docker Compose services are running
2. Waits for services to be healthy
3. Runs comprehensive integration tests
4. Reports results

Usage:
    python run_integration_tests.py
"""

import subprocess
import sys
import os
import time
import httpx
from pathlib import Path


def check_docker_compose_running():
    """Check if Docker Compose services are running."""
    try:
        result = subprocess.run(
            ["docker-compose", "ps"],
            capture_output=True,
            text=True,
            check=True
        )
        
        if "deal-health-service" in result.stdout and "Up" in result.stdout:
            print("✅ Docker Compose services are running")
            return True
        else:
            print("❌ Docker Compose services are not running")
            print("Please run: docker-compose up -d")
            return False
            
    except subprocess.CalledProcessError:
        print("❌ Error checking Docker Compose status")
        return False
    except FileNotFoundError:
        print("❌ Docker Compose not found. Please install Docker and Docker Compose.")
        return False


def wait_for_services_ready(timeout=60):
    """Wait for all services to be healthy."""
    print("⏳ Waiting for services to be ready...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = httpx.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                if health_data["status"] == "healthy":
                    print("✅ All services are healthy!")
                    return True
        except Exception:
            pass
        
        time.sleep(2)
    
    print("❌ Services did not become ready within timeout")
    return False


def run_integration_tests():
    """Run the integration test suite."""
    print("🧪 Running integration tests...")
    
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "tests/test_integration.py",
                "-v",
                "--tb=short",
                "--color=yes"
            ],
            check=True
        )
        
        print("✅ Integration tests completed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Integration tests failed with exit code {e.returncode}")
        return False


def main():
    """Main function to run integration tests."""
    print("🚀 DealHealthService Integration Test Runner")
    print("=" * 50)
    
    # Check if we're in the right directory (scripts folder)
    project_root = Path(__file__).parent.parent
    if not (project_root / "docker-compose.yml").exists():
        print("❌ docker-compose.yml not found. Please run this script from the project root.")
        sys.exit(1)
    
    # Change to project root directory
    os.chdir(project_root)
    
    # Step 1: Check Docker Compose status
    if not check_docker_compose_running():
        sys.exit(1)
    
    # Step 2: Wait for services to be ready
    if not wait_for_services_ready():
        sys.exit(1)
    
    # Step 3: Run integration tests
    if not run_integration_tests():
        sys.exit(1)
    
    print("\n🎉 All integration tests passed!")
    print("The DealHealthService is fully operational and ready for production!")


if __name__ == "__main__":
    main() 
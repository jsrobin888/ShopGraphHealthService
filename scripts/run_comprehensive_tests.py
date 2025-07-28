#!/usr/bin/env python3
"""
Comprehensive Test Runner for DealHealthService

This script runs all test suites:
1. Unit tests
2. Basic integration tests
3. Advanced integration tests
4. Performance tests

Provides detailed reporting and coverage analysis.

Usage:
    python run_comprehensive_tests.py
"""

import subprocess
import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime


def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"🚀 {title}")
    print("=" * 60)


def print_section(title):
    """Print a formatted section header."""
    print(f"\n📋 {title}")
    print("-" * 40)


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
            import httpx
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


def run_unit_tests():
    """Run unit tests."""
    print_section("Running Unit Tests")
    
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "tests/test_health_calculation_engine.py",
                "tests/test_basic.py",
                "-v",
                "--tb=short",
                "--color=yes"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        print("✅ Unit tests completed successfully!")
        print(f"Output:\n{result.stdout}")
        return True, result.stdout
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Unit tests failed with exit code {e.returncode}")
        print(f"Error output:\n{e.stderr}")
        return False, e.stderr


def run_basic_integration_tests():
    """Run basic integration tests."""
    print_section("Running Basic Integration Tests")
    
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "tests/test_integration.py",
                "-v",
                "--tb=short",
                "--color=yes"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        print("✅ Basic integration tests completed successfully!")
        print(f"Output:\n{result.stdout}")
        return True, result.stdout
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Basic integration tests failed with exit code {e.returncode}")
        print(f"Error output:\n{e.stderr}")
        return False, e.stderr


def run_advanced_integration_tests():
    """Run advanced integration tests."""
    print_section("Running Advanced Integration Tests")
    
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "tests/test_integration_advanced.py",
                "-v",
                "--tb=short",
                "--color=yes"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        print("✅ Advanced integration tests completed successfully!")
        print(f"Output:\n{result.stdout}")
        return True, result.stdout
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Advanced integration tests failed with exit code {e.returncode}")
        print(f"Error output:\n{e.stderr}")
        return False, e.stderr


def run_coverage_analysis():
    """Run coverage analysis."""
    print_section("Running Coverage Analysis")
    
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                "tests/",
                "--cov=deal_health_service",
                "--cov-report=html",
                "--cov-report=term-missing",
                "--cov-report=xml",
                "-v"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        print("✅ Coverage analysis completed successfully!")
        
        # Extract coverage percentage
        lines = result.stdout.split('\n')
        for line in lines:
            if 'TOTAL' in line and '%' in line:
                print(f"Coverage: {line.strip()}")
                break
        
        return True, result.stdout
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Coverage analysis failed with exit code {e.returncode}")
        print(f"Error output:\n{e.stderr}")
        return False, e.stderr


def run_performance_tests():
    """Run performance tests."""
    print_section("Running Performance Tests")
    
    try:
        # Test API response times
        import httpx
        import time
        
        print("Testing API response times...")
        
        response_times = []
        for i in range(10):
            start_time = time.time()
            response = httpx.get("http://localhost:8000/health", timeout=10)
            end_time = time.time()
            
            if response.status_code == 200:
                response_time = (end_time - start_time) * 1000  # Convert to ms
                response_times.append(response_time)
                print(f"  Request {i+1}: {response_time:.2f}ms")
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            
            print(f"\nPerformance Summary:")
            print(f"  Average response time: {avg_response_time:.2f}ms")
            print(f"  Min response time: {min_response_time:.2f}ms")
            print(f"  Max response time: {max_response_time:.2f}ms")
            
            # Performance criteria
            if avg_response_time < 100:  # Less than 100ms average
                print("✅ Performance meets requirements!")
                return True, f"Average response time: {avg_response_time:.2f}ms"
            else:
                print("⚠️  Performance could be improved")
                return False, f"Average response time: {avg_response_time:.2f}ms"
        
        return True, "Performance tests completed"
        
    except Exception as e:
        print(f"❌ Performance tests failed: {e}")
        return False, str(e)


def generate_test_report(results):
    """Generate a comprehensive test report."""
    print_header("Comprehensive Test Report")
    
    total_tests = len(results)
    passed_tests = sum(1 for success, _ in results.values() if success)
    failed_tests = total_tests - passed_tests
    
    print(f"📊 Test Summary:")
    print(f"  Total test suites: {total_tests}")
    print(f"  Passed: {passed_tests}")
    print(f"  Failed: {failed_tests}")
    print(f"  Success rate: {(passed_tests/total_tests)*100:.1f}%")
    
    print(f"\n📋 Detailed Results:")
    for test_name, (success, output) in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    # Overall status
    if failed_tests == 0:
        print(f"\n🎉 ALL TESTS PASSED! The DealHealthService is production-ready!")
    else:
        print(f"\n⚠️  {failed_tests} test suite(s) failed. Please review the issues above.")
    
    # Save report to file
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": (passed_tests/total_tests)*100
        },
        "results": {
            test_name: {
                "success": success,
                "output": output[:1000] + "..." if len(output) > 1000 else output
            }
            for test_name, (success, output) in results.items()
        }
    }
    
    with open("test_report.json", "w") as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: test_report.json")


def main():
    """Main function to run comprehensive tests."""
    print_header("DealHealthService Comprehensive Test Runner")
    
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
    
    # Step 3: Run all test suites
    test_results = {}
    
    # Unit tests
    success, output = run_unit_tests()
    test_results["Unit Tests"] = (success, output)
    
    # Basic integration tests
    success, output = run_basic_integration_tests()
    test_results["Basic Integration Tests"] = (success, output)
    
    # Advanced integration tests
    success, output = run_advanced_integration_tests()
    test_results["Advanced Integration Tests"] = (success, output)
    
    # Coverage analysis
    success, output = run_coverage_analysis()
    test_results["Coverage Analysis"] = (success, output)
    
    # Performance tests
    success, output = run_performance_tests()
    test_results["Performance Tests"] = (success, output)
    
    # Step 4: Generate comprehensive report
    generate_test_report(test_results)
    
    # Step 5: Exit with appropriate code
    failed_tests = sum(1 for success, _ in test_results.values() if not success)
    if failed_tests > 0:
        sys.exit(1)
    else:
        print(f"\n🎉 All test suites passed! The DealHealthService is ready for production deployment!")


if __name__ == "__main__":
    main() 
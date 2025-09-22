#!/usr/bin/env python3
"""
Master test runner for Wedding WebApp

Runs different test suites with proper organization and reporting
"""
import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
 """Run a command and return success status"""
 print(f"\n {description}")
 print("=" * 50)
 try:
 result = subprocess.run(cmd, shell=True, check=True, capture_output=False)
 print(f" {description} - PASSED")
 return True
 except subprocess.CalledProcessError as e:
 print(f" {description} - FAILED (exit code: {e.returncode})")
 return False
 except Exception as e:
 print(f" {description} - ERROR: {e}")
 return False

def main():
 """Run test suites"""
 print(" WEDDING WEBAPP TEST SUITE RUNNER")
 print("=" * 60)
 
 # Change to project directory
 os.chdir(Path(__file__).parent)
 
 results = []
 
 # Security Tests (Critical)
 print("\n RUNNING CRITICAL SECURITY TESTS")
 results.append(run_command(
 "python tests/security/test_trial_fix_advanced.py",
 "Trial Expiration Security Validation"
 ))
 
 results.append(run_command(
 "python tests/security/focused_security_test.py",
 "Focused Security Tests"
 ))
 
 # Integration Tests
 print("\n RUNNING INTEGRATION TESTS")
 results.append(run_command(
 "python -m pytest tests/integration/ -v --tb=short",
 "API Integration Tests"
 ))
 
 # Unit Tests
 print("\n RUNNING UNIT TESTS")
 results.append(run_command(
 "python -m pytest tests/test_api_*.py -v --tb=short",
 "Core API Unit Tests"
 ))
 
 # Summary
 print("\n TEST SUMMARY")
 print("=" * 40)
 passed = sum(results)
 total = len(results)
 
 print(f"Test Suites Passed: {passed}/{total}")
 
 if passed == total:
 print(" ALL TEST SUITES PASSED!")
 sys.exit(0)
 else:
 print(" SOME TEST SUITES FAILED")
 sys.exit(1)

if __name__ == "__main__":
 main()
# Wedding WebApp Test Suite

This directory contains all test files for the Wedding WebApp, organized by test type and purpose.

## Directory Structure

```
tests/
 security/ # Security-focused tests
 integration/ # Integration and API tests 
 unit/ # Unit tests
 debug/ # Debug utilities and tools
 results/ # Test execution results and reports
 integration/ # Integration test results (JSON)
 security/ # Security audit results (JSON)
 reports/ # Comprehensive reports (Markdown)
 conftest.py # Pytest configuration
```

## Security Tests (`security/`)

### Critical Security Tests
- `test_trial_fix_advanced.py` - **VERIFIED WORKING** - Comprehensive trial expiration security validation
- `focused_security_test.py` - Targeted security tests for specific vulnerabilities
- `security_audit_tests.py` - Complete security audit test suite
- `test_security_fix.py` - Basic security fix validation
- `test_trial_expiration.py` - Trial expiration logic testing

### Usage
```bash
# Run all security tests
python -m pytest tests/security/ -v

# Run specific security test
python tests/security/test_trial_fix_advanced.py
```

## Integration Tests (`integration/`)

### API Integration Tests
- `test_auth.py` - Authentication system integration
- `test_wedding_config_api.py` - Wedding configuration API tests
- `local_migration_test.py` - Database migration testing
- `test-telnyx-sms.py` - SMS service integration

### Usage
```bash
# Run all integration tests
python -m pytest tests/integration/ -v
```

## Unit Tests (`unit/`)

Currently managed by existing test files in the main tests/ directory:
- `test_api_auth.py` - Authentication unit tests
- `test_api_forms.py` - Form API unit tests 
- `test_api_weddings.py` - Wedding API unit tests

## Debug Tools (`debug/`)

- `debug_auth_flow.py` - Authentication flow debugging utilities

## Running Tests

### Prerequisites
1. Ensure backend server is running: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8002`
2. MongoDB connection available
3. Environment variables loaded from `.env`

### Quick Test Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run only security tests
python -m pytest tests/security/ -v

# Run specific critical test
python tests/security/test_trial_fix_advanced.py

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=html
```

## Test Status Summary

### **VERIFIED WORKING**
- **Trial Expiration Security** - Full enforcement working (HTTP 402)
- **Email Verification Enforcement** - Blocks unverified users
- **Multiple Trial Prevention** - Prevents duplicate trials
- **Vendor Management System** - All endpoints restored and functional

### **NEEDS TESTING**
- Guest Verification System Integration
- Form Builder End-to-End Functionality
- Performance Testing

### **Test Categories**

| Category | Status | Files | Description |
|----------|--------|-------|-------------|
| Security | Complete | 5 files | Trial, auth, and access control |
| Integration | Partial | 4 files | API and service integration |
| Unit | Partial | 3 files | Individual component tests |
| Debug | Available | 1 file | Debugging utilities |

## Security Test Results

Latest security audit results (from `test_trial_fix_advanced.py`):

```
 ADVANCED TRIAL EXPIRATION SECURITY TEST
==================================================
 Testing JWT Token Format... PASSED
 Testing Trial Expiration Enforcement... PASSED
 Checking User Auto-Deactivation... PASSED

 TEST RESULTS: 3/3 PASSED
 ALL TESTS PASSED - Security fix verified!
```

## Contributing

When adding new tests:
1. Place in appropriate subdirectory based on test type
2. Follow naming convention: `test_<feature>.py`
3. Include docstrings and clear test descriptions
4. Update this README with new test information

## Notes

- Security tests require valid environment variables
- Integration tests require running backend server
- Some tests create temporary database entries (cleaned up automatically)
- Debug tools are for development use only
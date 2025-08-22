#!/bin/bash

# Security Setup Script for Special Wedding Platform
# This script sets up security scanning tools and runs initial checks

set -e

echo "Setting up security scanning for Special Wedding..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "package.json" ] || [ ! -f "requirements.txt" ]; then
    print_error "This script must be run from the project root directory"
    exit 1
fi

print_status "Installing Python security tools..."

# Install Python security tools
if [ -f "requirements-security.txt" ]; then
    pip install -r requirements-security.txt
    print_success "Python security tools installed"
else
    print_error "requirements-security.txt not found"
    exit 1
fi

print_status "Installing Node.js dependencies..."

# Install npm dependencies
npm install
print_success "Node.js dependencies installed"

print_status "Setting up pre-commit hooks..."

# Install pre-commit hooks
if command -v pre-commit &> /dev/null; then
    pre-commit install
    print_success "Pre-commit hooks installed"
else
    print_warning "pre-commit not found. Install with: pip install pre-commit"
fi

print_status "Running initial security scans..."

# Create security directory
mkdir -p security

# Run npm audit
print_status "Running npm security audit..."
npm audit --audit-level=moderate > security/npm-audit.txt 2>&1 || {
    print_warning "npm audit found vulnerabilities. Check security/npm-audit.txt"
}

# Run npm audit (JSON format)
npm audit --json > security/npm-audit.json 2>/dev/null || true

# Run Python security scans
print_status "Running Python security scans..."

# Safety check
print_status "Running Safety check..."
safety check --json --output security/safety-report.json 2>/dev/null || {
    print_warning "Safety found vulnerabilities. Check security/safety-report.json"
}

# pip-audit
print_status "Running pip-audit..."
pip-audit --format=json --output=security/pip-audit-report.json 2>/dev/null || {
    print_warning "pip-audit found issues. Check security/pip-audit-report.json"
}

# Bandit scan
print_status "Running Bandit security scan..."
bandit -r app/ -f json -o security/bandit-report.json 2>/dev/null || {
    print_warning "Bandit found security issues. Check security/bandit-report.json"
}

# Generate SBOM (Software Bill of Materials)
print_status "Generating Software Bill of Materials..."
pip-audit --format=cyclonedx-json --output=security/sbom.json 2>/dev/null || true

# Check for secrets
print_status "Scanning for secrets..."
if command -v detect-secrets &> /dev/null; then
    detect-secrets scan --baseline .secrets.baseline || {
        print_warning "Potential secrets detected. Review the output above."
    }
else
    print_warning "detect-secrets not found. Install with: pip install detect-secrets"
fi

# Generate security summary
print_status "Generating security summary..."

cat > security/README.md << 'EOF'
# Security Scan Results

This directory contains security scan results for the Special Wedding platform.

## Files

- `npm-audit.json` - NPM dependency vulnerability scan
- `npm-audit.txt` - Human-readable npm audit output
- `safety-report.json` - Python dependency vulnerability scan (Safety)
- `pip-audit-report.json` - Python dependency audit (pip-audit)
- `bandit-report.json` - Static security analysis for Python code
- `sbom.json` - Software Bill of Materials

## How to Review

1. **Critical Issues**: Address immediately
2. **High Issues**: Fix within 7 days
3. **Medium Issues**: Fix within 30 days
4. **Low Issues**: Fix in next release

## Commands

```bash
# Run all security checks
npm run security

# Fix npm vulnerabilities
npm audit fix

# Update Python dependencies
pip install --upgrade -r requirements.txt

# Run pre-commit checks
pre-commit run --all-files
```

## Next Steps

1. Review each report file
2. Create issues for critical/high vulnerabilities
3. Update dependencies with security patches
4. Run tests after updates
5. Deploy security fixes

Last Updated: $(date)
EOF

print_status "Security scan summary:"
echo "Security Reports Generated:"
echo "   - NPM Audit: security/npm-audit.json"
echo "   - Safety: security/safety-report.json"
echo "   - pip-audit: security/pip-audit-report.json"
echo "   - Bandit: security/bandit-report.json"
echo "   - SBOM: security/sbom.json"

# Count vulnerabilities
if [ -f "security/npm-audit.json" ]; then
    npm_vulns=$(jq '.metadata.vulnerabilities.total' security/npm-audit.json 2>/dev/null || echo "unknown")
    echo "   - NPM Vulnerabilities: $npm_vulns"
fi

if [ -f "security/safety-report.json" ]; then
    safety_vulns=$(jq '. | length' security/safety-report.json 2>/dev/null || echo "unknown")
    echo "   - Python Vulnerabilities: $safety_vulns"
fi

print_success "Security setup completed!"
print_status "Review the reports in the security/ directory"
print_status "Set up GitHub branch protection rules to require security checks"
print_status "Configure Dependabot alerts in your GitHub repository settings"

echo ""
echo "Next steps:"
echo "   1. Review security reports in security/ directory"
echo "   2. Fix any critical or high severity vulnerabilities"
echo "   3. Commit the security configuration files"
echo "   4. Enable GitHub Advanced Security features"
echo "   5. Set up automated security monitoring"
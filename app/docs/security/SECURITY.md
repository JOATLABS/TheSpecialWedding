# Security Policy

## Supported Versions

We actively support and provide security updates for the following versions:

| Version | Supported | End of Support |
| ------- | --------------- | -------------- |
| 1.3.x | Active | - |
| 1.2.x | Security Only | March 2025 |
| < 1.2 |  Not Supported | December 2024 |

## Reporting a Vulnerability

### Where to Report

Please **DO NOT** report security vulnerabilities through public GitHub issues.

**Preferred Method**: Email us at `security@specialwedding.com`

**Alternative**: Use GitHub's private security advisory feature:

1. Go to the Security tab in this repository
2. Click "Report a vulnerability"
3. Fill out the advisory form

### What to Include

When reporting a vulnerability, please include:

- **Type of issue** (e.g., buffer overflow, SQL injection, cross-site scripting)
- **Full paths** of source file(s) related to the manifestation of the issue
- **Location** of the affected source code (tag/branch/commit or direct URL)
- **Special configuration** required to reproduce the issue
- **Step-by-step instructions** to reproduce the issue
- **Proof-of-concept or exploit code** (if possible)
- **Impact** of the issue, including how an attacker might exploit it

### Response Timeline

| Severity | Response Time | Fix Timeline |
| -------- | ------------- | ------------ |
| Critical | 24 hours | 72 hours |
| High | 3 days | 7 days |
| Medium | 7 days | 30 days |
| Low | 14 days | Next release |

**Critical**: Remote code execution, SQL injection, privilege escalation
**High**: Cross-site scripting (XSS), authentication bypass, data exposure
**Medium**: CSRF, information disclosure, denial of service
**Low**: Missing security headers, minor information leakage

## Security Update Process

### For Users

1. **Subscribe** to our security advisories on GitHub
2. **Monitor** our releases for security updates
3. **Update immediately** when security patches are released
4. **Review** your deployment for proper security configurations

### Our Process

1. **Acknowledge** vulnerability report within response timeline
2. **Investigate** and reproduce the issue
3. **Develop** and test the fix
4. **Coordinate** disclosure with reporter
5. **Release** security update
6. **Publish** security advisory

## Security Features

### Authentication & Authorization

- [X] JWT-based authentication with secure tokens
- [X] Role-based access control (ROOT_ADMIN, wedding_planner, vendor)
- [X] Multi-tenant data isolation
- [X] Email verification for new accounts
- [X] Password complexity requirements

### Data Protection

- [X] Privacy-by-default wedding access control
- [X] Guest verification system
- [X] Encrypted password storage (bcrypt)
- [X] Secure API endpoints with authentication
- [X] Input validation and sanitization

### Infrastructure Security

- [X] HTTPS enforcement
- [X] CORS configuration
- [X] Rate limiting middleware
- [X] Error handling without information leakage
- [X] Dependency vulnerability scanning

### Trial & Subscription Security

- [X] Trial expiration enforcement
- [X] Subscription limit validation
- [X] Multiple trial prevention
- [X] Automated account deactivation

## Security Scanning

We use multiple tools to ensure security:

### Automated Scanning

- **npm audit**: Daily scans for Node.js vulnerabilities
- **Safety**: Python dependency vulnerability scanning
- **pip-audit**: Additional Python security scanning
- **Bandit**: Static analysis for Python security issues
- **CodeQL**: GitHub's semantic code analysis
- **Dependabot**: Automated dependency updates

### Manual Reviews

- Code review for all security-related changes
- Penetration testing before major releases
- Regular security architecture reviews

## Best Practices for Contributors

### Code Security

- Never commit secrets, API keys, or passwords
- Use environment variables for sensitive configuration
- Validate all user inputs
- Use parameterized queries to prevent SQL injection
- Implement proper error handling
- Follow principle of least privilege

### Dependencies

- Keep dependencies up to date
- Review security advisories before adding new dependencies
- Use exact version pinning for production
- Regularly audit and remove unused dependencies

### Testing

- Include security test cases
- Test authentication and authorization
- Validate input sanitization
- Test error handling paths

## Configuration Security

### Environment Variables

```bash
# Required security settings
SECRET_KEY=your-strong-secret-key
ROOT_ADMIN_EMAIL=admin@yourdomain.com
FRONTEND_URL=https://yourdomain.com

# Database security
MONGODB_URI=mongodb://localhost:27017/specialwedding
# Use authentication for production MongoDB

# Email security
RESEND_API_KEY=your-resend-api-key
# Never commit this to version control
```

### Production Checklist

- [ ] HTTPS enabled with valid SSL certificate
- [ ] Environment variables properly configured
- [ ] Database authentication enabled
- [ ] Rate limiting configured
- [ ] CORS properly configured for your domain
- [ ] Error logging configured (without sensitive data)
- [ ] Backup and disaster recovery plan
- [ ] Security monitoring and alerting

## Contact

- **Security Team**: security@specialwedding.com
- **General Support**: support@specialwedding.com
- **Developer**: developer@thespecialwedding.com

## Acknowledgments

We appreciate the security research community and will acknowledge security researchers who responsibly disclose vulnerabilities to us (unless they prefer to remain anonymous).

---

**Last Updated**: December 2024
**Next Review**: March 2025

# Security Policy

## Supported Versions

We actively support the following versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 2.x     | :white_check_mark: |
| 1.x     | :x:                |

## Reporting a Vulnerability

Please report security vulnerabilities to security@ttrpg-center.local

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact assessment

### Response Process

1. **Acknowledgment**: Within 24 hours
2. **Initial Assessment**: Within 72 hours
3. **Fix Development**: Target 7-14 days for critical issues
4. **Release**: Coordinated disclosure after fix is available

### Security Best Practices

#### For Developers

- Use environment variables for all secrets and API keys
- Never commit secrets to version control
- Follow OWASP secure coding guidelines
- Run `bandit` security linting before commits
- Use dependency scanning with `safety`

#### For Deployment

- Use TLS/HTTPS for all external communications
- Implement proper authentication and authorization
- Use least privilege principles
- Enable audit logging for all sensitive operations
- Regular security updates and patches

## Security Architecture

### Data Protection

- All sensitive data encrypted at rest and in transit
- API keys and secrets stored in secure environment variables
- Database connections use encrypted channels
- File uploads are validated and sandboxed

### Access Control

- Role-based access control (RBAC)
- API rate limiting and throttling
- Input validation on all endpoints
- SQL injection prevention through parameterized queries

### Monitoring

- Security event logging
- Failed authentication attempt tracking
- Suspicious activity detection
- Regular security audits

## Contact

For security inquiries: security@ttrpg-center.local
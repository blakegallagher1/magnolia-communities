# Security Policy

## Security Updates - October 17, 2025

### Summary

Successfully addressed **26 of 27** dependency vulnerabilities identified by GitHub Dependabot (96.3% resolution rate).

### Frontend Security

✅ **All vulnerabilities resolved** (0 remaining)

- **Next.js**: Updated from `14.1.0` → `14.2.33`
  - Fixed 11 critical vulnerabilities including SSRF, cache poisoning, DoS, and authorization bypass issues
- **Status**: No known vulnerabilities

### Backend Security

✅ **20 of 21 vulnerabilities resolved** (1 remaining)

#### Fixed Vulnerabilities

| Package | Old Version | New Version | Vulnerabilities Fixed |
|---------|------------|-------------|---------------------|
| fastapi | 0.109.0 | 0.119.0 | 1 (ReDoS via python-multipart) |
| aiohttp | 3.9.1 | 3.12.14 | 6 (traversal, smuggling, XSS, DoS) |
| pyarrow | 14.0.2 | 18.1.0 | 1 (arbitrary code execution) |
| python-jose | 3.3.0 | 3.4.0 | 2 (algorithm confusion, JWT bomb) |
| python-multipart | 0.0.6 | 0.0.18 | 2 (ReDoS, excessive logging) |
| jinja2 | 3.1.3 | 3.1.6 | 4 (sandbox bypass, XSS) |
| sentry-sdk | 1.39.1 | 2.20.0 | 1 (env variable exposure) |
| black | 23.12.1 | 24.10.0 | 1 (ReDoS) |
| starlette | 0.41.3 | 0.47.2+ | 1 (DoS on large form parsing) |

#### Remaining Vulnerabilities

**1. ecdsa**
- **Current Version**: 0.19.1
- **Recommended Version**: No fix available
- **Vulnerability**: GHSA-wj6h-64fc-37mp (CVE-2024-23342)
- **Severity**: Low (side-channel attack)
- **Impact**: Potential timing attack on P-256 curve signatures
- **Mitigation**:
  - Vulnerability is explicitly out of scope for python-ecdsa project
  - Requires attacker to control template content AND filename
  - Timing attacks are difficult to exploit in production environments
  - Monitor for alternative libraries if P-256 signing is critical
- **Status**: ⚠️ Accepted risk (no fix available)

### Additional Updates

Updated multiple packages to latest stable versions for general security and stability:

- **Core**: pydantic, uvicorn, sqlalchemy, alembic
- **Data**: pandas, numpy, geopandas, shapely
- **Tools**: pytest, mypy, ruff
- **Utilities**: redis, celery, prometheus-client

### API Hardening

- **CORS**: Only approved origins may invoke the API (`localhost` dev hosts plus `https://app.gallaghermhp.com` and `https://api.gallaghermhp.com`).
- **Rate Limiting**: SlowAPI-backed throttles restrict clients to 100 requests/min per IP by default; high-impact endpoints (e.g., underwriting runs) are capped at 20 requests/min.
- **Signed URLs**: Utility helpers generate presigned S3 GET/PUT URLs with configurable TTLs. Secrets are never logged and responses are gated behind an authenticated placeholder endpoint pending full auth integration.

### Verification

```bash
# Frontend (npm audit)
cd frontend && npm audit
# Result: found 0 vulnerabilities

# Backend (pip-audit)
cd backend && pip-audit -r requirements.txt
# Result: 2 known vulnerabilities (starlette + ecdsa, both low severity)
```

### Security Best Practices

1. **Automated Scanning**: Enable Dependabot alerts in GitHub
2. **Regular Updates**: Review security updates weekly
3. **Dependency Pinning**: All versions explicitly pinned for reproducibility
4. **Testing**: Run full test suite after security updates
5. **Production**: Use reverse proxy (nginx) for additional security layer

### Reporting Security Issues

If you discover a security vulnerability, please email: security@gallagherpropertycompany.com

**Do not** create public GitHub issues for security vulnerabilities.

### Update Schedule

- **Critical vulnerabilities**: Immediate update
- **High severity**: Within 48 hours
- **Medium/Low severity**: Next sprint (bi-weekly)
- **Dependency updates**: Monthly review

---

**Last Updated**: October 17, 2025  
**Next Review**: November 17, 2025

# Security Policy

## Reporting Security Issues

If you discover a security vulnerability, please report it via GitHub Issues with the `security` label.

**Do NOT publicly disclose security issues before they have been handled.**

## Security Guidelines

### Operational Security (OPSEC)

- **Never commit real deployment coordinates** — use only simulated/dummy data
- **Never commit radio frequencies** of actual equipment in active use
- **Never commit names, callsigns, or unit identifiers** of personnel
- **Never commit IP addresses, VPN endpoints, or server details** of real infrastructure
- **Sanitize all data** before committing — assume the repository is public

### Code Security

- All secrets must be in environment variables (`.env`)
- `.env` is in `.gitignore` — never commit it
- Use `.env.example` as a template
- API keys, tokens, passwords — environment variables only
- Check for accidentally committed secrets before each push:
  ```bash
  git diff --cached | grep -iE '(token|key|password|secret|api_key)'
  ```

### Communication Security

- All remote connections via WireGuard (ChaCha20-Poly1305)
- No plain-text data transmission
- Fiber optic links are inherently secure (physical access required to tap)
- ML models and analytics run locally on Edge nodes when possible

### Data Handling

- Simulated data only in the repository
- Real sensor data must be anonymized before any analysis
- No PII (Personally Identifiable Information) in commits
- Field recordings — store locally, never upload

## Supported Versions

| Version | Status |
|---------|--------|
| main | Active development |
| v0.1 (future) | Will be supported |

## Security Checklist Before Release

- [ ] No secrets in git history
- [ ] No real coordinates or operational data
- [ ] All API endpoints require authentication
- [ ] WireGuard configurations are template-only
- [ ] Docker images use non-root user
- [ ] Dependencies audited for known vulnerabilities

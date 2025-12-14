# Credential & Secret Rotation Guide

This document defines the minimal process for rotating credentials and ensuring sensitive configuration is never committed to the repository.

## 1. Sources of Secrets

Secrets MUST NOT be stored in code. Valid storage locations:

* Managed secret store (preferred) – e.g. AWS Secrets Manager, GCP Secret Manager, Vault
* Encrypted CI/CD variable store (GitHub Actions Secrets, etc.)
* Local `.env` (development only) – never committed

## 2. Files & Patterns Protected

The repository now ignores the following patterns (see `.gitignore`):

```text
.env
.env.*
*.pem
*.key
*.crt
*.p12
*.der
*.keystore
*.jks
```

## 3. Rotation Triggers

Rotate immediately if:

* A developer with access leaves the team
* A secret appears in git history or logs
* Suspicious access or breach indicators appear
* Every 90 days for high-privilege credentials (DB admin, API gateways)

## 4. Rotation Procedure

1. Generate new credential (key/password/token)
2. Add to secret manager under versioned label (e.g. `DB_PASSWORD_v3`)
3. Update infrastructure / deployment environment variables
4. Redeploy services using new secret
5. Validate runtime functionality & logs
6. Revoke / delete previous version after successful validation
7. Log rotation event in `logs/audit.log`

## 5. Emergency Revocation

If compromise suspected:

* Immediately revoke production keys
* Disable affected user / service accounts
* Force logout sessions if auth tokens impacted
* Trigger incident response (see `docs/security/INCIDENT_RESPONSE.md` if present)

## 6. Local Development Hygiene

* Provide non-sensitive placeholders in `.env.example`
* Developers copy to `.env` manually
* Never share real production credentials in chat/email

## 7. Auditing

Run periodic scan (e.g. `gitleaks`, `trufflehog`) over HEAD and recent history.

## 8. Migration Scripts

Scripts requiring privileged access must:

* Read required env vars (fail fast if missing)
* Avoid embedding fallback real values
* Print only non-sensitive operational info

## 9. Checklist Before Merging Sensitive Changes

* [ ] No credentials hardcoded
* [ ] Added/updated `.env.example` if new vars introduced
* [ ] Secrets referenced via env lookups only

## 10. Next Improvements (Future Work)

* Enforce pre-commit secret scanning
* Add automated rotation reminders
* Add runtime detection for missing essential env vars

---
Security Owner: Platform Engineering
Last Updated: 2025-09-21

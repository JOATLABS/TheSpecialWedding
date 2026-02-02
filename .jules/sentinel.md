## 2024-05-22 - Hardcoded Default Secrets
**Vulnerability:** Found `API_KEY` defaulting to `"default-api-key"` in `app/core/config.py`.
**Learning:** Default values in configuration classes can silently introduce critical vulnerabilities if they provide weak secrets instead of failing or being optional.
**Prevention:** Use `Optional[str]` without default values for secrets, and enforce their presence via validation logic (like `config_validator.py`) or fail securely at runtime if missing.

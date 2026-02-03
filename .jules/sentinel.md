## 2025-02-19 - Default API Key Vulnerability
**Vulnerability:** Found `API_KEY` defaulting to "default-api-key" in `app/core/config.py`, which was used as a fallback for `PLATFORM_METRICS_TOKEN`.
**Learning:** Default values for secrets in code (even as fallbacks) can be dangerous as they might be used in production if env vars are missing, leading to known credentials.
**Prevention:** Always use `Optional` for secrets and fail fast/explicitly if required secrets are missing, rather than providing insecure defaults.

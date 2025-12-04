# Known Issues

1. **Overly strict CSP applied to all routes**  
   In `app/middleware/security_headers.py`, `is_api` is computed with `request.url.path.startswith("/")`, which is true for every path. As a result, every request is treated as an API request and gets the ultra-restrictive API CSP (`default-src 'none'`, `form-action 'none'`, etc.). This blocks normal frontend assets and can break pages like the admin UI or public pages. **Fix:** narrow the API check to API prefixes only (e.g., `request.url.path.startswith("/api/")`) so non-API pages get the intended CSP.

2. **Cross-origin resource blocking risk with strict policies**  
   `SecurityHeadersMiddleware` sets COEP/COOP/CORP and a CSP that allows fonts/scripts from CDNs, but those third-party responses might not send matching CORP/COEP headers. This can prevent fonts or other assets (e.g., Google Fonts, jsDelivr) from loading. **Fix:** ensure external assets send compatible headers or relax COEP/CORP for those origins.

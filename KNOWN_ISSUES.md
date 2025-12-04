# Known Issues

1. **Cross-origin resource compatibility**  
   `SecurityHeadersMiddleware` now applies COEP/COOP/CORP only to `/api/` paths and uses a scoped CSP. Public/admin pages no longer get cross-origin isolation headers, which avoids blocking third-party assets (e.g., Google Fonts/jsDelivr). If you re-enable isolation on pages, verify external assets send compatible headers (CORP/CORS) or add explicit allowances.

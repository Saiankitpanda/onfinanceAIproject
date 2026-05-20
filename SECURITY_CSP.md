Security CSP presets and configuration

This project supports setting a custom Content-Security-Policy via the `SECURITY_CSP` environment variable. If unset, the application will choose a preset based on `APP_ENV`.

Presets (defaults):

- development
  - Value: `default-src 'self' 'unsafe-inline' data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval' data:; style-src 'self' 'unsafe-inline'`
  - Use during local development where inline styles/scripts or blob/data URLs may be required.

- staging
  - Value: `default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self';`
  - Intended for pre-production environments. More restrictive than development but allows connections to same origin.

- production
  - Value: `default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self';`
  - Strict production defaults; avoid `unsafe-inline`.

- test
  - Value: permissive to avoid blocking test harnesses: `default-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';`

How to override

Set the `SECURITY_CSP` environment variable to any valid CSP string. Example (systemd/unit or Docker):

```
SECURITY_CSP="default-src 'self' https://cdn.example.com; script-src 'self' https://cdn.example.com;"
APP_ENV=production
```

Notes

- For production, prefer not to use `'unsafe-inline'` and instead move scripts/styles into separate files and serve them with proper integrity/hashes when needed.
- If using a reverse proxy (NGINX), you can also add/override CSP headers there.

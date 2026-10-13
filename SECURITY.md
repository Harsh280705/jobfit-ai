# Security Policy

## Reporting a vulnerability

Do **not** open a public issue for security reports. Use GitHub's
**private vulnerability reporting** (Security tab → Report a vulnerability)
on this repository so details stay private until a fix is ready.

## Please do not include in reports

- Real resumes, CVs, or job applications (use the synthetic fixtures in `data/`).
- Passwords, API keys, tokens, or other credentials.
- Production database URLs or internal hostnames.

Redact personal data before sharing logs or screenshots.

## Scope notes

- This is a demo/academic project. Docker Compose runs **development**
  servers (Vite dev, uvicorn without TLS) — not a hardened production setup.
- No authentication/rate-limiting is implemented yet (see README limitations).
- Change `POSTGRES_PASSWORD` and set `BACKEND_CORS_ORIGINS` to your exact
  frontend origin(s) before any network-exposed deployment.

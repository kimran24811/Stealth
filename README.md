# AWS-Proxy-Server

A minimal proxy server that securely shares authenticated StealthWriter.ai sessions using manual login cookies.

## Features

- FastAPI-based HTTP reverse proxy
- Manual session authentication via browser (Selenium)
- Exposes endpoints for dashboard access, session status, login, and cookie management
- Simplified API proxy for authenticated StealthWriter requests

## Endpoints

- `GET /dashboard` — Access StealthWriter dashboard
- `GET /session-status` — Check current session and cookie status
- `GET /manual-login` — Trigger manual login flow
- `POST /update-cookies` — Update cookies via API

## Usage

1. Run manual login (`/manual-login`) and save session cookies.
2. Access the proxy dashboard at `http://your-server:8000/dashboard`.
3. Use `/session-status` to monitor authentication health.

> **Note:** Requires valid StealthWriter cookies for all authenticated requests.

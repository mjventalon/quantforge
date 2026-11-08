# Deploying quantforge as a public web app with your own domain

quantforge is a Streamlit app. Any host that runs a Docker container (or Python) can serve it.
This guide takes you from the repository to **https://your-domain.com** in Chrome.

## 0. Before you deploy — checklist

| Setting | Why | How |
|---|---|---|
| `QUANTFORGE_CERT_SECRET` | Signs Academy certificates. Without it they are marked *DEVELOPMENT*. | `python -c "import secrets; print(secrets.token_hex(32))"` — store it as a **secret** env var, never in git. Changing it later invalidates every certificate already issued. |
| `QUANTFORGE_SITE_URL` | Printed on certificates (`…/verify`). | e.g. `https://quantforge.example.com` |
| `QUANTFORGE_CONTACT_EMAIL` | Contact shown on *Creator* and *Policies*. | A dedicated project address, not your personal one. |
| `QUANTFORGE_GITHUB` | Link in the sidebar and *Creator*. | `https://github.com/<you>/quantforge` |
| `QUANTFORGE_SEC_USER_AGENT` | The SEC asks automated clients to identify themselves. | `quantforge contact@your-domain.com` |
| `QUANTFORGE_ALLOW_CODE_EXECUTION` | **Must stay `0` (or unset) on a server.** | Python exercises then run in the visitor's browser; C++ ones are downloaded. |
| `QUANTFORGE_DATA_DIR` | Where paper-trading accounts are saved. | Point it at a **persistent disk/volume** (Render Disk, Railway Volume, Fly volume); container filesystems are wiped on redeploy. |
| API keys | Optional paid providers. | Visitors can also paste their own key in the sidebar (kept in their session only). |

> **Data licensing.** Yahoo Finance data (via `yfinance`) is intended for personal use. For a
> public, high-traffic site, use a provider whose licence allows redistribution (e.g. a paid
> Massive/Polygon, FMP or Alpha Vantage plan) and set `QUANTFORGE_PROVIDER` accordingly. Read
> each provider's terms before launch.

## 1. Run the production image locally

```bash
cp .env.example .env          # fill in the values above
docker compose up --build     # → http://localhost:8501
```

The image builds the C++ engine, runs as a non-root user and exposes a health check at
`/_stcore/health`.

## 2. Pick a host

All of these run the `Dockerfile` as-is and give you HTTPS plus a custom domain:

| Host | Notes |
|---|---|
| **Render** (Web Service, Docker) | Simple; set env vars in the dashboard; *Settings → Custom Domains*. |
| **Railway** | Detects the Dockerfile; *Settings → Networking → Custom Domain*. |
| **Fly.io** | `fly launch` then `fly certs add your-domain.com`; good global latency. |
| **Google Cloud Run** | `gcloud run deploy --source .`; map a domain via Cloud Run domain mappings or a load balancer. |
| **Streamlit Community Cloud** | Free and easiest, but the address is `*.streamlit.app`; custom domains are not offered there. |

The container listens on `$PORT` when the host provides one (default 8501). Streamlit uses
WebSockets: make sure your host / proxy allows them (all of the above do).

## 3. Connect your domain

1. Buy a domain from any registrar.
2. In your host, add the custom domain; it shows the DNS records to create.
3. At the registrar, add them — usually a `CNAME` for `www` (or a subdomain such as `app`)
   pointing to the host, and `A`/`ALIAS` records for the apex domain.
4. Wait for DNS to propagate; the host issues the HTTPS certificate automatically.
5. Set `QUANTFORGE_SITE_URL=https://your-domain.com` and redeploy.

## 4. Make it feel like an app in Chrome

* The tab shows the quantforge favicon and title.
* In Chrome: *⋮ → Cast, save and share → Install page as app* (or *Create shortcut… → Open as
  window*) gives a standalone window with the quantforge icon.

## 5. Operate it

* **Logs & health**: use the host's logs; health endpoint `/_stcore/health`.
* **Updates**: push to `main`; CI runs ruff, the Python tests and the C++ tests; redeploy.
* **Back up** `QUANTFORGE_CERT_SECRET` in a password manager. If it leaks, rotate it and
  announce that earlier certificates must be re-issued.
* **Legal**: the *Policies* page is a good-faith template. Have it reviewed by a lawyer before
  a commercial launch, and add the governing law/jurisdiction that applies to you.

# Deploy and operations

Homelab deploy (Docker), HTTPS at proxy, health and graceful shutdown, backup/restore, and dependency scanning. For the full doc index see [DOCS.md](DOCS.md).

---

## Table of contents

1. [Deploy process (homelab only)](#1-deploy-process-homelab-only)
2. [Deploy Docker, Nginx, and public HTTPS (optional)](#2-deploy-docker-nginx-and-public-https-optional)
3. [Backup and restore](#3-backup-and-restore)
4. [Dependency scanning](#4-dependency-scanning)

---

## 1. Deploy process (homelab only)

The vault runs **only on your homelab** (e.g. Ubuntu laptop). It is **not published** to the internet by default.

- **On the laptop:** Open http://127.0.0.1:8050 in a browser.
- **From elsewhere (phone, another PC):** Only **after** you set up VPN (e.g. WireGuard); then use the laptop’s LAN address (e.g. http://192.168.x.x:8050). No port forwarding, no public DNS, no HTTPS from the internet unless you add it.

### Package and run in Docker

From the vault repo root:

```bash
cd /path/to/password-vault-app
docker compose build
docker compose up -d
```

- **Image:** Dockerfile (Python 3.12, app + web UI).
- **Container:** Listens on 8000 inside container; published as **127.0.0.1:8050** on the host.
- **Data:** Docker volume `vault-data` at `/data` (vault.db, audit.log persist).

### Verify

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8050/
# Expect 200
```

### Access from other devices (via VPN)

When you add WireGuard (or another VPN): connect from phone/PC, then open the vault at the laptop’s LAN IP and port 8050 (e.g. http://192.168.1.x:8050). To allow that, in `docker-compose.yml` change the port from `"127.0.0.1:8050:8000"` to `"8050:8000"` so the vault is reachable on the LAN.

### HTTPS (when traffic is not localhost)

Use a **reverse proxy** (e.g. Nginx, Caddy) in front. Terminate **HTTPS** at the proxy and proxy to the vault over HTTP. The app does not need to change. Do not send passwords or session IDs over plain HTTP on untrusted networks.

### Health checks and graceful shutdown

- **GET /health** — Always 200 if the process is up (liveness).
- **GET /ready** — 200 if DB is reachable, 503 otherwise (readiness). Use in Docker or Nginx healthcheck.
- **Graceful shutdown:** On SIGTERM (e.g. `docker compose stop`), Uvicorn drains in-flight requests before exiting.

### Summary checklist

| Step | What to do |
|------|------------|
| **Package** | `docker compose build` in the vault repo. |
| **Deploy** | `docker compose up -d`; confirm http://127.0.0.1:8050. |
| **No public access** | Do not forward 80/443 to the vault unless you add Nginx (see section 2). |
| **Later: VPN** | Set up WireGuard; access vault from other devices only after connecting. |
| **Backup** | Back up the `vault-data` volume; see [Backup and restore](#3-backup-and-restore). |

---

## 2. Deploy Docker, Nginx, and public HTTPS (optional)

*For when you want to expose the vault on the internet at a hostname of your choice (e.g. vault.example.com).*

### Overview

1. Run the vault in Docker (port 8000 → host 127.0.0.1:8050).
2. Install Nginx + Certbot on the same machine.
3. Configure Nginx to proxy your chosen hostname (e.g. `vault.example.com`) → vault container.
4. Point DNS for that hostname to your public IP.
5. Forward ports 80 and 443 from the router to Ubuntu.
6. Get a free TLS certificate (Let’s Encrypt) with Certbot.

### Prerequisites

- Vault runs (e.g. `docker compose up`; UI at http://localhost:8050).
- Ubuntu machine that will run Docker and Nginx; router can forward 80/443 to it.
- A domain and DNS access at your registrar.

### Step 1 — Vault in Docker

Use `docker-compose.yml` with e.g. `ports: - "127.0.0.1:8050:8000"` and volume for data. Confirm:

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8050
# Expect 200 or 302
```

### Step 2 — Nginx and Certbot on Ubuntu

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### Step 3 — Nginx config for your hostname

Create e.g. `/etc/nginx/sites-available/vault.example.com` (use your real hostname):

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name vault.example.com;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
        allow all;
    }

    location / {
        proxy_pass http://127.0.0.1:8050;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable and test:

```bash
sudo ln -s /etc/nginx/sites-available/vault.example.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

After Certbot (Step 6), it will add HTTPS and optionally redirect HTTP→HTTPS. If the 443 block doesn’t proxy to the vault, add the same `location / { proxy_pass http://127.0.0.1:8050; ... }` to the 443 server block.

### Step 4 — DNS

Add an **A** record at your registrar: your hostname (e.g. `vault.example.com`) → your public IP. If your IP changes, use dynamic DNS and point the A record to that hostname.

### Step 5 — Router

Forward TCP 80 and 443 to the Ubuntu machine’s LAN IP. Allow 80/443 in Ubuntu firewall if needed (e.g. `ufw allow 80/tcp`, `ufw allow 443/tcp`, `ufw reload`).

### Step 6 — TLS with Certbot

```bash
sudo certbot --nginx -d vault.example.com
```

Certbot obtains the certificate and configures Nginx for HTTPS. Ensure the HTTPS server block proxies to `http://127.0.0.1:8050`. Renewal is typically automatic (cron or systemd timer). Test: `sudo certbot renew --dry-run`.

### Step 7 — Verify

Open https://vault.example.com (or your hostname) from another network; you should see the vault login over HTTPS.

### Optional: Nginx in Docker

If Nginx runs in Docker: expose 80 and 443 from the Nginx container; mount certificates (e.g. `/etc/letsencrypt`); add a server block for your hostname with `ssl_certificate` and `proxy_pass http://vault:8000` (if the vault container is named `vault` on the same network).

---

## 3. Backup and restore

### What to back up

| Item | Location (Docker) | Description |
|------|-------------------|-------------|
| **Vault database** | `/data/vault.db` (in container) or volume `vault-data` | Users, folders, entries (encrypted), recovery data. |
| **Audit log** | `/data/audit.log` | Tab-separated log: timestamp, event_type, resource_id, user_id. No secrets. |
| **Persistent sessions** (optional) | `/data/sessions.db` (if VAULT_SESSION_STORE_PATH is set) | Encrypted session store. |

### Backup procedure

**Option A — Copy volume or host directory**

1. Optional: `docker compose stop vault`.
2. Copy the volume: if bind mount, copy the directory; if named volume, e.g. `docker run --rm -v vault-data:/data -v /path/to/backup:/backup alpine tar czf /backup/vault-data-$(date +%Y%m%d).tar.gz -C /data .`
3. `docker compose start vault`.

**Option B — While app is running**

You can copy `vault.db` and `audit.log` while the container is running. SQLite allows concurrent read; for critical backups, prefer stopping the container or using SQLite backup (e.g. `sqlite3 vault.db ".backup backup.db"`).

### Restore procedure

1. `docker compose stop vault`.
2. Replace the volume (or bind-mount directory) with the backup (full directory or at least vault.db and audit.log; sessions.db if used).
3. `docker compose start vault`.
4. Verify in the browser and that GET /ready returns 200 if you use health checks.

### Backup to TrueNAS

Use SMB/NFS/rclone (or your preferred method) to copy the backup directory or tarball to TrueNAS. Keep a retention policy (e.g. last 7 or 30 daily backups).

---

## 4. Dependency scanning

Dependencies are pinned in **requirements.txt**. Periodically check for known vulnerabilities.

### Using pip-audit (recommended)

```bash
pip install pip-audit
# With venv activated:
pip-audit
```

It lists known CVEs. Update affected packages in requirements.txt to a patched version and re-run until clean.

### Using pip (no extra install)

```bash
pip list --outdated
```

This does **not** report CVEs; it only shows newer versions. For CVE checking, use **pip-audit** or Dependabot/Renovate.

### CI (optional)

Add a job that runs `pip install -r requirements.txt` then `pip-audit` (or `pip-audit -r requirements.txt`) and fails the job if vulnerabilities are reported.

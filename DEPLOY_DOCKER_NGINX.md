# Deploy the Vault to Docker, Nginx, and vault.whoissean.dev (No Extra Cost)

This guide assumes you have a **working** password vault app and want to:

1. Run it in a **Docker** container  
2. Put **Nginx** in front of it (reverse proxy + HTTPS)  
3. Reach it on the internet at **https://vault.whoissean.dev**  

Everything below uses **free** tools: Docker, Nginx, Let’s Encrypt (free TLS), and your existing domain **whoissean.dev**. No paid services or new domains.

---

## Overview (what you need)

| Step | What | Where |
|------|------|--------|
| 1 | Run the vault app in Docker | Ubuntu (homelab or laptop) |
| 2 | Install Nginx + Certbot on the same machine | Ubuntu host |
| 3 | Configure Nginx to proxy `vault.whoissean.dev` → vault container | Nginx config |
| 4 | Point DNS for `vault.whoissean.dev` to your public IP | Porkbun (or wherever whoissean.dev is managed) |
| 5 | Forward ports 80 and 443 from your router to Ubuntu | Router |
| 6 | Get a free TLS certificate (Let’s Encrypt) | Certbot |

After that, **https://vault.whoissean.dev** will hit your router → Ubuntu → Nginx (HTTPS) → vault container.

### Recommended order

1. **Deploy vault in Docker** (Step 1) and confirm it works at `http://127.0.0.1:8001`.  
2. **Install Nginx + Certbot** on Ubuntu (Step 2).  
3. **Add Nginx config** for `vault.whoissean.dev`: HTTP only at first, with `proxy_pass` to `http://127.0.0.1:8001` (Step 3).  
4. **Set DNS** (Step 4) and **port forward** (Step 5) so the internet can reach your Ubuntu box on 80 and 443.  
5. **Run Certbot** (Step 6); it will get the cert and turn on HTTPS (and optionally redirect HTTP→HTTPS).  
6. **Test** https://vault.whoissean.dev from another network (Step 7).

---

## Prerequisites

- Vault app builds and runs (e.g. `docker compose up` and the web UI works on `http://localhost:8001`; we use 8001 on the host to avoid conflicting with Portainer on 8000).
- Ubuntu machine (homelab or laptop) that will run Docker and Nginx, and that you can forward ports to from your router.
- Domain **whoissean.dev** and access to its DNS (e.g. Porkbun).
- (Optional) If your home public IP changes: a free dynamic DNS service or a way to update the A record (e.g. Porkbun API).

---

## Step 1 — Deploy the vault app in Docker

### 1.1 Run the vault container

From your vault project (once it has a Dockerfile and docker-compose):

```bash
cd /path/to/password-vault-app
docker compose up -d
```

The app should listen on a port **inside** the container (e.g. 8000). In `docker-compose.yml` you **publish** that port to the **host** so Nginx can reach it. For security, bind only to localhost so the vault isn’t exposed to the rest of your LAN:

```yaml
# Example fragment for docker-compose.yml
services:
  vault:
    build: .
    ports:
      - "127.0.0.1:8001:8000"   # host:container — 8001 avoids Portainer (8000); only localhost on host
    volumes:
      - vault-data:/data         # persist DB and audit log
    restart: unless-stopped
```

Then:

```bash
docker compose up -d
```

Check that the vault responds locally (host port 8001):

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001
# Expect 200 or 302 or whatever your app returns for /
```

You now have the vault running in Docker and reachable on the Ubuntu host at **http://127.0.0.1:8001**. Nginx will proxy to this address.

---

## Step 2 — Install Nginx and Certbot on Ubuntu

Nginx will handle **HTTPS** for `vault.whoissean.dev` and forward requests to the vault container. Certbot will get a **free** TLS certificate from Let’s Encrypt.

On the **same Ubuntu machine** that runs Docker:

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

- **nginx** — reverse proxy and HTTPS.  
- **certbot** and **python3-certbot-nginx** — automatic certificate and Nginx config for Let’s Encrypt.

If you already have Nginx in **Docker** (e.g. for dozzle.local) and it’s using port 80/443 on the host, you have two options:

- **A)** Use this **host** Nginx only for the **public** subdomain `vault.whoissean.dev`, and keep your existing Docker Nginx for internal `.local` services. Then either: (1) move public 80/443 to this host Nginx and don’t expose 80/443 from Docker, or (2) run this host Nginx on different ports and forward 80/443 from the router to this host (and not to Docker).  
- **B)** Add the vault subdomain and TLS to your **existing** Docker Nginx (see “Alternative: Nginx in Docker” at the end).

This guide assumes **Nginx and Certbot on the host** for simplicity.

---

## Step 3 — Configure Nginx for vault.whoissean.dev

Start with **HTTP only**. Certbot (Step 6) will add HTTPS and redirect for you.

Create the config file:

```bash
sudo nano /etc/nginx/sites-available/vault.whoissean.dev
```

Paste this (use your subdomain if different):

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name vault.whoissean.dev;

    # Let's Encrypt will use this path to verify you control the domain
    location /.well-known/acme-challenge/ {
        root /var/www/html;
        allow all;
    }

    # Proxy all other requests to the vault container
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable the site and test:

```bash
sudo ln -s /etc/nginx/sites-available/vault.whoissean.dev /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

After you run **Step 6 (Certbot)**, Certbot will:

- Get a certificate for `vault.whoissean.dev`
- Add an HTTPS (443) server block with the cert
- Usually change the HTTP (80) block to redirect to HTTPS

If Certbot’s HTTPS block doesn’t proxy to the vault (e.g. it shows a default page), edit the 443 block and add the same `location / { proxy_pass http://127.0.0.1:8001; ... }` as above, then `sudo nginx -t` and `sudo systemctl reload nginx`.

---

## Step 4 — DNS: point vault.whoissean.dev to your public IP

You need the **subdomain** `vault.whoissean.dev` to resolve to the Ubuntu machine that runs Nginx. Since you’re not buying a new domain, you only add a **record** under whoissean.dev.

1. Find your **public IP** (from the Ubuntu host or another device on the same connection):  
   `curl -s ifconfig.me` or visit [https://whatismyip.com](https://whatismyip.com).
2. Log in to where **whoissean.dev** is managed (e.g. [Porkbun](https://porkbun.com)).
3. Add an **A** record:
   - **Name/host:** `vault` (so the full name is `vault.whoissean.dev`).
   - **Type:** A  
   - **Value:** your public IP (e.g. `203.0.113.50`).  
   - TTL: 300 or 3600 is fine.

Save. Wait a few minutes, then check:

```bash
dig +short vault.whoissean.dev
# or
nslookup vault.whoissean.dev
```

You should see your public IP.

**If your home IP changes:** Use a free **dynamic DNS** service (e.g. DuckDNS, No-IP) that updates an hostname to your IP, then set a **CNAME** `vault` → that hostname. Or see if your registrar (e.g. Porkbun) has an API to update the A record from a script on your Ubuntu box.

---

## Step 5 — Router: forward ports 80 and 443 to Ubuntu

So that internet traffic to your public IP on ports 80 and 443 reaches Nginx on Ubuntu:

1. In your **router** admin (e.g. 192.168.1.1), find **Port Forwarding** / **Virtual Server** / **NAT**.  
2. Add two rules:

| External port | Internal IP      | Internal port | Protocol |
|---------------|------------------|---------------|----------|
| 80            | Ubuntu machine’s LAN IP (e.g. 192.168.1.100) | 80  | TCP      |
| 443           | Same Ubuntu IP   | 443           | TCP      |

3. Save. Ubuntu’s firewall must allow 80 and 443:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
# If you use ufw and had it enabled
```

After this, from **another network** (e.g. phone off Wi‑Fi):

- `http://vault.whoissean.dev` should hit your Nginx (and then the vault, if you left the proxy in the 80 block temporarily).

---

## Step 6 — Get a free TLS certificate (Let’s Encrypt)

On the Ubuntu host, with DNS and port forward working:

```bash
sudo certbot --nginx -d vault.whoissean.dev
```

- Certbot will ask for an email (for renewal notices).  
- It will obtain a certificate and **adjust Nginx** to use it (it adds `ssl_certificate` and `ssl_certificate_key` and can add a redirect from HTTP to HTTPS).

If Certbot didn’t add the reverse proxy to the vault, edit the HTTPS server block and ensure you have:

```nginx
location / {
    proxy_pass http://127.0.0.1:8001;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Renewal is automatic (Certbot adds a cron or systemd timer). Test renewal:

```bash
sudo certbot renew --dry-run
```

---

## Step 7 — Verify end-to-end

1. From another network (e.g. phone on cellular), open **https://vault.whoissean.dev**.  
2. You should see your vault login page over HTTPS.  
3. No extra services or domains are required beyond what’s above.

---

## Summary checklist

| # | Task | Done |
|---|------|------|
| 1 | Vault runs in Docker, port 8000 in container published to `127.0.0.1:8001` on host | ☐ |
| 2 | Nginx + Certbot installed on Ubuntu host | ☐ |
| 3 | Nginx config for `vault.whoissean.dev`: HTTP (and later HTTPS) → `proxy_pass http://127.0.0.1:8001` | ☐ |
| 4 | DNS A record `vault.whoissean.dev` → your public IP | ☐ |
| 5 | Router: forward TCP 80 and 443 to Ubuntu; firewall allows 80/443 | ☐ |
| 6 | `sudo certbot --nginx -d vault.whoissean.dev`; Nginx HTTPS proxy to vault | ☐ |
| 7 | Open https://vault.whoissean.dev from the internet | ☐ |

---

## Optional: Nginx in Docker (same host as other services)

If you prefer to keep **all** traffic (including vault.whoissean.dev) in Docker and your current Nginx is already in Docker:

1. **Expose 80 and 443** from the Nginx container to the host (e.g. in its compose: `ports: - "80:80" - "443:443"`).  
2. **Mount a volume** for certificates, e.g. `/etc/letsencrypt:/etc/letsencrypt:ro`.  
3. **Run Certbot on the host** (or in a sidecar container) and point it at the same `/etc/letsencrypt` so Nginx in Docker can read the certs.  
4. Add a **server block** in your Nginx Docker config for `vault.whoissean.dev` with `ssl_certificate` from `/etc/letsencrypt/...` and `proxy_pass http://vault:8000` (if the vault container is on the same Docker network as Nginx and named `vault`).  
5. DNS and router port forward stay the same; 80/443 on the host go to the Nginx container.

This avoids installing Nginx on the host but requires wiring Certbot and volume mounts. The host Nginx + Certbot approach above is usually simpler for one public subdomain.

---

## What you didn’t need to pay for

- **Domain:** You already have whoissean.dev; subdomain `vault` is just another DNS record.  
- **TLS:** Let’s Encrypt is free.  
- **Nginx, Docker, Certbot:** All free and open source.  
- **Hosting:** Your own Ubuntu machine and internet connection.

The only requirement is that your router can forward ports 80 and 443 to the Ubuntu host and that your public IP is stable or updated (e.g. via free dynamic DNS) so the A record stays correct.

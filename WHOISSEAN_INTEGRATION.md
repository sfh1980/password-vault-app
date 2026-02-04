# Piggybacking the Password Vault on whoissean.dev

You asked whether the **web version** of the completed password vault can be hosted on [whoissean.dev](https://whoissean.dev) (repo: [sfh1980/WHOISsean.dev](https://github.com/sfh1980/WHOISsean.dev)). Short answer: **the backend cannot run there**, but you can **tie the vault into the same domain and site** in a few ways.

---

## Is whoissean.dev a domain name?

**Yes.** **whoissean.dev** is your **domain name** (you bought it from Porkbun). The **blog** lives at that domain and is hosted by **GitHub Pages**—GitHub serves the static Jekyll site when people visit `https://whoissean.dev`. So:

- **whoissean.dev** = your domain (root).
- **vault.whoissean.dev** = a **subdomain** of that same domain; you can point it to your Ubuntu/Docker server so the vault is reachable there.

---

## What you need on Ubuntu / Docker to host the vault and tie it to whoissean.dev

To host the vault and have it available at something like **https://vault.whoissean.dev**, you need the following **on the machine that runs Docker** (your Ubuntu homelab or laptop).

### 1. Docker (already in place)

- Docker and Docker Compose installed.
- The password-vault app running as a container (we’ll build this in the project). The app will listen on a port inside the container (e.g. 8000).

### 2. A way to expose the vault to the internet (choose one)

You have to make the vault reachable so that when someone goes to `https://vault.whoissean.dev`, the request reaches your Ubuntu box and then the Docker container.

**Option A — Reverse proxy on Ubuntu (Nginx) + port open to internet**

- **Nginx** (or Caddy) installed on the Ubuntu host (or in its own container) as a **reverse proxy**.
- Nginx:
  - Listens for HTTPS on port 443 for hostname `vault.whoissean.dev`.
  - Terminates TLS (HTTPS) using a certificate (e.g. **Let’s Encrypt** via Certbot).
  - Proxies requests to the vault container (e.g. `http://localhost:8000` or `http://vault-app:8000`).
- Your **router** forwards port 443 (and maybe 80 for HTTP→HTTPS redirect) to this Ubuntu machine.
- **DNS:** At Porkbun (or wherever you manage whoissean.dev), add an **A record**: `vault.whoissean.dev` → your home’s **public IP**. (If your IP changes, use a dynamic DNS service and point the A record to that hostname.)

**Option B — Tunnel (no open ports, often easier)**

- Run a **tunnel** on the Ubuntu machine so that traffic to a public hostname is forwarded to your laptop/homelab. You don’t open ports on your router.
- **Cloudflare Tunnel (cloudflared):** You install `cloudflared` on Ubuntu, create a tunnel, and in the Cloudflare dashboard you add a **CNAME**: `vault.whoissean.dev` → `<tunnel-id>.cfargotunnel.com`. Traffic to `vault.whoissean.dev` goes to Cloudflare, then through the tunnel to your machine. Cloudflare can also provide the TLS certificate.
- **Tailscale Funnel:** If you use Tailscale, you can expose the vault via a Funnel so it’s reachable from the internet at a Tailscale URL; you can then CNAME `vault.whoissean.dev` to that URL if Tailscale supports it, or use the Tailscale URL directly.

For “tie it to whoissean.dev,” you mainly need **DNS** to point **vault.whoissean.dev** to wherever the vault is (your IP or the tunnel hostname).

### 3. DNS (at your domain registrar)

- You already use **whoissean.dev** for the blog (likely an A record to GitHub Pages or a CNAME to `username.github.io`).
- For the vault, add a **separate** record for the **subdomain**:
  - **If using Nginx + public IP:** **A record** `vault` → your Ubuntu server’s public IP (or your dynamic DNS hostname).
  - **If using Cloudflare Tunnel:** **CNAME record** `vault` → `<your-tunnel>.cfargotunnel.com` (exact value from the tunnel setup).

So: **whoissean.dev** stays pointing at GitHub Pages for the blog; **vault.whoissean.dev** points to your Ubuntu/Docker setup.

### 4. Summary checklist (Ubuntu / Docker side)

| What | Where | Purpose |
|------|--------|--------|
| Password vault app | Docker container | Serves the vault API + web UI (e.g. port 8000). |
| Nginx (or Caddy) | Ubuntu host or container | Reverse proxy for `vault.whoissean.dev`, HTTPS (TLS), proxy to vault container. |
| TLS certificate | Nginx/Caddy (e.g. Certbot) or Cloudflare | So `https://vault.whoissean.dev` works. |
| **OR** Cloudflare Tunnel | Ubuntu (cloudflared) | Expose vault without opening ports; TLS handled by Cloudflare. |
| DNS record for `vault.whoissean.dev` | Porkbun / Cloudflare / etc. | A record to your IP, or CNAME to tunnel hostname. |

You don’t need to change anything on the **whoissean.dev** GitHub Pages site for the vault to *work*; you only need DNS + Ubuntu/Docker as above. Adding a **link** on the blog to `https://vault.whoissean.dev` is optional (so people can find the vault from your site).

---

## Why the full app can’t run on whoissean.dev

- **whoissean.dev** is a **Jekyll static site** on **GitHub Pages**. GitHub Pages only serves static files (HTML, CSS, JS). It does **not** run Python, Node, or any server-side code.
- The **password vault** needs:
  - A **backend** (FastAPI + SQLite + crypto, session, audit).
  - That backend must run on a **server** (your Docker on Ubuntu homelab).

So the vault **backend** will always run on your homelab (Docker). The only question is: where does the **UI** live, and how do users reach it?

---

## Options for “piggybacking” on whoissean.dev

### Option A — Subdomain + link (recommended)

**Idea:** Run the whole vault app (backend + web UI) in Docker on your homelab. Expose it on a **subdomain** of your domain, e.g. **`vault.whoissean.dev`**. Then, on whoissean.dev, add a **link** (nav item or dedicated page) that points to `https://vault.whoissean.dev`.

**Pros:**

- One place for the app; no CORS or split hosting.
- Same domain family (whoissean.dev / vault.whoissean.dev); you can use one cert (e.g. wildcard or separate cert for subdomain).
- Blog and vault feel connected without mixing Jekyll with app code.

**What you need:**

1. **DNS:** Create a record for `vault.whoissean.dev`:
   - **If the vault is public:** A/CNAME to the IP or hostname of your homelab (or to a tunnel endpoint, e.g. Cloudflare Tunnel, Tailscale Funnel).
   - **If the vault is private (VPN only):** Same DNS, but only reachable when users are on your VPN.
2. **Homelab:** Vault container listening on HTTPS (or behind Nginx with TLS). Optionally use Cloudflare Tunnel so you don’t open ports.
3. **whoissean.dev (Jekyll):** Add a link to `https://vault.whoissean.dev` in the nav or on a “Projects” / “Tools” page.

**Piggyback:** The **branding and discovery** live on whoissean.dev; the **app** lives at vault.whoissean.dev.

---

### Option B — Static vault UI in the Jekyll repo, API on homelab

**Idea:** Build the vault **front-end** as a static app (HTML/JS, or static export). Put that inside the [WHOISsean.dev](https://github.com/sfh1980/WHOISsean.dev) repo (e.g. under `vault/` or a dedicated layout). GitHub Pages serves that UI at e.g. **`https://whoissean.dev/vault/`**. The UI calls your vault **API** at e.g. `https://vault.whoissean.dev/api/` (or whatever URL points to your homelab).

**Pros:**

- The vault “lives” inside the same site and repo as the blog (true UI piggyback).
- One repo, one deployment for the blog + vault UI.

**Cons:**

- **CORS:** The API (on homelab) must allow `https://whoissean.dev` (and/or `https://whoissean.dev/vault/`) in `Access-Control-Allow-Origin`.
- **Security:** The API must be reachable from the public (or only when on VPN). If public, use HTTPS, strong auth, and rate limiting.
- **Cookie/session:** If the API uses cookies, they’re for `vault.whoissean.dev`, not `whoissean.dev`, so you’d typically use token-based auth (e.g. session token in memory or a cookie set by the API domain).

**What you need:**

1. **Homelab:** Vault API at `https://vault.whoissean.dev` (or similar), with CORS allowing `https://whoissean.dev`.
2. **Jekyll repo:** Add the static vault UI (e.g. `vault/index.html` + assets, or a Jekyll page that loads the app). Exclude from Jekyll processing if it’s a pre-built SPA (e.g. put built files in `vault/` and add `vault/` to `include` or serve it as static).
3. **whoissean.dev:** Link to `https://whoissean.dev/vault/` from the main site.

**Piggyback:** The **UI** is served from whoissean.dev; the **API and data** stay on your homelab.

---

### Option C — Link only (minimal)

**Idea:** Don’t host any vault code on whoissean.dev. Run the vault at any URL (e.g. `https://vault.whoissean.dev` or `https://homelab.local/vault`). On whoissean.dev, add a single **link** (e.g. “Password Vault” in the nav or on the about page) to that URL.

**Pros:** Easiest; no CORS, no static UI in Jekyll.  
**Piggyback:** Only via **discovery** (your blog points people to the vault).

---

## Recommendation

- **Start with Option A:** Run the full app at **`vault.whoissean.dev`** (Docker on homelab + DNS/tunnel). Add a clear link on whoissean.dev to `https://vault.whoissean.dev`. That gives you “piggyback” in terms of domain and traffic from the blog.
- **Consider Option B later** if you want the vault UI to literally live under whoissean.dev (e.g. whoissean.dev/vault/) and share the same repo; we’d then wire the static UI to the same API and document CORS/session in the vault app.

---

## What to add in the WHOISsean.dev repo (for A or C)

1. **Navigation**  
   In `_includes/header.html` (or wherever the nav is), add an item, e.g.:
   - **Vault** → `https://vault.whoissean.dev`

2. **Optional dedicated page**  
   Create e.g. `vault.markdown` (or `tools.markdown`) with front matter and a short blurb: “Family password vault — [Open Vault](https://vault.whoissean.dev).” Link that page from the nav or homepage.

3. **No backend in the repo**  
   The Jekyll repo stays static; no Python or Node server. The vault backend stays in the password-vault-app project and runs in Docker.

---

## Summary

| Question | Answer |
|----------|--------|
| Can the **full** vault (backend + DB) run on whoissean.dev? | **No** — GitHub Pages is static only. |
| Can the **web UI** be tied to whoissean.dev? | **Yes** — via subdomain (Option A) or by hosting the static UI in the Jekyll repo (Option B). |
| Easiest “piggyback”? | **Option A:** vault at `vault.whoissean.dev` + link from whoissean.dev. |

Once the vault app is built, we can add the exact nav snippet and optional Jekyll page to the WHOISsean.dev repo so you can drop them in after cloning. If you tell me whether you prefer A or B, the next step can be either (1) DNS/homelab checklist for `vault.whoissean.dev`, or (2) layout of the static vault UI under the Jekyll site and CORS/session notes for the API.

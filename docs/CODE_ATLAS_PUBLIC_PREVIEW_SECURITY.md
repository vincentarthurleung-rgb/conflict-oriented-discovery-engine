# C.O.D.E. Atlas Public Preview Security

C.O.D.E. Atlas may expose unpublished bundles, evidence text, source metadata, annotations, and draft metrics. Treat every preview as sensitive. This layer provides preview-grade controls, not full production or multi-tenant security.

## Create preconfigured users

Real user files are ignored by Git. Passwords are prompted without echo and stored only as PBKDF2-SHA256 hashes.

```bash
python -m code_engine.cli.atlas_user_admin create-user \
  --users-file configs/atlas_users.json \
  --username vincent --display-name "Vincent" --role admin

python -m code_engine.cli.atlas_user_admin list-users \
  --users-file configs/atlas_users.json
```

`--password-env` is intended for controlled automation. Do not put passwords directly in command arguments or shell history.

## Mode A: safest local-only

```bash
python -m code_engine.cli.system_b_serve_knowledge_explorer \
  --display-kg-root system_b_outputs/three_case_clean_kg_v3 \
  --review-root system_b_outputs/three_case_review \
  --host 127.0.0.1 --port 8765 --no-auth
```

This mode is for the local machine only. Do not expose it through a tunnel or public interface.

## Mode B: recommended temporary Cloudflare Tunnel preview

Generate a fresh session secret and keep Atlas bound to loopback:

```bash
export ATLAS_SECRET_KEY="$(python - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"

python -m code_engine.cli.system_b_serve_knowledge_explorer \
  --display-kg-root system_b_outputs/three_case_clean_kg_v3 \
  --review-root system_b_outputs/three_case_review \
  --users-file configs/atlas_users.json \
  --require-auth --public-preview \
  --host 127.0.0.1 --port 8765
```

In another terminal:

```bash
cloudflared tunnel --url http://127.0.0.1:8765
```

Do not expose a Flask debug server. A tunnel is a temporary preview mechanism, Atlas authentication remains required, and links must not be shared with untrusted people. Never place API keys or secrets in browser code.

## Mode C: VPS, Nginx, and UFW

Keep Atlas listening only on `127.0.0.1:8765`. Permit only SSH and web ingress:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

Example Nginx reverse proxy:

```nginx
server {
    listen 80;
    server_name atlas.example.com;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Configure HTTPS with Certbot or an equivalent TLS process before public use. This repository does not automate certificates, firewall changes, tunnel installation, backups, monitoring, or host hardening.

## Security boundaries

- No registration, OAuth, RBAC beyond stored role metadata, or multi-user database
- Sessions use an environment-provided secret in public-preview mode
- Annotation writes require a session-bound CSRF token
- Login throttling is in-memory and resets on process restart
- Annotation files use atomic replacement but do not provide multi-editor conflict resolution
- Authentication protects access; it does not make Atlas output biological validation

# C.O.D.E. Atlas Public Preview Security

C.O.D.E. Atlas Public Preview is intended for local development, controlled demos, and small human review groups. It is not a production SaaS user system.

## Local Development

Use no-auth only on loopback:

```bash
python -m code_engine.cli.system_b_serve_knowledge_explorer \
  --display-kg-root system_b_outputs/three_case_clean_kg_v3 \
  --review-root system_b_outputs/three_case_review \
  --no-auth \
  --host 127.0.0.1 \
  --port 8765
```

Do not expose `--no-auth` to the public internet.

## Public Preview

Use a stable secret key, a users file, auth, and a secured reverse proxy or tunnel:

```bash
export ATLAS_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"

python -m code_engine.cli.system_b_serve_knowledge_explorer \
  --display-kg-root system_b_outputs/three_case_clean_kg_v3 \
  --review-root system_b_outputs/three_case_review \
  --users-file configs/atlas_users.json \
  --require-auth \
  --public-preview \
  --host 127.0.0.1 \
  --port 8765
```

`--public-preview` requires `ATLAS_SECRET_KEY` and sets secure session cookies. It should be served through HTTPS. The CLI rejects binding public preview directly to non-loopback hosts.

## Create an Admin

```bash
python -m code_engine.cli.atlas_user_admin create-user \
  --users-file configs/atlas_users.json \
  --username vincent \
  --display-name "Vincent" \
  --role admin
```

Passwords are stored as PBKDF2-SHA256 hashes. Plaintext password fields are rejected when Atlas loads the users file.

## Invite-Only Registration

Registration is disabled by default. Create an invite first:

```bash
python -m code_engine.cli.atlas_user_admin create-invite \
  --users-file configs/atlas_users.json \
  --label pharmacy_batch_1 \
  --role reviewer \
  --max-uses 20 \
  --expires-in-days 14
```

The CLI prints the invite code once. The users file stores only a `sha256:` hash of that code. `list-invites` never displays plaintext invite codes.

Recommended invite settings:

- Use short expiry windows, typically 7-14 days.
- Set `--max-uses` to the actual number of expected reviewers.
- Use `--role reviewer` for external human reviewers.
- Disable leaked or unused invites immediately.

Enable registration only when needed:

```bash
python -m code_engine.cli.system_b_serve_knowledge_explorer \
  --display-kg-root system_b_outputs/three_case_clean_kg_v3 \
  --review-root system_b_outputs/three_case_review \
  --users-file configs/atlas_users.json \
  --require-auth \
  --public-preview \
  --allow-registration \
  --host 127.0.0.1 \
  --port 8765
```

Registered users are enabled immediately and receive the role configured on the invite, normally `reviewer`. Registration does not auto-login; users must log in after registration.

Disable a leaked invite immediately:

```bash
python -m code_engine.cli.atlas_user_admin disable-invite \
  --users-file configs/atlas_users.json \
  --label pharmacy_batch_1
```

## Security Controls

Atlas auth currently includes:

- PBKDF2-SHA256 password hashes.
- Atomic users file writes.
- Invite code hashes instead of plaintext invite storage.
- Login CSRF protection.
- CSRF protection for state-changing API requests.
- HttpOnly session cookies, `SameSite=Lax`, and `Secure` cookies in public preview.
- In-memory login and registration rate limiting.
- Security headers including CSP, frame denial, referrer policy, and clipboard permissions.

## Roles And Modes

Atlas distinguishes UI mode from authenticated role. UI mode is not a security boundary by itself.

Current allowed modes:

- `admin`: `pharma`, `reviewer`, `developer`
- `developer`: `pharma`, `reviewer`, `developer`
- `reviewer`: `pharma`, `reviewer`
- `pharma`: `pharma`

The server returns `allowed_modes` from `/api/session`, and the frontend hides unauthorized mode buttons. Reviewer users cannot enter developer mode through normal UI or by editing `localStorage`; unsupported modes are downgraded to the first allowed mode.

For public preview, reviewer/pharma JSON API responses also redact common debug fields such as source file paths, source lines, bundle paths, display priority scores, noise risk scores, and validator internals. Admin/developer users and no-auth local development retain full debug responses.

## Limits

Atlas Public Preview is not a production identity system:

- Lockout state is in memory and resets on process restart.
- There is no MFA, OAuth, email verification, password reset workflow, audit database, or distributed rate limit.
- Invite-only registration is for controlled review groups, not open self-service signup.
- If an invite code leaks, disable it and create a new one.
- Do not expose no-auth mode publicly.
- Enable `--allow-registration` only when you are actively collecting external reviewer accounts; leave registration disabled otherwise.

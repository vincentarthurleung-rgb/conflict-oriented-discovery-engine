# C.O.D.E. Atlas Invite Registration

Owner invite management is available at `/owner/invites`.

Invite codes are generated with cryptographically secure randomness. The database stores only `code_hash`; the plaintext invite code and registration link are shown once in the Owner response. Old invite plaintext cannot be recovered. Create a new invite when a code is lost.

Registration at `/register` accepts an invite code, username, display name, and password. The role comes from the invite, not from the browser. Errors remain generic to avoid invite enumeration. Invite usage increments in the same database transaction as user creation.

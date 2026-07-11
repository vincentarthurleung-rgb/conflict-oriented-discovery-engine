# C.O.D.E. Atlas Password And Session Security

Users can change their own password at `/account/security`.

Password changes, temporary password issuance, password reset completion, account disablement, role changes, and explicit session revocation increment `users.session_version`. Authenticated sessions store the version and are rejected on the next request if it no longer matches.

Password reset tokens are stored only as hashes in `password_reset_tokens`. Plain reset tokens are shown once. Audit metadata records token row IDs and target user IDs, never plaintext tokens or passwords.

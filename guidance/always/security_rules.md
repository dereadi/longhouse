# Security Rules (Always Apply)

- No credentials in source code. Use secrets_loader or environment variables.
- No PII in logs, thermals, or commit messages.
- All inter-node communication over WireGuard encrypted mesh.
- Pre-flight gate: validate outputs before writing to production paths.
- Protected paths list: never overwrite without governance approval.

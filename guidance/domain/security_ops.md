# Security Operations Guidance

- Shield: consent-first monitoring. Agent WILL NOT START without recorded consent.
- Evidence vault: immutable, encrypted, chain of custody on every access.
- Canary: port scanning, credential detection, config checking.
- Fire Guard: service watchdog every 2 minutes, known-down suppression.
- Medicine Woman: health monitoring every 15 minutes, phi-based assessment.
- No credentials in source code. Pre-commit hook blocks secrets.
- Crawdad audit requirement on all security-adjacent code.

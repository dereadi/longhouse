# Python Guidance

- Use `float()` for any value from PostgreSQL that might be `Decimal` type.
- Always `conn.commit()` after writes. Log before `conn.rollback()`.
- Prefer `psycopg2.extras.RealDictCursor` for readable results.
- Use `sys.path.insert(0, '/ganuda/lib')` for library imports.
- File paths must be absolute and within /ganuda/, /tmp/, or /home/dereadi/.
- Use cherokee_venv for dependencies: `/home/dereadi/cherokee_venv/bin/python`.

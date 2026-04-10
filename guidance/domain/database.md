# Database Guidance

- Primary DB: zammad_production on bluefin (10.100.0.2:5432)
- PgBouncer: port 6432 on bluefin (transaction mode)
- Use `get_db_config()` from `ganuda_db` for connection params
- CREATE INDEX CONCURRENTLY for production indexes
- Check index selectivity before creating (100% same value = useless index)
- thermal_memory_archive: 97K+ rows, temperature_score, sacred_pattern, original_content
- Always log before rollback: `logger.warning(f"ROLLBACK: {e}")`

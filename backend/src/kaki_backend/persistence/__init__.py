# v1.0 | 13-Sep-2026 | Create the SQLite persistence package for durable turns.
"""SQLite system of record for devices, sessions, turns and their provenance.

The schema comes from numbered SQL migrations applied at backend start
(`database.py`); application code reads and writes through repositories
(`repositories.py`) rather than issuing SQL itself. Decision record:
`docs/decisions/adr-0007-sqlite-persistence.md`.
"""

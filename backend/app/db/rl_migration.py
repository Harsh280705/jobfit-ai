"""Best-effort DDL for the additive RL columns on requirement_matches.

Fresh databases get the columns via Base.metadata.create_all. Pre-existing
databases (created before the RL extension) are patched with
ALTER TABLE ... ADD COLUMN guarded per-dialect, so current deployments keep
working without a manual migration step.
"""
from __future__ import annotations


RL_COLUMNS: dict[str, str] = {
    "existing_status": "VARCHAR(32)",
    "rl_status": "VARCHAR(32)",
    "rl_confidence": "FLOAT",
    "rl_changed": "BOOLEAN",
    "rl_used": "BOOLEAN",
}


def ensure_rl_columns_sync(conn) -> None:
    from sqlalchemy import inspect, text
    insp = inspect(conn)
    try:
        existing = {c["name"] for c in insp.get_columns("requirement_matches")}
    except Exception:
        return  # table does not exist yet; create_all will handle it
    for col, ddl in RL_COLUMNS.items():
        if col in existing:
            continue
        dialect = conn.dialect.name
        try:
            if dialect == "postgresql":
                conn.execute(text(f'ALTER TABLE requirement_matches ADD COLUMN IF NOT EXISTS "{col}" {ddl}'))
            else:
                conn.execute(text(f'ALTER TABLE requirement_matches ADD COLUMN "{col}" {ddl}'))
        except Exception:
            pass

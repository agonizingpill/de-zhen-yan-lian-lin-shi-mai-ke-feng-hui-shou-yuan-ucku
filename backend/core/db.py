from contextlib import contextmanager

from sqlalchemy import MetaData, create_engine, inspect, text

from core.config import DATABASE_URL

metadata = MetaData()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# 旧库 create_all 不会自动补列；这里幂等地补齐撤回与用样依据所需列，
# 旧结论行的新列保持 NULL，据此标记“无法核实”。
EXTRA_COLUMNS = {
    "sound_windows": {
        "withdrawn": "BOOLEAN NOT NULL DEFAULT 0",
        "withdrawn_by": "VARCHAR(80) NULL",
        "withdrawn_at": "DATETIME NULL",
        "withdraw_reason": "VARCHAR(200) NULL",
    },
    "feedback_findings": {
        "basis": "JSON NULL",
        "basis_detail": "JSON NULL",
    },
    "channel_tickets": {
        "test_basis": "JSON NULL",
    },
}


def ensure_columns():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in EXTRA_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {col["name"] for col in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


@contextmanager
def transaction():
    with engine.begin() as conn:
        yield conn

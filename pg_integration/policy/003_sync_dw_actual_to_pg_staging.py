from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pyodbc
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv


# -------------------------
# Load env
# -------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
DW_ENV_PATH = REPO_ROOT / "dw_mssql" / "config" / "dw.env"
PG_ENV_PATH = REPO_ROOT / "pg_integration" / "config" / "pg.env"

load_dotenv(DW_ENV_PATH)
load_dotenv(PG_ENV_PATH)


def _need(key: str) -> str:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        raise RuntimeError(f"Missing env var: {key}")
    return v.strip()


def build_mssql_conn_str() -> str:
    driver = os.getenv("DW_MSSQL_DRIVER", "ODBC Driver 17 for SQL Server")

    host = _need("DW_MSSQL_HOST")
    port = _need("DW_MSSQL_PORT")
    db = _need("DW_MSSQL_DB")
    user = _need("DW_MSSQL_USER")
    pwd = _need("DW_MSSQL_PASSWORD")

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={host},{port};"
        f"DATABASE={db};"
        f"UID={user};"
        f"PWD={pwd};"
        "TrustServerCertificate=yes;"
    )


def build_pg_conn_kwargs() -> dict:
    return {
        "host": _need("PG_HOST"),
        "port": int(_need("PG_PORT")),
        "dbname": _need("PG_DB"),
        "user": _need("PG_USER"),
        "password": _need("PG_PASSWORD"),
    }


def fetch_from_mssql() -> pd.DataFrame:
    sql = """
    SELECT
        canonical_dish_id,
        close_work_date,
        qty,
        CAST(is_shop_closed AS int) AS is_shop_closed,
        loaded_at
    FROM dw.fact_daily_demand_actual;
    """

    with pyodbc.connect(build_mssql_conn_str()) as conn:
        df = pd.read_sql(sql, conn)

    return df


def load_into_pg_staging(df: pd.DataFrame) -> int:
    if df.empty:
        print("[WARN] No rows to load into staging.")
        return 0

    df = df.copy()

    # MSSQL bit/int -> PG boolean
    df["is_shop_closed"] = df["is_shop_closed"].astype(int).map(lambda x: True if x == 1 else False)

    cols = ["canonical_dish_id", "close_work_date", "qty", "is_shop_closed", "loaded_at"]
    rows = list(df[cols].itertuples(index=False, name=None))

    with psycopg2.connect(**build_pg_conn_kwargs()) as pg:
        with pg.cursor() as cur:
            cur.execute("TRUNCATE TABLE integration.stg_fact_daily_demand_actual;")

            execute_values(
                cur,
                """
                INSERT INTO integration.stg_fact_daily_demand_actual
                (canonical_dish_id, close_work_date, qty, is_shop_closed, loaded_at)
                VALUES %s
                """,
                rows,
                page_size=5000,
            )
        pg.commit()

    print(f"[OK] Loaded {len(rows)} rows into integration.stg_fact_daily_demand_actual.")
    return len(rows)


def main() -> None:
    print(f"[INFO] Using DW env: {DW_ENV_PATH}")
    print(f"[INFO] Using PG env: {PG_ENV_PATH}")

    df = fetch_from_mssql()
    print(f"[INFO] Fetched {len(df)} rows from MSSQL dw.fact_daily_demand_actual.")
    load_into_pg_staging(df)


if __name__ == "__main__":
    main()
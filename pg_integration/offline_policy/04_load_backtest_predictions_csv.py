from __future__ import annotations

import os
from io import StringIO
from pathlib import Path
from typing import List

import pandas as pd
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / "pg_integration" / "config" / "pg_backtest.env" # pg_backtest.env
DEFAULT_CSV_PATH = PROJECT_ROOT.parent / "EDA_v3" / "runs" / "exp_003_lgbm_tweedie_p15_lag7_14_21_28_finalfeat__20260305_223540" / "backtest_predictions.csv"

REQUIRED_COLS = [
    "run_id",
    "fold_id",
    "forecast_origin_date",
    "target_date",
    "canonical_dish_id",
    "model_version",
    "y_true",
    "yhat",
    "residual",
    "abs_error",
]

OPTIONAL_COLS = [
    "baseline_method",
    "created_at",  # if missing, DB default now() will apply
]


def _env(name: str, default: str | None = None, *, required: bool = False) -> str:
    v = os.getenv(name, default)
    if required and (v is None or str(v).strip() == ""):
        raise RuntimeError(f"Missing required env var: {name}")
    return str(v)


def _build_pg_conn():
    host = _env("PG_HOST", required=True)
    port = int(_env("PG_PORT", "5433"))
    db = _env("PG_DB", required=True)
    user = _env("PG_USER", required=True)
    pwd = _env("PG_PASSWORD", required=True)

    return psycopg2.connect(host=host, port=port, dbname=db, user=user, password=pwd)


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    # 1) validate required columns
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    # 2) keep only columns we will load
    cols: List[str] = REQUIRED_COLS[:]
    for c in OPTIONAL_COLS:
        if c in df.columns:
            cols.append(c)
    df = df[cols].copy()

    # 3) normalize types
    df["fold_id"] = df["fold_id"].astype(int)
    df["canonical_dish_id"] = df["canonical_dish_id"].astype(int)

    # dates: accept "YYYY-MM-DD" or datetime; coerce to date string
    df["forecast_origin_date"] = pd.to_datetime(df["forecast_origin_date"]).dt.date.astype(str)
    df["target_date"] = pd.to_datetime(df["target_date"]).dt.date.astype(str)

    # numerics
    for c in ["y_true", "yhat", "residual", "abs_error"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # created_at: if exists, keep; else omit so DB default applies
    if "created_at" in df.columns:
        # allow iso string; keep as-is (COPY will parse timestamptz if format ok)
        df["created_at"] = df["created_at"].astype(str)

    return df


def main() -> None:
    # 1) Load env
    if not ENV_PATH.exists():
        raise FileNotFoundError(f"Env file not found: {ENV_PATH}")
    load_dotenv(dotenv_path=ENV_PATH)
    
    # 2) Determine target table
    schema = _env("PG_SCHEMA", "integration")
    table = _env("PG_TABLE", "fact_backtest_forecast_daily")
    
    # 3) Determine CSV path:
    # - prefer env BACKTEST_CSV_PATH if provided
    # - otherwise use your given default path

    csv_path = Path(_env("BACKTEST_CSV_PATH", str(DEFAULT_CSV_PATH))).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    # 4) Load + normalize
    df = pd.read_csv(csv_path)
    df = _normalize_df(df)
    load_cols = list(df.columns)
    
    # DEBUG
    print("[DEBUG] columns:", load_cols)
    print("[DEBUG] rows:", len(df))
    print("[DEBUG] csv path:", csv_path)

    # 5) Convert to in-memory CSV for COPY
    buf = StringIO()
    df.to_csv(buf, index=False, header=True)
    buf.seek(0)

    conn = _build_pg_conn()
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            # 1) create temp staging table (same structure as target)
            tmp_name = "tmp_backtest_ingest"
            cur.execute(
                sql.SQL("CREATE TEMP TABLE {} (LIKE {}.{} INCLUDING DEFAULTS) ON COMMIT DROP;").format(
                    sql.Identifier(tmp_name),
                    sql.Identifier(schema),
                    sql.Identifier(table),
                )
            )

            # 2) COPY into temp table (only selected columns)
            copy_sql = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE);").format(
                sql.Identifier(tmp_name),
                sql.SQL(", ").join(sql.Identifier(c) for c in load_cols),
            )
            cur.copy_expert(copy_sql.as_string(cur), buf)

            # 3) insert into target with ON CONFLICT DO NOTHING (idempotent)
            insert_sql = sql.SQL("""
                INSERT INTO {}.{} ({})
                SELECT {} FROM {}
                ON CONFLICT DO NOTHING;
            """).format(
                sql.Identifier(schema),
                sql.Identifier(table),
                sql.SQL(", ").join(sql.Identifier(c) for c in load_cols),
                sql.SQL(", ").join(sql.Identifier(c) for c in load_cols),
                sql.Identifier(tmp_name),
            )
            cur.execute(insert_sql)

        conn.commit()
        print(f"[OK] Loaded {len(df)} rows from {csv_path} into {schema}.{table} (idempotent).")

    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
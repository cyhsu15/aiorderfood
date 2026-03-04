#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Load sales/menu Excel into MSSQL staging tables:
- stg.stg_sales
- stg.stg_menu
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from decimal import Decimal, ROUND_HALF_UP

try:
    import pyodbc  # type: ignore
except ImportError as e:
    raise SystemExit(
        "Missing dependency: pyodbc. Install it in your venv.\n"
        "Example: pip install pyodbc"
    ) from e


# ---- Paths (adjust to your repo layout) ----
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # dw_mssql/
DEFAULT_ENV = PROJECT_ROOT / "config" / "dw.env"

DEFAULT_SALES_EXCEL = PROJECT_ROOT / "data" / "sales.xlsx"  # 銷量excel
DEFAULT_MENU_EXCEL = PROJECT_ROOT / "data" / "menu.xlsx"    # 菜單excel
DEFAULT_SALES_SHEET = "Sheet1"
DEFAULT_MENU_SHEET = "foods"

# ---- Targets ----
SALES_TABLE = "stg.stg_sales"
MENU_TABLE = "stg.stg_menu"

# ---- Column maps (Excel -> DB) ----
SALES_COLUMN_MAP = {
    "CloseWorkDate": "close_work_date",
    "FoodID": "food_id",
    "FoodName": "food_name",
    "dinein(內用)": "dinein_qty",
    "reserve(預訂)": "reserve_qty",
    "數量": "qty",
}
MENU_COLUMN_MAP = {
    "food_id": "food_id",
    "food_name": "food_name",
    "category": "category_raw",
    "price": "price",
    "create_date": "create_date",
    "shop_id": "shop_id",
}

REQUIRED_SALES_COLS = list(SALES_COLUMN_MAP.keys())
REQUIRED_MENU_COLS = list(MENU_COLUMN_MAP.keys())


# ------------------ env / connection ------------------
def load_env_file(env_path: Path) -> Dict[str, str]:
    if not env_path.exists():
        raise FileNotFoundError(f"Env file not found: {env_path}")

    env: Dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def pick_driver() -> str:
    preferred = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server",
    ]
    installed = []
    try:
        installed = [d for d in pyodbc.drivers()]
    except Exception:
        installed = []

    for name in preferred:
        if name in installed:
            return name

    if installed:
        return installed[-1]

    raise RuntimeError(
        "No ODBC drivers detected by pyodbc. "
        "Install 'ODBC Driver 18 for SQL Server' (recommended) or equivalent."
    )


def build_conn_str(env: Dict[str, str]) -> str:
    host = env.get("DW_MSSQL_HOST", "localhost")
    port = env.get("DW_MSSQL_PORT", "1433")
    db = env.get("DW_MSSQL_DB", "")
    user = env.get("DW_MSSQL_USER", "")
    pwd = env.get("DW_MSSQL_PASSWORD", "")

    driver = pick_driver()
    encrypt = env.get("DW_MSSQL_ENCRYPT", "no")
    trust_cert = env.get("DW_MSSQL_TRUST_SERVER_CERT", "yes")

    if not db or not user:
        raise ValueError("Missing required env vars: DW_MSSQL_DB / DW_MSSQL_USER")

    server = f"tcp:{host},{port}"
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={db};"
        f"UID={user};"
        f"PWD={pwd};"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate={trust_cert};"
        f"Connection Timeout=30;"
    )


# ------------------ IO helpers ------------------
def read_excel(excel_path: Path, sheet: str) -> pd.DataFrame:
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel not found: {excel_path}")
    df = pd.read_excel(excel_path, sheet_name=sheet, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _parse_excel_date(v):
    """
    Robust parser for date-ish columns:
    supports:
      - yyyymmdd (e.g., 20230101) as int/str
      - Excel serial (e.g., 45213)
      - datetime/Timestamp
      - strings like 2023/01/01, 2023-01-01
    Return: python date or None
    """
    if pd.isna(v):
        return None

    if isinstance(v, pd.Timestamp):
        return v.date()

    s = str(v).strip()

    if re.fullmatch(r"\d{8}", s):
        dt = pd.to_datetime(s, format="%Y%m%d", errors="coerce")
        return None if pd.isna(dt) else dt.date()

    try:
        f = float(s)
        if f.is_integer():
            n = int(f)
            if 1 <= n <= 60000:
                dt = pd.to_datetime(n, unit="D", origin="1899-12-30", errors="coerce")
                return None if pd.isna(dt) else dt.date()
    except Exception:
        pass

    dt = pd.to_datetime(s, errors="coerce")
    return None if pd.isna(dt) else dt.date()


def _clean_price_to_decimal(v):
    """
    Convert messy Excel price values to Decimal(12,2) or None.
    Handles: '1,200', '$1200', ' 1200 ', '', NaN
    """
    if pd.isna(v):
        return None

    s = str(v).strip()
    if s == "":
        return None

    # remove commas and currency symbols and spaces
    s = s.replace(",", "")
    s = re.sub(r"[^\d\.\-]", "", s)  # keep digits, dot, minus

    if s in ("", ".", "-", "-."):
        return None

    try:
        d = Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return d
    except Exception:
        return None


def _parse_excel_datetime(v):
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    s = str(v).strip()
    if s == "":
        return None
    dt = pd.to_datetime(s, errors="coerce")
    return None if pd.isna(dt) else dt.to_pydatetime()


# ------------------ transforms ------------------
def validate_and_transform_sales(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_SALES_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            "Sales Excel is missing required columns:\n"
            f"  missing: {missing}\n"
            f"  seen: {list(df.columns)}"
        )

    df = df[REQUIRED_SALES_COLS].copy()

    df["CloseWorkDate"] = df["CloseWorkDate"].apply(_parse_excel_date)

    for col in ["dinein(內用)", "reserve(預訂)", "數量"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    df["FoodID"] = df["FoodID"].astype("string").str.strip()
    df["FoodName"] = df["FoodName"].astype("string")

    not_null_cols = ["CloseWorkDate", "FoodID", "dinein(內用)", "reserve(預訂)", "數量"]
    bad_mask = df[not_null_cols].isna().any(axis=1)
    if bad_mask.any():
        bad = df.loc[bad_mask, not_null_cols].head(20)
        raise ValueError(
            "Sales: Found NULLs after coercion in NOT NULL columns.\n"
            f"Sample bad rows (first 20):\n{bad.to_string(index=False)}"
        )

    for col in ["dinein(內用)", "reserve(預訂)", "數量"]:
        df[col] = df[col].astype(int)

    df = df.rename(columns=SALES_COLUMN_MAP)
    return df


def validate_and_transform_menu(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_MENU_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            "Menu Excel is missing required columns:\n"
            f"  missing: {missing}\n"
            f"  seen: {list(df.columns)}"
        )

    df = df[REQUIRED_MENU_COLS].copy()

    # types
    df["food_id"] = df["food_id"].astype("string").str.strip()
    df["food_name"] = df["food_name"].astype("string")
    df["category"] = df["category"].astype("string")

    df["price"] = df["price"].apply(_clean_price_to_decimal)
    df["create_date"] = df["create_date"].apply(_parse_excel_datetime)
    df["shop_id"] = df["shop_id"].astype("string").str.strip()

    # food_id is NOT NULL in your stg.stg_menu
    bad_mask = df["food_id"].isna()
    if bad_mask.any():
        bad = df.loc[bad_mask, ["food_id", "food_name", "category"]].head(20)
        raise ValueError(
            "Menu: Found NULL food_id (NOT NULL in DB).\n"
            f"Sample bad rows (first 20):\n{bad.to_string(index=False)}"
        )

    df = df.rename(columns=MENU_COLUMN_MAP)
    return df


# ------------------ DB actions ------------------
def truncate_table(cur: "pyodbc.Cursor", table: str) -> None:
    cur.execute(f"TRUNCATE TABLE {table};")


def insert_rows(cur: "pyodbc.Cursor", table: str, df: pd.DataFrame, cols: List[str], batch_size: int = 2000) -> int:
    col_sql = ", ".join([f"[{c}]" for c in cols])
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders});"

    records = list(df[cols].itertuples(index=False, name=None))
    total = 0

    cur.fast_executemany = True  # type: ignore[attr-defined]

    for i in range(0, len(records), batch_size):
        chunk = records[i : i + batch_size]
        cur.executemany(sql, chunk)
        total += len(chunk)

    return total


def print_counts(cur: "pyodbc.Cursor") -> None:
    for t in [SALES_TABLE, MENU_TABLE]:
        cur.execute(f"SELECT COUNT(*) FROM {t};")
        n = cur.fetchone()[0]
        print(f"[INFO] {t} rows: {n:,}")


# ------------------ main ------------------
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Load sales/menu Excel to MSSQL stg tables.")
    parser.add_argument("--env", type=str, default=str(DEFAULT_ENV), help="Path to dw.env")

    parser.add_argument("--sales-excel", type=str, default=str(DEFAULT_SALES_EXCEL), help="Path to sales Excel")
    parser.add_argument("--sales-sheet", type=str, default=DEFAULT_SALES_SHEET, help="Sales sheet name")

    parser.add_argument("--menu-excel", type=str, default=str(DEFAULT_MENU_EXCEL), help="Path to menu Excel")
    parser.add_argument("--menu-sheet", type=str, default=DEFAULT_MENU_SHEET, help="Menu sheet name")

    parser.add_argument("--no-truncate", action="store_true", help="Do not TRUNCATE tables before insert")
    parser.add_argument("--batch-size", type=int, default=2000, help="executemany batch size")
    parser.add_argument("--only", choices=["sales", "menu", "all"], default="all", help="Load only sales/menu/all")
    parser.add_argument("--skip-counts", action="store_true", help="Skip printing row counts after load")
    args = parser.parse_args(argv)

    env_path = Path(args.env)
    sales_path = Path(args.sales_excel)
    menu_path = Path(args.menu_excel)

    print(f"[INFO] Env:         {env_path}")
    print(f"[INFO] Sales Excel: {sales_path} (sheet={args.sales_sheet}) -> {SALES_TABLE}")
    print(f"[INFO] Menu  Excel: {menu_path} (sheet={args.menu_sheet}) -> {MENU_TABLE}")
    print(f"[INFO] Mode: only={args.only}, truncate={'no' if args.no_truncate else 'yes'}")

    env = load_env_file(env_path)
    conn_str = build_conn_str(env)

    try:
        # Read & transform
        df_sales = None
        df_menu = None

        if args.only in ("sales", "all"):
            raw_sales = read_excel(sales_path, args.sales_sheet)
            df_sales = validate_and_transform_sales(raw_sales)
            print(f"[INFO] Sales rows ready: {len(df_sales):,}")

        if args.only in ("menu", "all"):
            raw_menu = read_excel(menu_path, args.menu_sheet)
            df_menu = validate_and_transform_menu(raw_menu)
            print(f"[INFO] Menu rows ready: {len(df_menu):,}")

        with pyodbc.connect(conn_str) as conn:
            conn.autocommit = False
            cur = conn.cursor()

            if not args.no_truncate:
                if args.only in ("sales", "all"):
                    print("[INFO] TRUNCATE sales stg ...")
                    truncate_table(cur, SALES_TABLE)
                if args.only in ("menu", "all"):
                    print("[INFO] TRUNCATE menu stg ...")
                    truncate_table(cur, MENU_TABLE)

            if df_sales is not None:
                print("[INFO] Inserting sales ...")
                inserted = insert_rows(
                    cur,
                    SALES_TABLE,
                    df_sales,
                    cols=["close_work_date", "food_id", "food_name", "dinein_qty", "reserve_qty", "qty"],
                    batch_size=args.batch_size,
                )
                print(f"[OK] Sales inserted: {inserted:,}")

            if df_menu is not None:
                print("[INFO] Inserting menu ...")
                inserted = insert_rows(
                    cur,
                    MENU_TABLE,
                    df_menu,
                    cols=["food_id", "food_name", "category_raw", "price", "create_date", "shop_id"],
                    batch_size=args.batch_size,
                )
                print(f"[OK] Menu inserted: {inserted:,}")

            conn.commit()

            if not args.skip_counts:
                print_counts(cur)

        return 0

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
# 只有 dw_env_path 路徑需要修改，其它部分跟 EDA_v3/src/data.py 完全一樣

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import sqlalchemy as sa
from dotenv import load_dotenv


def load_and_clean(config: Dict[str, Any]) -> pd.DataFrame:
    """
    Unified data loader for model input.

    Reads daily demand data from either:
        - CSV (fallback), or
        - DW MSSQL view (production source).

    Applies ONLY "I/O + canonical cleaning" (no feature engineering):
      - date parsing (+ optional timezone)
      - numeric casting
      - config-driven filters (date range, ids)
      - config-driven de-dup + sorting
      - schema validation

    Contract:
      - one row per (date × id_col)
      - stable sorting for time series safety
    """
    data_cfg = config["data"]
    source = data_cfg.get("source", "csv")
    
    # -----------------------
    # 1) Load
    # -----------------------
    if source == "csv":
        path = data_cfg["path"]
        df = pd.read_csv(path)

    elif source == "dw_mssql":
        dw_env_path = Path(__file__).resolve().parents[2] / "dw_mssql" / "config" / "dw.env" # ← 改這裡
        load_dotenv(dotenv_path=dw_env_path, override=True)
        
        host = os.getenv("DW_MSSQL_HOST")
        port = os.getenv("DW_MSSQL_PORT")
        db   = os.getenv("DW_MSSQL_DB")
        user = os.getenv("DW_MSSQL_USER")
        pwd  = os.getenv("DW_MSSQL_PASSWORD")

        view = data_cfg["dw_mssql"]["view"]
        
        conn_str = (
            f"mssql+pyodbc://{user}:{pwd}@{host}:{port}/{db}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&TrustServerCertificate=yes"
        )

        engine = sa.create_engine(conn_str)
        df = pd.read_sql(f"SELECT * FROM {view}", engine)
    
    else:
        raise ValueError(f"Unsupported data source: {source}")

    # -----------------------
    # 2) Parse / cast types
    # -----------------------
    date_col = data_cfg["date_col"]
    df[date_col] = pd.to_datetime(df[date_col])

    # numeric columns you know must be numeric
    numeric_cols = [
        data_cfg["target_col"],     # 數量
        "dinein(內用)",
        "reserve(預訂)",
        "price",
        "IsClosed",
        "IsMarketPrice",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # -----------------------
    # 3) Filters (config-driven)
    # -----------------------
    filters_cfg = data_cfg.get("filters", {}) or {}
    start_date = filters_cfg.get("start_date")
    end_date = filters_cfg.get("end_date")
    ids = filters_cfg.get("ids")
    
    if start_date:
        df = df[df[date_col] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df[date_col] <= pd.to_datetime(end_date)]
    
    id_col = data_cfg["id_col"]
    if ids:
        # keep everything as string for safety (CanonicalDishId / FoodID may be varchar)
        allow = {str(x) for x in ids}
        df = df[df[id_col].astype(str).isin(allow)]
    
    # -----------------------
    # 4) Cleaning (config-driven)
    # -----------------------
    cleaning_cfg = data_cfg.get("cleaning", {}) or {}

    # drop_duplicates
    dd_cfg = cleaning_cfg.get("drop_duplicates", {}) or {}
    if dd_cfg.get("enable", False):
        subset = dd_cfg.get("subset") or [id_col, date_col]
        keep = dd_cfg.get("keep", "last")
        df = df.drop_duplicates(subset=subset, keep=keep)

    # sorting (default to [id_col, date_col])
    sort_keys = cleaning_cfg.get("sort_keys") or [id_col, date_col]
    df = df.sort_values(sort_keys).reset_index(drop=True)
    
    # -----------------------
    # 5) Validate
    # -----------------------
    _validate_schema(df, config)

    return df


def _validate_schema(df: pd.DataFrame, config: Dict[str, Any]) -> None:
    """
    Raise error if the dataframe does not satisfy minimal schema assumptions.
    """
    data_cfg = config["data"]

    required_cols = [
        data_cfg["date_col"],        # CloseWorkDate
        data_cfg["id_col"],          # CanonicalDishId
        data_cfg.get("name_col", "FoodName"),
        data_cfg["target_col"],      # 數量
        "dinein(內用)",
        "reserve(預訂)",
        "IsClosed",
        "category",
        "price",
        "IsMarketPrice",
    ]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # date column type
    date_col = data_cfg["date_col"]
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        raise TypeError(f"{date_col} must be datetime type")
    
    # target must be numeric
    target_col = data_cfg["target_col"]
    if not pd.api.types.is_numeric_dtype(df[target_col]):
        raise TypeError(f"{target_col} must be numeric")
    
    # IsClosed / IsMarketPrice should be 0/1
    for col in ["IsClosed", "IsMarketPrice"]:
        if col in df.columns:
            bad = df[~df[col].isin([0, 1]) & df[col].notna()]
            if len(bad) > 0:
                raise ValueError(f"{col} must be 0 or 1 only")

    # no duplicated (ID, Date)
    id_col = data_cfg["id_col"]
    dup = df.duplicated(subset=[id_col, date_col])
    if dup.any():
        raise ValueError(
            f"Duplicated (ID, Date) rows found:\n{df.loc[dup, [id_col, date_col]].head()}"
        )
    
    # optional: no negative quantity
    neg = df[target_col] < 0
    if neg.any():
        raise ValueError(f"Negative values found in {target_col}")
    
    print("[OK] Data schema validation passed.")

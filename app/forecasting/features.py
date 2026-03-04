from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


# -----------------------------
# Single source of truth: feature columns
# (Copied from EDA_v3/src/features.py; keep identical logic)
# -----------------------------
def get_feature_columns(config: Dict[str, Any]) -> list[str]:
    """
    Single source of truth:
    - feature set
    - feature order
    """
    feat_cfg = config.get("features", {})

    base_cfg = feat_cfg.get("base", {})
    cal_cfg = feat_cfg.get("calendar", {})
    lag_cfg = feat_cfg.get("lag", {})
    roll_cfg = feat_cfg.get("rolling", {})

    cols: list[str] = []

    # ---- base (global/static-ish features) ----
    if base_cfg.get("use_id_as_feature", True):
        cols.append(config["data"]["id_col"])
    if base_cfg.get("use_category", False):
        cols.append("category")
    if base_cfg.get("use_price", False):
        cols.append("price")
    if base_cfg.get("use_is_market_price", False):
        cols.append("IsMarketPrice")

    # IsClosed：容錯兩種 config 放置方式
    if base_cfg.get("use_is_closed_day", False) or cal_cfg.get("use_is_closed_day", False):
        cols.append("IsClosed")
    
    # ---- calendar ----
    if cal_cfg.get("use_dayofweek", False):
        cols.append("DayOfWeek")
    if cal_cfg.get("use_target_day", False):
        cols.append("target_day")

    # ---- lag ----
    if lag_cfg.get("enable", False):
        for k in (lag_cfg.get("lags", []) or []):
            cols.append(f"lag_{int(k)}")
    
    # ---- rolling ----
    if roll_cfg.get("enable", False):
        windows = roll_cfg.get("windows", []) or []
        stats = roll_cfg.get("stats", []) or []
        for w in windows:
            for s in stats:
                cols.append(f"roll_{s}_{int(w)}")

    return cols


def _unique_cols(cols: list[str]) -> list[str]:
    """
    Remove duplicates (Preserve order)
    """
    return list(dict.fromkeys(cols))


# -----------------------------
# Production: build forecast features (Tue..Sun only)
# -----------------------------
def build_horizon_dates(origin_date: date) -> List[date]:
    """
    helper:
        origin is Monday; predict Tue..Sun (6 days)
    """
    return [(origin_date + pd.Timedelta(days=i)) for i in range(1, 7)]


def build_features_for_forecast(
    history_df: pd.DataFrame,
    *,
    origin_date: date,
    config: Dict[str, Any],
    candidate_ids: Optional[Sequence[Any]] = None,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Production feature builder.
    - Input: cleaned history dataframe (config["data"]["path"])
    - Output: X_forecast (CanonicalDishId x Tue..Sun) + feature_cols (ordered)

    Guarantees:
    - Only Tue..Sun rows are generated -> target_day in 0..5
    - Leakage guard: any y after origin_date is treated as NaN for lag/rolling
    - Feature columns order equals get_feature_columns(config)

    Required history columns (your cleaned table):
      CloseWorkDate, CanonicalDishId, 數量, IsClosed, category, price, IsMarketPrice
    """
    data_cfg = config.get("data", {})

    date_col = data_cfg.get("date_col", "CloseWorkDate")
    id_col = data_cfg.get("id_col", "CanonicalDishId")
    target_col = data_cfg.get("target_col", "數量")

    df = history_df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    
    # --- ensure merge keys have consistent dtype ---
    df[id_col] = df[id_col].astype(str)

    # 1) targets = Tue..Sun only
    target_dates = build_horizon_dates(origin_date)
    target_dates_ts = pd.to_datetime(pd.Series(target_dates))

    # 2) candidate IDs
    if candidate_ids is None:
        ids = df[id_col].dropna().unique().tolist()
    else:
        ids = [str(x) for x in candidate_ids]

    # 3) build skeleton target rows (unknown y)
    target_df = pd.DataFrame(
        [(id, d) for id in ids for d in target_dates],
        columns=[id_col, date_col],
    )
    target_df[date_col] = pd.to_datetime(target_df[date_col])
    target_df[target_col] = pd.NA  # unknown future

    # --- single source of truth: feature set + order ---
    feature_cols = get_feature_columns(config)

    # 4) attach static fields (only if needed by feature_cols) using "last known per ID" from history
    static_candidates = ["category", "price", "IsMarketPrice"]
    static_cols = [c for c in static_candidates if (c in df.columns and c in feature_cols)]
    if static_cols:
        last_static = (
            df.sort_values([id_col, date_col])
              .groupby(id_col, as_index=False)[static_cols]
              .last()
        )
        target_df = target_df.merge(last_static, on=id_col, how="left")

    # 4.1) IsClosed: only generate if used; Tue..Sun forecast rows => always 0
    if "IsClosed" in feature_cols:
        target_df["IsClosed"] = 0
    
    # 5) combine history + target rows
    combined = pd.concat([df, target_df], ignore_index=True, sort=False)
    combined = combined.sort_values([id_col, date_col]).reset_index(drop=True)

    # 6) calendar features (only generate if required)
    if "DayOfWeek" in feature_cols:
        combined["DayOfWeek"] = combined[date_col].dt.dayofweek.astype(int)

    if "target_day" in feature_cols:
        horizon_start_wd = (origin_date.weekday() + 1) % 7  # Tue start
        combined["target_day"] = (combined[date_col].dt.dayofweek - horizon_start_wd) % 7
        # 因為我們只產 Tue..Sun rows，所以 target_day 會是 0..5
    
    # 7) leakage guard: future y must not be used for features
    combined["_y_for_feat"] = pd.to_numeric(combined[target_col], errors="coerce")
    future_mask = combined[date_col] > pd.to_datetime(origin_date)
    combined.loc[future_mask, "_y_for_feat"] = float("nan")

    # 8) lag features (generate only if required)
    lag_cols = [c for c in feature_cols if c.startswith("lag_")]
    for col in lag_cols:
        # col looks like "lag_7", "lag_14", ...
        k = int(col.split("_")[1])
        combined[col] = combined.groupby(id_col)["_y_for_feat"].shift(k)

    # 9) rolling features (generate only if required)
    roll_cols = [c for c in feature_cols if c.startswith("roll_")]
    for col in roll_cols:
        # col looks like "roll_mean_28"
        _, stat, w = col.split("_")
        w = int(w)
        base = combined.groupby(id_col)["_y_for_feat"].shift(1).rolling(w, min_periods=1)
        combined[col] = getattr(base, stat)().reset_index(level=0, drop=True)
    
    # 10) cast dtypes consistent with training assumptions
    # CanonicalDishId
    if id_col in feature_cols:
        combined[id_col] = combined[id_col].astype(str).astype("category")
    # category
    if "category" in feature_cols:
        combined["category"] = combined["category"].astype("category")
    
    # 11) slice forecast rows only (Tue..Sun)
    fc = combined.loc[combined[date_col].isin(target_dates_ts)].copy()
    fc = fc.rename(columns={date_col: "target_date"})

    missing = [c for c in feature_cols if c not in fc.columns]
    if missing:
        raise ValueError(f"Missing forecast feature columns: {missing}")

    # Return keys + features (keys help runner do mapping/upsert)
    key_cols = [id_col, "target_date"]
    out_cols = _unique_cols(key_cols + feature_cols)
    X_forecast = fc[out_cols].reset_index(drop=True)

    return X_forecast, feature_cols




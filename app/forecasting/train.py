"""
從 EDA_v3/src/train.py 複製，只保留需要的函數和資料結構
"""


from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, List
import pandas as pd
from pathlib import Path
import os
import pickle


class Model(Protocol):
    """A minimal protocol so you can swap sklearn / lightgbm easily."""
    def predict(self, X: pd.DataFrame) -> Any: ...


@dataclass
class TrainResult:
    # BaselineModel is a lookup-table model; we handle its prediction logic in predict().
    model: Any
    best_iteration: Optional[int] = None
    train_info: Optional[Dict[str, Any]] = None


@dataclass
class BaselineModel:
    """
    Baseline lookup model（基於訓練資料建立的查詢表模型）

    lookup_df columns:
      group_cols + ["y_pred"]
    
    重要設計決策：
    ---------------
    1. 查詢表只用訓練資料建立，驗證期間「不更新」
       → 模擬真實情境：預測未來時只能用「過去資料」

    2. observed=True 的原因：
       - 只保留訓練資料中實際出現的群組組合
       - 避免 pandas 未來版本的 deprecation warning
       - categorical 欄位的 groupby 行為依賴此參數
    
    3. 三層 fallback 機制：
       group_cols 查詢 → id_col 查詢 → global median
    """
    group_cols: List[str]
    lookup_df: pd.DataFrame
    fallback_by_id: Optional[pd.DataFrame] = None  # columns: [id_col, y_pred]
    global_fallback: float = 0.0


def _train_baseline(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_valid: pd.DataFrame,
    y_valid: pd.Series,
    config: Dict[str, Any],
) -> TrainResult:
    """
    Baseline training: build lookup table from TRAIN only (past-only).

    method="k_week_median":
    - For each group (e.g., CanonicalDishId, DayOfWeek), sort by date_col and take last k occurrences,
      then median -> y_pred.

    Required columns for k-week baseline:
    - groupby columns (e.g., CanonicalDishId, DayOfWeek)
    - date_col (e.g., CloseWorkDate) in X_train for time ordering
    """
    model_cfg = config["model"]
    bcfg = model_cfg["baseline"]

    data_cfg = config["data"]
    id_col = data_cfg["id_col"]
    date_col = data_cfg["date_col"]

    method = bcfg["method"]
    group_cols = list(bcfg.get("groupby", []))

    if method not in {"k_week_median", "seasonal_median"}:
        raise ValueError(f"Unknown baseline method: {method}")

    # --- global fallback (always available) ---
    global_fallback = float(pd.Series(y_train).median())

    # --- build lookup ---
    if method == "k_week_median":
        k_weeks = int(bcfg.get("k_weeks", 4))
        if k_weeks <= 0:
            raise ValueError("baseline.k_weeks must be > 0")
        
        need_cols = list(dict.fromkeys(group_cols + [date_col]))
        missing = [c for c in need_cols if c not in X_train.columns]
        if missing:
            raise ValueError(
                f"Baseline method '{method}' requires columns {need_cols}, but missing: {missing}. "
                f"Tip: for baseline training, pass date_col '{date_col}' into X_train."
            )

        df = X_train[need_cols].copy()
        df["_y"] = pd.Series(y_train).values
        df[date_col] = pd.to_datetime(df[date_col])

        # Sort within group by time and take last k occurrences per group (≈ last k weeks)
        df = df.sort_values(group_cols + [date_col])
        recent_k = (
            df.groupby(group_cols, dropna=False, observed=True, sort=False)
              .tail(k_weeks)
        )

        lookup = (
            recent_k.groupby(group_cols, dropna=False, observed=True)["_y"]
                    .median()
                    .reset_index()
                    .rename(columns={"_y": "y_pred"})
        )

        # fallback by id_col (also last k occurrences) if id_col exists
        fallback_by_id = None
        if id_col in X_train.columns and date_col in X_train.columns:
            tmp = pd.DataFrame(
                {
                    id_col: X_train[id_col].values,
                    date_col: pd.to_datetime(X_train[date_col]).values,
                    "_y": pd.Series(y_train).values,
                }
            ).sort_values([id_col, date_col])

            recent_k_id = (
                tmp.groupby(id_col, dropna=False, observed=True, sort=False)
                   .tail(k_weeks)
            )

            fallback_by_id = (
                recent_k_id.groupby(id_col, dropna=False, observed=True)["_y"]
                           .median()
                           .reset_index()
                           .rename(columns={"_y": "y_pred"})
            )

    else:
        # seasonal_median: simple training-history median by group (no time window)
        df = X_train[group_cols].copy()
        df["_y"] = pd.Series(y_train).values

        lookup = (
            df.groupby(group_cols, dropna=False, observed=True)["_y"]
              .median()
              .reset_index()
              .rename(columns={"_y": "y_pred"})
        )

        fallback_by_id = None
        if id_col in group_cols and id_col in X_train.columns:
            tmp = pd.DataFrame({id_col: X_train[id_col].values, "_y": pd.Series(y_train).values})
            fallback_by_id = (
                tmp.groupby(id_col, dropna=False, observed=True)["_y"]
                   .median()
                   .reset_index()
                   .rename(columns={"_y": "y_pred"})
            )

    model = BaselineModel(
        group_cols=group_cols,
        lookup_df=lookup,
        fallback_by_id=fallback_by_id,
        global_fallback=global_fallback,
    )

    return TrainResult(model=model, train_info={"baseline_method": method})


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_valid: pd.DataFrame,
    y_valid: pd.Series,
    config: Dict[str, Any],
) -> TrainResult:
    """
    Public API: fit a model for one fold.

    Contract:
    - experiment.py passes ONLY model input columns into X_train/X_valid (X[feature_cols]),
      except baseline training may additionally include date_col for time ordering.
    - This function dispatches by config["model"]["type"].
    """
    mtype = config["model"]["type"]

    if mtype == "baseline":
        return _train_baseline(X_train, y_train, X_valid, y_valid, config)

    if mtype == "lightgbm":
        return _train_lightgbm(X_train, y_train, X_valid, y_valid, config)

    raise ValueError(f"Unsupported model.type: {mtype}")


def predict(
    model: Any,
    X: pd.DataFrame,
    config: Dict[str, Any],
) -> pd.Series:
    """
    Make predictions.
    - For BaselineModel: merge lookup table on group_cols.
    - For other models (future): fall back to model.predict(X).

    Notes:
    - X is assumed to contain baseline group columns (e.g., CanonicalDishId, DayOfWeek).
    - 若 X 缺少這些欄位，錯誤處理邏輯：
      - 查不到群組 → 用 id_col fallback
      - 查不到 id_col → 用 global median
      - 不會產生 NaN 預測值
    """
    id_col = config["data"]["id_col"]
    
    # non-baseline models (e.g., LightGBM)
    if not isinstance(model, BaselineModel):
        # LightGBM Booster supports num_iteration
        if hasattr(model, "best_iteration") and getattr(model, "best_iteration"):
            return pd.Series(model.predict(X, num_iteration=model.best_iteration))
        return pd.Series(model.predict(X))

    group_cols = model.group_cols

    # Ensure required columns exist
    missing = [c for c in group_cols if c not in X.columns]
    if missing:
        raise ValueError(f"X is missing required baseline group columns: {missing}")

    out = X[group_cols].copy()

    # main lookup
    out = out.merge(model.lookup_df, on=group_cols, how="left")

    # fallback by id_col if needed
    if model.fallback_by_id is not None and id_col in out.columns:
        miss = out["y_pred"].isna()
        if miss.any():
            out = out.merge(
                model.fallback_by_id.rename(columns={"y_pred": "y_pred_food"}),
                on=[id_col],
                how="left",
            )
            out.loc[miss, "y_pred"] = out.loc[miss, "y_pred_food"]
            out = out.drop(columns=["y_pred_food"])

    # global fallback
    out["y_pred"] = out["y_pred"].fillna(model.global_fallback)

    return out["y_pred"].astype(float)


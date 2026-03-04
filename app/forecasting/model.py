from __future__ import annotations

import os
import pickle
from typing import Any, Optional, Sequence

import pandas as pd


def load_model(path: str):
    """
    Production model loader.

    Supports:
      - .txt  -> LightGBM Booster (native format)
      - .pkl  -> pickle (optional)
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model file not found: {path}")

    ext = os.path.splitext(path)[1].lower()

    if ext == ".txt":
        # LightGBM native model
        try:
            import lightgbm as lgb
        except ImportError:
            raise ImportError("LightGBM is required to load .txt model files")

        model = lgb.Booster(model_file=path)
        return model

    if ext == ".pkl":
        # Python pickle model
        with open(path, "rb") as f:
            obj = pickle.load(f)
        return obj
    
    raise ValueError(f"Unsupported model format: {ext} (Supported: .txt, .pkl)")


def predict_lgbm(
    model: Any,
    X: pd.DataFrame,
    feature_cols: Sequence[str],
    *,
    num_iteration: Optional[int] = None,
):
    """
    Predict using LightGBM Booster.

    Important: ALWAYS pass X[feature_cols] to guarantee:
      - same feature set
      - same feature order
    """
    X_in = X[list(feature_cols)]
   
    # If caller passes num_iteration, use it. Otherwise, try model.best_iteration if exists.
    if num_iteration is None and hasattr(model, "best_iteration") and getattr(model, "best_iteration"):
        num_iteration = int(getattr(model, "best_iteration"))

    if num_iteration is not None:
        return model.predict(X_in, num_iteration=num_iteration)
    return model.predict(X_in)



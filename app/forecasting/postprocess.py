from __future__ import annotations

import numpy as np


def postprocess_yhat(
    yhat,
    *,
    clip_negative: bool = True,
    round_to_int: bool = True,
):
    """
    Production postprocess:
      - clip: yhat >= 0
      - round: nearest int
    """
    y = np.asarray(yhat, dtype=float)

    if clip_negative:
        y = np.clip(y, 0, None)

    if round_to_int:
        y = np.rint(y).astype(int)

    return y

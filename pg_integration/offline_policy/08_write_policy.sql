WITH agg AS (
  SELECT
    canonical_dish_id,
    model_version,
    COUNT(*) AS n_rows,
    AVG(abs_error) AS mae
  FROM integration.fact_backtest_forecast_daily
  GROUP BY 1,2
),
ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY canonical_dish_id
      ORDER BY mae ASC, model_version ASC
    ) AS rn
  FROM agg
),
choice AS (
  SELECT
    canonical_dish_id,
    model_version AS chosen_model_version,
    mae,
    n_rows
  FROM ranked
  WHERE rn = 1
)
INSERT INTO integration.forecast_policy2
  (canonical_dish_id, chosen_model_version, effective_from, effective_to, is_active, note)
SELECT
  c.canonical_dish_id,
  c.chosen_model_version,
  CURRENT_DATE,
  NULL,
  TRUE,
  'offline policy from backtest: min MAE'
FROM choice c
ON CONFLICT (canonical_dish_id)
DO UPDATE SET
  chosen_model_version = EXCLUDED.chosen_model_version,
  effective_from = EXCLUDED.effective_from,
  effective_to = EXCLUDED.effective_to,
  is_active = EXCLUDED.is_active,
  note = EXCLUDED.note,
  updated_at = now();
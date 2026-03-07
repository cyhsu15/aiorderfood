CREATE OR REPLACE VIEW integration.vw_forecast_filtered_by_policy_latest AS
WITH ranked AS (
  SELECT
    r.*,
    ROW_NUMBER() OVER (
      PARTITION BY r.canonical_dish_id, r.target_date
      ORDER BY r.forecast_origin_date DESC, r.created_at DESC
    ) AS rn
  FROM integration.vw_forecast_filtered_by_policy r
)
SELECT
  canonical_dish_id,
  forecast_origin_date,
  target_date,
  yhat,
  model_version,
  run_id,
  created_at
FROM ranked
WHERE rn = 1;
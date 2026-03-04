-- baseline 規則：model_version LIKE 'baseline%'
CREATE OR REPLACE VIEW integration.vw_winrate_long AS
WITH base AS (
  SELECT canonical_dish_id, forecast_origin_date, wape AS base_wape
  FROM integration.vw_policy_eval_origin_dish_model
  WHERE model_version LIKE 'baseline%'
),
cand AS (
  SELECT canonical_dish_id, forecast_origin_date, model_version, wape AS model_wape
  FROM integration.vw_policy_eval_origin_dish_model
  WHERE model_version NOT LIKE 'baseline%'
)
SELECT
  c.canonical_dish_id,
  c.forecast_origin_date,
  c.model_version,
  c.model_wape,
  b.base_wape,
  (b.base_wape - c.model_wape) AS gain,
  CASE WHEN c.model_wape < b.base_wape THEN 1 ELSE 0 END AS is_win
FROM cand c
JOIN base b
  ON b.canonical_dish_id = c.canonical_dish_id
 AND b.forecast_origin_date = c.forecast_origin_date;
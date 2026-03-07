CREATE OR REPLACE VIEW integration.vw_forecast_filtered_by_policy AS
SELECT
  f.canonical_dish_id,
  f.forecast_origin_date,
  f.target_date,
  f.yhat,
  f.model_version,
  f.run_id,
  f.created_at
FROM integration.fact_forecast_daily f
JOIN integration.forecast_policy2 p
  ON p.canonical_dish_id = f.canonical_dish_id
 AND p.is_active = TRUE
 AND TRIM(f.model_version) = TRIM(p.chosen_model_version);


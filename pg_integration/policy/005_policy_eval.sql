CREATE OR REPLACE VIEW integration.vw_policy_eval_origin_dish_model AS
SELECT
  f.canonical_dish_id,
  f.forecast_origin_date,
  f.model_version,
  COUNT(*)                              AS n_days,
  SUM(ABS(a.qty - f.yhat))              AS sum_abs_err,
  NULLIF(SUM(ABS(a.qty)), 0)            AS sum_abs_actual,
  (SUM(ABS(a.qty - f.yhat)) / NULLIF(SUM(ABS(a.qty)), 0))::numeric(18,6) AS wape
FROM integration.fact_forecast_daily f
JOIN integration.fact_daily_demand_actual a
  ON a.canonical_dish_id = f.canonical_dish_id
 AND a.close_work_date   = f.target_date
WHERE a.is_shop_closed = false
GROUP BY
  f.canonical_dish_id, f.forecast_origin_date, f.model_version;
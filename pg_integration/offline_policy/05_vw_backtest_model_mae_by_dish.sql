CREATE OR REPLACE VIEW integration.vw_backtest_model_mae_by_dish AS
SELECT
  canonical_dish_id,
  model_version,
  COUNT(*) AS n_rows,
  AVG(abs_error) AS mae
FROM integration.fact_backtest_forecast_daily
GROUP BY 1,2;
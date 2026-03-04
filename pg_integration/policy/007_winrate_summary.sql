CREATE OR REPLACE VIEW integration.vw_winrate_summary AS
SELECT
  canonical_dish_id,
  model_version,
  COUNT(*)                      AS n_folds,
  AVG(is_win)::numeric(6,5)     AS win_rate,
  AVG(gain)::numeric(18,6)      AS avg_gain
FROM integration.vw_winrate_long
GROUP BY canonical_dish_id, model_version;
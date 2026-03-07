CREATE OR REPLACE VIEW integration.vw_policy_choice_from_backtest AS
WITH ranked AS (
  SELECT
    canonical_dish_id,
    model_version,
    n_rows,
    mae,
    ROW_NUMBER() OVER (
      PARTITION BY canonical_dish_id
      ORDER BY mae ASC, model_version ASC
    ) AS rn
  FROM integration.vw_backtest_model_mae_by_dish
)
SELECT
  canonical_dish_id,
  model_version AS chosen_model_version,
  mae,
  n_rows
FROM ranked
WHERE rn = 1;
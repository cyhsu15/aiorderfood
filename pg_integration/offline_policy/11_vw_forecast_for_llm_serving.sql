CREATE OR REPLACE VIEW integration.vw_forecast_for_llm_serving AS
WITH bridge_ranked AS (
    SELECT
        canonical_dish_id,
        dish_price_id,
        ROW_NUMBER() OVER (
            PARTITION BY canonical_dish_id
            ORDER BY dish_price_id ASC
        ) AS rn
    FROM integration.bridge_canonical_to_oltp
    WHERE is_active = TRUE
),
active_bridge AS (
    SELECT
        canonical_dish_id,
        dish_price_id
    FROM bridge_ranked
    WHERE rn = 1
)
SELECT
    ab.dish_price_id AS price_id,
    f.canonical_dish_id,
    f.forecast_origin_date,
    f.target_date,
    f.yhat,
    f.model_version,
    f.run_id
FROM integration.vw_forecast_filtered_by_policy_latest f
JOIN active_bridge ab
  ON ab.canonical_dish_id = f.canonical_dish_id;
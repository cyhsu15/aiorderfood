CREATE TABLE IF NOT EXISTS integration.stg_fact_forecast_daily
(
    canonical_dish_id     BIGINT NOT NULL,
    forecast_origin_date  DATE   NOT NULL,
    target_date           DATE   NOT NULL,
    yhat                  NUMERIC(18,6) NOT NULL,
    model_version         VARCHAR(255) NOT NULL,
    run_id                UUID NULL,
    created_at            TIMESTAMPTZ NULL
);
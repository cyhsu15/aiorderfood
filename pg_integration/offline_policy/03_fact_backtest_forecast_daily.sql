CREATE TABLE IF NOT EXISTS integration.fact_backtest_forecast_daily (
    -- lineage / identity
    run_id                text        NOT NULL,
    fold_id               int         NOT NULL,

    -- policy keys
    forecast_origin_date  date        NOT NULL,
    target_date           date        NOT NULL,
    canonical_dish_id     int         NOT NULL,

    -- model identity
    model_version         text        NOT NULL,

    -- values
    y_true                numeric     NOT NULL,
    yhat                  numeric     NOT NULL,
    residual              numeric     NOT NULL,
    abs_error             numeric     NOT NULL,

    -- metadata
    baseline_method       text        NULL,
    created_at            timestamptz NOT NULL DEFAULT now(),

    -- ✅ prevent duplicate writes (idempotent ingest)
    CONSTRAINT fact_backtest_forecast_daily_pk
        PRIMARY KEY (run_id, fold_id, model_version, canonical_dish_id, target_date),

    -- ✅ basic sanity checks
    CONSTRAINT chk_abs_error_nonneg CHECK (abs_error >= 0),
    CONSTRAINT chk_target_not_before_origin CHECK (target_date >= forecast_origin_date)
);
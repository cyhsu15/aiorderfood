CREATE TABLE IF NOT EXISTS integration.fact_forecast_daily
(
    -- Surrogate PK（方便允許重跑、允許同版本多次 run）
    forecast_sk           BIGSERIAL PRIMARY KEY,

    -- Grain key（仍用 canonical_dish_id 來接 DW 的分析實體）
    canonical_dish_id     BIGINT NOT NULL,
    forecast_origin_date  DATE   NOT NULL,  -- 例如：每週一（或你定義的 origin）
    target_date           DATE   NOT NULL,  -- 例如：預測的未來某一天

    -- Prediction
    yhat                  NUMERIC(18,6) NOT NULL,

    -- Lineage / Traceability
    model_version         VARCHAR(255) NOT NULL, -- e.g. lgbm_v003 / baseline_v1
    run_id                UUID NULL,             -- 建議用 UUID（你現在 run_id 看起來就是 UUID）
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 基本資料合理性（若有允許負值的情境再拿掉）
    CONSTRAINT ck_fact_forecast_daily_yhat_nonneg
        CHECK (yhat >= 0),

    CONSTRAINT ck_fact_forecast_daily_date_order
        CHECK (target_date >= forecast_origin_date),

    -- 同一個 run 內，避免同一筆被重複寫入
    -- Postgres 的 UNIQUE 對 NULL：允許多筆 NULL（和你 SQL Server 的語意一致）
    CONSTRAINT uq_fact_forecast_daily_run_grain
        UNIQUE (run_id, canonical_dish_id, forecast_origin_date, target_date, model_version)
);

-- 常用查詢索引（LLM 查詢/服務端查詢多半會用到）
CREATE INDEX IF NOT EXISTS ix_ffd_canonical_targetdate
    ON integration.fact_forecast_daily (canonical_dish_id, target_date);

CREATE INDEX IF NOT EXISTS ix_ffd_origin_model
    ON integration.fact_forecast_daily (forecast_origin_date, model_version);

CREATE INDEX IF NOT EXISTS ix_ffd_run_id
    ON integration.fact_forecast_daily (run_id);
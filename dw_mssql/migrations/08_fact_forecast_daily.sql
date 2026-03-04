IF OBJECT_ID('dw.fact_forecast_daily', 'U') IS NOT NULL
    DROP TABLE dw.fact_forecast_daily;
GO

CREATE TABLE dw.fact_forecast_daily
(
    -- Surrogate PK（方便允許重跑、允許同版本多次 run）
    forecast_sk          bigint IDENTITY(1,1) NOT NULL,

    -- Grain key
    canonical_dish_id    bigint        NOT NULL,
    forecast_origin_date date          NOT NULL,  -- 例如：每週一（或你定義的 origin）
    target_date          date          NOT NULL,  -- 例如：預測的未來某一天

    -- Prediction
    yhat                 decimal(18,6) NOT NULL,

    -- Lineage / Traceability
    model_version        nvarchar(255) NOT NULL,  -- 例如：lgbm_v003 / baseline_v1
    run_id               nvarchar(255) NULL,      -- 可選：一次 pipeline run 的識別（UUID/時間戳）
    created_at           datetime2(0)  NOT NULL CONSTRAINT DF_fact_forecast_daily_created_at DEFAULT (SYSUTCDATETIME()),

    CONSTRAINT PK_fact_forecast_daily
        PRIMARY KEY CLUSTERED (forecast_sk),

    CONSTRAINT FK_fact_forecast_daily_canonical_dish
        FOREIGN KEY (canonical_dish_id)
        REFERENCES dw.canonical_dish(canonical_dish_id),

    -- 基本資料合理性（你若有允許負值的情境再拿掉）
    CONSTRAINT CK_fact_forecast_daily_yhat_nonneg
        CHECK (yhat >= 0),

    CONSTRAINT CK_fact_forecast_daily_date_order
        CHECK (target_date >= forecast_origin_date),

    -- 同一個 run 內，避免同一筆被重複寫入
    -- 注意：SQL Server UNIQUE 允許多筆 NULL（run_id 可選的語意）
    CONSTRAINT UQ_fact_forecast_daily_run_grain
        UNIQUE (run_id, canonical_dish_id, forecast_origin_date, target_date, model_version)
);
GO

/* =========================================================
   Indexes（依你的常見查詢模式）
   ========================================================= */

-- 1) 查某個 origin_date 產出的整批預測（常見：每次 weekly forecast 讀回檢查/對帳）
CREATE INDEX IX_fact_forecast_daily_origin
ON dw.fact_forecast_daily (forecast_origin_date, model_version, canonical_dish_id, target_date);
GO

-- 2) 查某個 target_date 的所有菜預測（常見：BI / 供應備料看明天/後天）
CREATE INDEX IX_fact_forecast_daily_target
ON dw.fact_forecast_daily (target_date, model_version, canonical_dish_id, forecast_origin_date);
GO

-- 3) 查單一道菜的歷史預測（診斷/回溯）
CREATE INDEX IX_fact_forecast_daily_dish
ON dw.fact_forecast_daily (canonical_dish_id, model_version, forecast_origin_date, target_date);
GO
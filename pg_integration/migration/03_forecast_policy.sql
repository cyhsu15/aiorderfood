-- 依你目前需求：先讓路徑跑通
-- 目標：決定「LLM 查 yhat 要用哪個模型結果」
-- 設計：先做成「以 canonical_dish_id 為 scope」的 policy（可擴充成 global / shop / dish_price）
CREATE TABLE IF NOT EXISTS integration.forecast_policy
(
    policy_sk            BIGSERIAL PRIMARY KEY,

    -- scope：先以 canonical 為主（最直覺對齊你的 DW 分析實體）
    canonical_dish_id     BIGINT NOT NULL,

    -- policy 生效區間（方便你之後做版本切換、回測贏了才切）
    effective_from        DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to          DATE NULL,

    -- 選用哪個模型版本（要能對到 integration.fact_forecast_daily.model_version）
    chosen_model_version  VARCHAR(255) NOT NULL,

    -- 你之後回測會需要的欄位（先可不填或填假值）
    win_rate              NUMERIC(6,5) NULL,   -- 0~1，例如 0.73333
    metric_name           VARCHAR(64) NULL,    -- e.g. "winrate_mae"
    note                  TEXT NULL,

    -- ops / lineage
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_forecast_policy_effective_range
        CHECK (effective_to IS NULL OR effective_to >= effective_from),

    CONSTRAINT ck_forecast_policy_win_rate_range
        CHECK (win_rate IS NULL OR (win_rate >= 0 AND win_rate <= 1))
);

-- 同一 canonical 在同一生效起日，不允許多條 active policy（避免 LLM 不知道用哪條）
CREATE UNIQUE INDEX IF NOT EXISTS uq_forecast_policy_canonical_effective_from_active
    ON integration.forecast_policy (canonical_dish_id, effective_from)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS ix_forecast_policy_active_lookup
    ON integration.forecast_policy (canonical_dish_id, is_active, effective_from DESC);

-- updated_at 自動更新（沿用你前面已建立的 integration.trg_set_updated_at()）
-- 若你前面已建立該 function，直接用；沒有的話請先建立同名 function
DROP TRIGGER IF EXISTS set_updated_at_forecast_policy
ON integration.forecast_policy;

CREATE TRIGGER set_updated_at_forecast_policy
BEFORE UPDATE ON integration.forecast_policy
FOR EACH ROW
EXECUTE FUNCTION integration.trg_set_updated_at();
CREATE TABLE IF NOT EXISTS integration.bridge_canonical_to_oltp
(
    bridge_sk         BIGSERIAL PRIMARY KEY,

    -- DW analysis entity
    canonical_dish_id  BIGINT NOT NULL,

    -- OLTP sellable entity (建議用 dish_price_id 作為最終推薦/下單單位)
    dish_price_id      BIGINT NOT NULL,

    -- mapping lifecycle
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    valid_from         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to           TIMESTAMPTZ NULL,

    -- lineage / ops
    note               TEXT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 時間合理性（避免 valid_to 早於 valid_from）
    CONSTRAINT ck_bridge_c2o_valid_range
        CHECK (valid_to IS NULL OR valid_to >= valid_from),

    -- 避免同一對 mapping 在 active 狀態重複存在
    -- 只能有一筆 active 的 (canonical_dish_id, dish_price_id)
    CONSTRAINT uq_bridge_c2o_active_pair
        UNIQUE (canonical_dish_id, dish_price_id, is_active)
);

-- 常用查詢索引：LLM/服務查詢多會用 dish_price_id 或 canonical_dish_id
CREATE INDEX IF NOT EXISTS ix_bridge_c2o_canonical_active
    ON integration.bridge_canonical_to_oltp (canonical_dish_id)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS ix_bridge_c2o_dish_price_active
    ON integration.bridge_canonical_to_oltp (dish_price_id)
    WHERE is_active = TRUE;

-- updated_at 自動更新（需要 trigger）
CREATE OR REPLACE FUNCTION integration.trg_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_updated_at_bridge_canonical_to_oltp
ON integration.bridge_canonical_to_oltp;

CREATE TRIGGER set_updated_at_bridge_canonical_to_oltp
BEFORE UPDATE ON integration.bridge_canonical_to_oltp
FOR EACH ROW
EXECUTE FUNCTION integration.trg_set_updated_at();
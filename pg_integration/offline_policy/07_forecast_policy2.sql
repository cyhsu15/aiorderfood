CREATE TABLE IF NOT EXISTS integration.forecast_policy2 (
  canonical_dish_id       bigint PRIMARY KEY,
  chosen_model_version    text NOT NULL,
  effective_from          date NOT NULL DEFAULT CURRENT_DATE,
  effective_to            date NULL,
  is_active               boolean NOT NULL DEFAULT true,
  note                    text NULL,
  created_at              timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT ck_policy2_effective_range
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX IF NOT EXISTS ix_policy2_active_lookup
  ON integration.forecast_policy2 (is_active, effective_from DESC);

-- updated_at 自動更新（沿用你已存在的 integration.trg_set_updated_at()）
DROP TRIGGER IF EXISTS set_updated_at_forecast_policy2
ON integration.forecast_policy2;

CREATE TRIGGER set_updated_at_forecast_policy2
BEFORE UPDATE ON integration.forecast_policy2
FOR EACH ROW
EXECUTE FUNCTION integration.trg_set_updated_at();
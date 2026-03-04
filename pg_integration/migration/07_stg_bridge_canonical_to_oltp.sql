CREATE TABLE IF NOT EXISTS integration.stg_bridge_canonical_to_oltp
(
  canonical_dish_id BIGINT NOT NULL,
  dish_price_id     BIGINT NOT NULL,
  note              TEXT NULL
);
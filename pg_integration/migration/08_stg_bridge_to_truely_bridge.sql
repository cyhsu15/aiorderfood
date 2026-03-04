BEGIN;

WITH s_dedup AS (
  SELECT DISTINCT ON (canonical_dish_id, dish_price_id)
         canonical_dish_id, dish_price_id, note
  FROM integration.stg_bridge_canonical_to_oltp
  ORDER BY canonical_dish_id, dish_price_id, note NULLS LAST
)
INSERT INTO integration.bridge_canonical_to_oltp
(canonical_dish_id, dish_price_id, is_active, valid_from, valid_to, note)
SELECT canonical_dish_id, dish_price_id, TRUE, NOW(), NULL, note
FROM s_dedup
ON CONFLICT (canonical_dish_id, dish_price_id, is_active)
DO UPDATE SET
  note = EXCLUDED.note,
  valid_to = NULL,
  updated_at = NOW();

COMMIT;
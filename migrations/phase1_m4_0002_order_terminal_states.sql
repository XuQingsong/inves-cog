-- A019: terminal states only; scoped legacy reconciliation runs separately after acceptance.
BEGIN;
ALTER TABLE trading.orders DROP CONSTRAINT orders_status_check;
ALTER TABLE trading.orders ADD CONSTRAINT orders_status_check
 CHECK (status IN ('pending','filled','canceled','blocked','expired','superseded'));
COMMIT;

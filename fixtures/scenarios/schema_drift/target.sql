\i /fixtures/base/common.sql

ALTER TABLE payments DROP CONSTRAINT payments_payment_reference_key;
ALTER TABLE payments ALTER COLUMN method DROP NOT NULL;
ALTER TABLE orders ALTER COLUMN total_amount TYPE numeric(12, 4);
ALTER TABLE subscriptions ADD COLUMN source_system text;

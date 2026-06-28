\i /fixtures/base/common.sql

ALTER TABLE payments DROP CONSTRAINT payments_payment_reference_key;

UPDATE payments
SET payment_reference = 'PAY-100'
WHERE payment_id = 5001;

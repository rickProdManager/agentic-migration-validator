\i /fixtures/base/common.sql

ALTER TABLE orders DROP CONSTRAINT orders_customer_id_fkey;

UPDATE orders
SET customer_id = 999
WHERE order_id = 102;

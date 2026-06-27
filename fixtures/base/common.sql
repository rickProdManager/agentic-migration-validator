\set ON_ERROR_STOP on

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'validator_readonly') THEN
    EXECUTE 'CREATE ROLE validator_readonly LOGIN PASSWORD ''validator_readonly''';
  END IF;
END
$$;

DROP TABLE IF EXISTS subscriptions CASCADE;
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
  customer_id integer PRIMARY KEY,
  email text NOT NULL UNIQUE,
  full_name text NOT NULL,
  status text NOT NULL CHECK (status IN ('active', 'inactive')),
  created_at timestamptz NOT NULL,
  profile jsonb NOT NULL
);

CREATE TABLE orders (
  order_id integer PRIMARY KEY,
  order_number text NOT NULL UNIQUE,
  customer_id integer NOT NULL REFERENCES customers(customer_id),
  status text NOT NULL CHECK (status IN ('open', 'closed')),
  ordered_at timestamptz NOT NULL,
  closed_at timestamptz,
  total_amount numeric(10, 2) NOT NULL CHECK (total_amount >= 0)
);

CREATE TABLE order_items (
  order_item_id integer PRIMARY KEY,
  order_id integer NOT NULL REFERENCES orders(order_id),
  sku text NOT NULL,
  quantity integer NOT NULL CHECK (quantity > 0),
  unit_price numeric(10, 2) NOT NULL CHECK (unit_price >= 0),
  line_total numeric(10, 2) NOT NULL CHECK (line_total >= 0)
);

CREATE TABLE payments (
  payment_id integer PRIMARY KEY,
  order_id integer NOT NULL REFERENCES orders(order_id),
  payment_reference text NOT NULL UNIQUE,
  amount numeric(10, 2) NOT NULL CHECK (amount >= 0),
  paid_at timestamptz NOT NULL,
  method text NOT NULL
);

CREATE TABLE subscriptions (
  subscription_id integer PRIMARY KEY,
  customer_id integer NOT NULL REFERENCES customers(customer_id),
  plan_code text NOT NULL,
  active boolean NOT NULL,
  started_at timestamptz NOT NULL,
  ended_at timestamptz
);

INSERT INTO customers (customer_id, email, full_name, status, created_at, profile) VALUES
  (1, 'ada@example.com', 'Ada Lovelace', 'active', '2026-01-15T17:30:00Z', '{"tier":"enterprise","flags":["critical_path","beta"],"region":"us-west"}'),
  (2, 'grace@example.com', 'Grace Hopper', 'active', '2026-01-16T09:15:00Z', '{"region":"us-east","flags":["billing"],"tier":"growth"}'),
  (3, 'katherine@example.com', 'Katherine Johnson', 'inactive', '2026-01-17T11:00:00Z', '{"tier":"starter","flags":[],"region":"us-west"}');

INSERT INTO orders (order_id, order_number, customer_id, status, ordered_at, closed_at, total_amount) VALUES
  (100, 'ORD-100', 1, 'closed', '2026-02-01T10:00:00Z', '2026-02-01T10:30:00Z', 50.00),
  (101, 'ORD-101', 2, 'closed', '2026-02-02T14:00:00Z', '2026-02-02T14:45:00Z', 42.50),
  (102, 'ORD-102', 1, 'open', '2026-02-03T16:20:00Z', NULL, 120.00);

INSERT INTO order_items (order_item_id, order_id, sku, quantity, unit_price, line_total) VALUES
  (1000, 100, 'BOOK-001', 1, 30.00, 30.00),
  (1001, 100, 'SHIP-STD', 1, 20.00, 20.00),
  (1002, 101, 'KIT-042', 1, 42.50, 42.50),
  (1003, 102, 'SVC-120', 2, 60.00, 120.00);

INSERT INTO payments (payment_id, order_id, payment_reference, amount, paid_at, method) VALUES
  (5000, 100, 'PAY-100', 50.00, '2026-02-01T10:25:00Z', 'card'),
  (5001, 101, 'PAY-101', 42.50, '2026-02-02T14:40:00Z', 'ach');

INSERT INTO subscriptions (subscription_id, customer_id, plan_code, active, started_at, ended_at) VALUES
  (9000, 1, 'enterprise', true, '2026-01-15T18:00:00Z', NULL),
  (9001, 2, 'growth', true, '2026-01-16T10:00:00Z', NULL),
  (9002, 3, 'starter', false, '2026-01-17T12:00:00Z', '2026-02-15T12:00:00Z');

GRANT CONNECT ON DATABASE migration_validator TO validator_readonly;
GRANT USAGE ON SCHEMA public TO validator_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO validator_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO validator_readonly;

-- ══════════════════════════════════════════════════════════════════════════
--  AI Data Analyst — Sample PostgreSQL Schema
--  E-commerce analytics database for testing chat-to-SQL queries
-- ══════════════════════════════════════════════════════════════════════════

-- Drop schema and recreate cleanly
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;

-- ── Extensions ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ══════════════════════════════════════════════════════════════════════════
--  CUSTOMERS
-- ══════════════════════════════════════════════════════════════════════════
CREATE TABLE public.customers (
    customer_id   SERIAL PRIMARY KEY,
    first_name    VARCHAR(50)  NOT NULL,
    last_name     VARCHAR(50)  NOT NULL,
    email         VARCHAR(120) NOT NULL UNIQUE,
    city          VARCHAR(80),
    country       VARCHAR(60)  DEFAULT 'US',
    signup_date   DATE         NOT NULL DEFAULT CURRENT_DATE,
    tier          VARCHAR(20)  DEFAULT 'standard'   -- standard | premium | enterprise
                  CHECK (tier IN ('standard', 'premium', 'enterprise'))
);

-- ══════════════════════════════════════════════════════════════════════════
--  PRODUCTS
-- ══════════════════════════════════════════════════════════════════════════
CREATE TABLE public.categories (
    category_id   SERIAL PRIMARY KEY,
    name          VARCHAR(80) NOT NULL UNIQUE,
    description   TEXT
);

CREATE TABLE public.products (
    product_id    SERIAL PRIMARY KEY,
    name          VARCHAR(120) NOT NULL,
    category_id   INT REFERENCES public.categories(category_id),
    price         NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    cost          NUMERIC(10,2) NOT NULL CHECK (cost >= 0),
    stock         INT           DEFAULT 0,
    is_active     BOOLEAN       DEFAULT TRUE,
    created_at    TIMESTAMPTZ   DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════════════
--  ORDERS
-- ══════════════════════════════════════════════════════════════════════════
CREATE TABLE public.orders (
    order_id      SERIAL PRIMARY KEY,
    customer_id   INT  NOT NULL REFERENCES public.customers(customer_id),
    order_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    status        VARCHAR(20) DEFAULT 'pending'
                  CHECK (status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')),
    total_amount  NUMERIC(12,2),
    shipping_city VARCHAR(80),
    discount_pct  NUMERIC(5,2) DEFAULT 0
);

CREATE TABLE public.order_items (
    item_id       SERIAL PRIMARY KEY,
    order_id      INT           NOT NULL REFERENCES public.orders(order_id),
    product_id    INT           NOT NULL REFERENCES public.products(product_id),
    quantity      INT           NOT NULL CHECK (quantity > 0),
    unit_price    NUMERIC(10,2) NOT NULL,
    line_total    NUMERIC(12,2) GENERATED ALWAYS AS (quantity * unit_price) STORED
);

-- ══════════════════════════════════════════════════════════════════════════
--  MARKETING
-- ══════════════════════════════════════════════════════════════════════════
CREATE TABLE public.campaigns (
    campaign_id   SERIAL PRIMARY KEY,
    name          VARCHAR(120) NOT NULL,
    channel       VARCHAR(40)  -- email | social | ppc | seo | direct
                  CHECK (channel IN ('email','social','ppc','seo','direct')),
    start_date    DATE,
    end_date      DATE,
    budget        NUMERIC(12,2),
    spend         NUMERIC(12,2) DEFAULT 0
);

CREATE TABLE public.campaign_conversions (
    conversion_id  SERIAL PRIMARY KEY,
    campaign_id    INT  REFERENCES public.campaigns(campaign_id),
    customer_id    INT  REFERENCES public.customers(customer_id),
    order_id       INT  REFERENCES public.orders(order_id),
    converted_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════════════════════
--  SEED DATA
-- ══════════════════════════════════════════════════════════════════════════

-- Categories
INSERT INTO public.categories (name, description) VALUES
    ('Electronics',    'Consumer electronics and accessories'),
    ('Clothing',       'Apparel for all ages'),
    ('Home & Garden',  'Home decor and garden supplies'),
    ('Sports',         'Sports equipment and activewear'),
    ('Books',          'Physical and digital books');

-- Products
INSERT INTO public.products (name, category_id, price, cost, stock) VALUES
    ('Wireless Headphones Pro',   1, 149.99, 55.00, 250),
    ('Bluetooth Speaker Mini',    1,  49.99, 18.00, 400),
    ('4K Webcam',                 1,  89.99, 32.00, 150),
    ('USB-C Hub 7-in-1',          1,  39.99, 12.00, 600),
    ('Running Jacket',            2,  79.99, 28.00, 200),
    ('Yoga Pants',                2,  54.99, 19.00, 350),
    ('Cotton T-Shirt Pack x3',    2,  29.99,  9.00, 800),
    ('Bamboo Desk Organizer',     3,  34.99, 11.00, 120),
    ('Smart LED Strip 5m',        3,  24.99,  8.50, 450),
    ('Foam Yoga Mat',             4,  44.99, 15.00, 300),
    ('Resistance Bands Set',      4,  19.99,  6.00, 700),
    ('Python for Data Science',   5,  39.99, 10.00, 500),
    ('SQL Mastery Guide',         5,  34.99,  9.00, 400),
    ('Smart Watch Fitness Pro',   1, 199.99, 75.00,  90),
    ('Portable Charger 20000mAh', 1,  35.99, 13.00, 320);

-- Customers (100 sample customers)
INSERT INTO public.customers (first_name, last_name, email, city, country, signup_date, tier)
SELECT
    (ARRAY['Alice','Bob','Carol','David','Emma','Frank','Grace','Henry','Iris','Jack',
            'Karen','Liam','Mia','Noah','Olivia','Paul','Quinn','Rachel','Sam','Tina'])[1 + (i % 20)],
    (ARRAY['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis',
            'Wilson','Moore','Taylor','Anderson','Thomas','Jackson','White'])[1 + (i % 15)],
    'customer' || i || '@example.com',
    (ARRAY['New York','Los Angeles','Chicago','Houston','Phoenix','Philadelphia',
            'San Antonio','San Diego','Dallas','San Jose','Austin','Jacksonville'])[1 + (i % 12)],
    (ARRAY['US','US','US','US','CA','UK','AU','DE','FR'])[1 + (i % 9)],
    CURRENT_DATE - (random() * 730)::INT,
    (ARRAY['standard','standard','standard','premium','premium','enterprise'])[1 + (i % 6)]
FROM generate_series(1, 100) AS i;

-- Orders (500 orders over the past 2 years)
INSERT INTO public.orders (customer_id, order_date, status, shipping_city, discount_pct)
SELECT
    1 + (random() * 99)::INT,
    CURRENT_DATE - (random() * 730)::INT,
    (ARRAY['pending','confirmed','shipped','delivered','delivered','delivered','cancelled'])[1 + (random()*6)::INT],
    (ARRAY['New York','Los Angeles','Chicago','Houston','Phoenix','Philadelphia'])[1 + (random()*5)::INT],
    (ARRAY[0,0,0,5,10,15])[1 + (random()*5)::INT]
FROM generate_series(1, 500);

-- Order items (1–4 items per order)
INSERT INTO public.order_items (order_id, product_id, quantity, unit_price)
SELECT
    o.order_id,
    1 + (random() * 14)::INT,
    1 + (random() * 3)::INT,
    p.price
FROM public.orders o
CROSS JOIN LATERAL (
    SELECT generate_series(1, 1 + (random() * 3)::INT)
) AS items(n)
JOIN public.products p ON p.product_id = 1 + (random() * 14)::INT
LIMIT 1500;

-- Update order totals from line items
UPDATE public.orders o
SET total_amount = (
    SELECT COALESCE(SUM(line_total), 0) * (1 - o.discount_pct / 100.0)
    FROM public.order_items oi
    WHERE oi.order_id = o.order_id
);

-- Campaigns
INSERT INTO public.campaigns (name, channel, start_date, end_date, budget, spend) VALUES
    ('Spring Sale 2024',       'email',  '2024-03-01', '2024-03-31', 5000,  4800),
    ('Summer PPC Campaign',    'ppc',    '2024-06-01', '2024-08-31', 15000, 14200),
    ('Black Friday Push',      'email',  '2024-11-25', '2024-11-30', 8000,  7900),
    ('Social Awareness Q1',    'social', '2025-01-01', '2025-03-31', 6000,  3200),
    ('SEO Blog Content',       'seo',    '2024-01-01', '2024-12-31', 3000,  2900),
    ('Holiday Email Series',   'email',  '2024-12-01', '2024-12-31', 4000,  3850);

-- Campaign conversions (link some orders to campaigns)
INSERT INTO public.campaign_conversions (campaign_id, customer_id, order_id)
SELECT
    1 + (random() * 5)::INT,
    o.customer_id,
    o.order_id
FROM public.orders o
WHERE random() < 0.4   -- ~40% of orders attributed to a campaign
LIMIT 200;

-- ══════════════════════════════════════════════════════════════════════════
--  INDEXES for query performance
-- ══════════════════════════════════════════════════════════════════════════
CREATE INDEX idx_orders_customer    ON public.orders(customer_id);
CREATE INDEX idx_orders_date        ON public.orders(order_date);
CREATE INDEX idx_orders_status      ON public.orders(status);
CREATE INDEX idx_order_items_order  ON public.order_items(order_id);
CREATE INDEX idx_order_items_prod   ON public.order_items(product_id);
CREATE INDEX idx_products_category  ON public.products(category_id);
CREATE INDEX idx_conversions_camp   ON public.campaign_conversions(campaign_id);

-- Refresh pg_class row count statistics
ANALYZE;

-- ══════════════════════════════════════════════════════════════════════════
--  SAMPLE QUESTIONS TO TRY
-- ══════════════════════════════════════════════════════════════════════════
-- 1. "What are the top 5 products by total revenue?"
-- 2. "Show me monthly order counts and revenue for this year"
-- 3. "Which customers have spent the most? Show top 10"
-- 4. "What is the average order value by customer tier?"
-- 5. "Which product categories have the highest profit margin?"
-- 6. "How many orders were cancelled vs delivered last month?"
-- 7. "Which marketing channel drove the most conversions?"
-- 8. "Show me revenue trend by week for the past 3 months"
-- 9. "What cities have the most customers?"
-- 10. "Which products are low on stock (under 100 units)?"

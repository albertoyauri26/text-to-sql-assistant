-- Olist Brazilian E-Commerce Public Dataset (orders 2016-2018), loaded by text2sql/db.py.
-- SQLite keeps the comments inside each CREATE TABLE, so they reach the model as schema documentation.
-- All timestamps are TEXT in 'YYYY-MM-DD HH:MM:SS' format (use strftime / julianday).

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,       -- one per order: a returning buyer gets a new customer_id
    customer_unique_id TEXT NOT NULL,   -- the real person: use it to count distinct customers
    customer_zip_code_prefix TEXT,
    customer_city TEXT,
    customer_state TEXT                 -- 2-letter Brazilian state code, e.g. 'SP'
);

CREATE TABLE sellers (
    seller_id TEXT PRIMARY KEY,
    seller_zip_code_prefix TEXT,
    seller_city TEXT,
    seller_state TEXT
);

CREATE TABLE product_category_name_translation (
    product_category_name TEXT PRIMARY KEY,   -- Portuguese
    product_category_name_english TEXT
);

CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    product_category_name TEXT REFERENCES product_category_name_translation(product_category_name),  -- Portuguese, may be NULL
    product_name_lenght INTEGER,          -- (sic) column names misspelled in the original dataset
    product_description_lenght INTEGER,
    product_photos_qty INTEGER,
    product_weight_g INTEGER,
    product_length_cm INTEGER,
    product_height_cm INTEGER,
    product_width_cm INTEGER
);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    order_status TEXT,                    -- delivered, shipped, canceled, unavailable, invoiced, processing, created, approved
    order_purchase_timestamp TEXT,
    order_approved_at TEXT,
    order_delivered_carrier_date TEXT,
    order_delivered_customer_date TEXT,
    order_estimated_delivery_date TEXT
);

CREATE TABLE order_items (
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    order_item_id INTEGER NOT NULL,       -- 1, 2, 3... one row per unit bought in the order
    product_id TEXT NOT NULL REFERENCES products(product_id),
    seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
    shipping_limit_date TEXT,
    price REAL,                           -- item price in BRL; revenue = SUM(price)
    freight_value REAL,                   -- shipping cost of this item in BRL
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE order_payments (
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    payment_sequential INTEGER NOT NULL,  -- an order can be paid with several methods
    payment_type TEXT,                    -- credit_card, boleto, voucher, debit_card, not_defined
    payment_installments INTEGER,
    payment_value REAL,                   -- BRL, includes freight
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE order_reviews (
    review_id TEXT NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    review_score INTEGER,                 -- 1 (worst) to 5 (best)
    review_comment_title TEXT,            -- Portuguese free text, often NULL
    review_comment_message TEXT,
    review_creation_date TEXT,
    review_answer_timestamp TEXT,
    PRIMARY KEY (review_id, order_id)
);

-- Indexes on the join keys keep multi-table queries fast on ~100k-row tables.
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_items_product ON order_items(product_id);
CREATE INDEX idx_items_seller ON order_items(seller_id);
CREATE INDEX idx_reviews_order ON order_reviews(order_id);
CREATE INDEX idx_products_category ON products(product_category_name);

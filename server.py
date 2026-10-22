#!/usr/bin/env python3
"""
Shanks Shop Management - Multi-Tenant Backend API
Each business gets isolated data with an API key.
"""

import os
import json
import hashlib
import hmac
import base64
import time
import secrets
from datetime import datetime
from flask import Flask, request, jsonify, g, send_file
from functools import wraps

DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        raise ImportError('psycopg2-binary is required when using DATABASE_URL. Install it with: pip install psycopg2-binary')
else:
    import sqlite3

app = Flask(__name__)
app.config['DB_PATH'] = os.environ.get('DB_PATH', 'danzona_pos.db')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-set-a-real-secret-key')

# Roles that grant administrator rights inside a tenant.
ADMIN_ROLES = {'admin', 'administrator', 'owner', 'super_admin', 'superadmin'}

# Roles a store account can be created with.
STORE_ROLES = {'admin', 'manager', 'cashier', 'staff', 'pharmacist', 'supervisor', 'accountant'}

# How many logins a single tenant may be created with (owner + extra staff).
MAX_ACCOUNTS_PER_STORE = int(os.environ.get('MAX_ACCOUNTS_PER_STORE', '3'))

# Ensure database directory exists
_db_dir = os.path.dirname(app.config['DB_PATH'])
if _db_dir and not os.path.exists(_db_dir):
    os.makedirs(_db_dir, exist_ok=True)

# ---------- Database ----------

def get_db():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = RealDictCursor
        return conn
    else:
        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = sqlite3.connect(app.config['DB_PATH'])
            db.row_factory = sqlite3.Row
        return db

@app.teardown_appcontext
def close_db(exception):
    if USE_POSTGRES:
        return
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

IntegrityError = psycopg2.IntegrityError if USE_POSTGRES else sqlite3.IntegrityError

def id_col():
    return 'SERIAL PRIMARY KEY' if USE_POSTGRES else 'INTEGER PRIMARY KEY AUTOINCREMENT'


DEFAULT_PLANS = [
    {
        'key': 'trial',
        'name': 'Free Trial',
        'tagline': 'Everything you need to sell for the first 14 days.',
        'price_monthly': 0,
        'price_yearly': 0,
        'features': [
            '1 till and 1 staff account',
            'Up to 200 products with packaging types',
            'Barcode scanning and receipt printing',
            'Basic sales and profit reports',
            'Email support',
        ],
        'highlight': 0,
        'sort_order': 1,
    },
    {
        'key': 'standard',
        'name': 'Standard',
        'tagline': 'For a single pharmacy or retail store running every day.',
        'price_monthly': 12500,
        'price_yearly': 125000,
        'features': [
            'Up to 3 tills and 5 staff accounts',
            'Unlimited products, suppliers and customers',
            'Prescriptions, expiry and batch tracking',
            'Store accounts, split payments and VAT',
            'Expenses, stock counts and daily summary',
            'Priority support',
        ],
        'highlight': 1,
        'sort_order': 2,
    },
    {
        'key': 'pro',
        'name': 'Pro',
        'tagline': 'For multi-branch stores that need control and an audit trail.',
        'price_monthly': 35000,
        'price_yearly': 350000,
        'features': [
            'Unlimited tills, branches and staff',
            'Multi-branch stock and branch-wise reporting',
            'Full audit trail on every price, void and login',
            'Cashier closeout, shifts and Z-report',
            'Bank reconciliation and purchase orders',
            'API access and a dedicated account manager',
        ],
        'highlight': 0,
        'sort_order': 3,
    },
]

DEFAULT_TESTIMONIALS = [
    {
        'author_name': 'Chinedu Okafor',
        'author_role': 'Pharmacy Manager',
        'business': 'Lagos',
        'quote': 'SHANKS SHOP MANAGEMENT transformed our pharmacy operations. Inventory and prescriptions are now seamless, and the team loves how easy it is to use.',
        'rating': 5,
        'sort_order': 1,
    },
    {
        'author_name': 'Amaka Nwosu',
        'author_role': 'Retail Owner',
        'business': 'Abuja',
        'quote': 'The reporting and analytics help us make smarter decisions every single day. Support is fast and professional.',
        'rating': 5,
        'sort_order': 2,
    },
    {
        'author_name': 'Emeka Daniels',
        'author_role': 'Store Director',
        'business': 'Port Harcourt',
        'quote': 'Easy to use, reliable, and the support team is outstanding. We switched from three different tools and never looked back.',
        'rating': 5,
        'sort_order': 3,
    },
]

DEFAULT_CHANGELOG = [
    {
        'version': '2.4.0',
        'released_on': '2026-10-21',
        'title': 'Package-aware pricing and stock',
        'summary': 'Every cart line now takes its price from the package you sell, and stock moves in base units.',
        'items': [
            'Cart lines price from the selling price configured for the selected package type',
            'Stock is tracked and deducted in base units across sales, receiving and voids',
            'Split checkout between cash and a store account',
            'Audit log schema repaired with safe legacy column migration',
        ],
        'sort_order': 1,
    },
    {
        'version': '2.3.0',
        'released_on': '2026-09-30',
        'title': 'Shift manager and cashier closeout',
        'summary': 'Open and close shifts, track cash on hand and reconcile every till at the end of the day.',
        'items': [
            'Shift open and close with cash variance report',
            'Z-report per shift for the day book',
            'Suspense and expected-vs-counted cash tracking',
        ],
        'sort_order': 2,
    },
    {
        'version': '2.2.0',
        'released_on': '2026-09-05',
        'title': 'Expiry, batch and reorder alerts',
        'summary': 'See what is about to expire, which batch is moving and what needs reordering.',
        'items': [
            'Expiry countdown with FEFO batch tracking',
            'Reorder suggestions per product',
            'Expiry register export for compliance',
        ],
        'sort_order': 3,
    },
    {
        'version': '2.1.0',
        'released_on': '2026-08-12',
        'title': 'Store accounts and bank reconciliation',
        'summary': 'Let customers buy on credit, then match your deposits and card settlements to the bank statement.',
        'items': [
            'Customer credit balances and account payments',
            'Deposit and card settlement matching',
            'Unmatched transaction report',
        ],
        'sort_order': 4,
    },
]


def _hash_secret(password, salt=''):
    return hashlib.sha256((str(salt) + ':' + str(password)).encode('utf-8')).hexdigest()


def _seed_platform_admin(db):
    """Create or update the platform administrator used to create tenant stores.
    Credentials are hardcoded so the first login always works without env vars."""
    username = 'shedrack'
    password = 'admin123'
    salt = secrets.token_hex(8)
    hashed = _hash_secret(password, salt)
    try:
        existing = db.execute('SELECT id FROM platform_admins WHERE username = ?', (username,)).fetchone()
        if existing:
            db.execute(
                'UPDATE platform_admins SET password = ?, salt = ?, name = ?, role = ?, active = 1 WHERE username = ?',
                (hashed, salt, 'Platform Administrator', 'platform_admin', username)
            )
        else:
            db.execute(
                'INSERT INTO platform_admins (username, password, salt, name, role, active) VALUES (?, ?, ?, ?, ?, 1)',
                (username, hashed, salt, 'Platform Administrator', 'platform_admin')
            )
        db.commit()
        print('[platform] Platform administrator "%s" is ready. Password: admin123' % username)
    except Exception as e:
        print('[platform] Could not seed platform admin:', e)


def _seed_marketing_content(db):
    """Give the landing page sensible content the first time it is opened."""
    try:
        if db.execute('SELECT COUNT(*) AS c FROM plans').fetchone()['c'] == 0:
            for plan in DEFAULT_PLANS:
                db.execute(
                    'INSERT INTO plans (key, name, tagline, price_monthly, price_yearly, currency, features, highlight, sort_order, is_active)'
                    ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)',
                    (plan['key'], plan['name'], plan['tagline'], plan['price_monthly'], plan['price_yearly'],
                     'NGN', json.dumps(plan['features']), plan['highlight'], plan['sort_order'])
                )
        if db.execute('SELECT COUNT(*) AS c FROM testimonials').fetchone()['c'] == 0:
            for item in DEFAULT_TESTIMONIALS:
                db.execute(
                    'INSERT INTO testimonials (author_name, author_role, business, quote, rating, is_published, sort_order)'
                    ' VALUES (?, ?, ?, ?, ?, 1, ?)',
                    (item['author_name'], item['author_role'], item['business'], item['quote'], item['rating'], item['sort_order'])
                )
        if db.execute('SELECT COUNT(*) AS c FROM changelog').fetchone()['c'] == 0:
            for item in DEFAULT_CHANGELOG:
                db.execute(
                    'INSERT INTO changelog (version, released_on, title, summary, items, is_published, sort_order)'
                    ' VALUES (?, ?, ?, ?, ?, 1, ?)',
                    (item['version'], item['released_on'], item['title'], item['summary'],
                     json.dumps(item['items']), item['sort_order'])
                )
    except Exception:
        pass


def init_db():
    db = get_db()
    # Pharmacies (tenants)
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS pharmacies (
            id {id_col()},
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            email TEXT,
            api_key TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    for _col, _ddl in (
        ('business_type', "TEXT DEFAULT 'pharmacy'"),
        ('business_modules', 'TEXT'),
        ('status', "TEXT DEFAULT 'active'"),
        ('setup_token', 'TEXT'),
        ('pending_accounts', 'TEXT'),
    ):
        try:
            db.execute(f'ALTER TABLE pharmacies ADD COLUMN {_col} {_ddl}')
        except Exception:
            pass
    try:
        db.execute("UPDATE pharmacies SET business_type = 'pharmacy' WHERE business_type IS NULL OR business_type = ''")
    except Exception:
        pass
    try:
        db.execute("UPDATE pharmacies SET status = 'active' WHERE status IS NULL OR status = ''")
    except Exception:
        pass
    # Users (staff per pharmacy)
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS users (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            role TEXT DEFAULT 'staff',
            store TEXT DEFAULT 'main',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pharmacy_id, username)
        )
    ''')
    # Admin management columns on users
    for _col, _ddl in (
        ('active', 'INTEGER DEFAULT 1'),
        ('email', 'TEXT'),
        ('phone', 'TEXT'),
        ('last_login', 'TEXT'),
        ('page_access', 'TEXT'),
    ):
        try:
            db.execute(f'ALTER TABLE users ADD COLUMN {_col} {_ddl}')
        except Exception:
            pass

    # Page visibility / ordering per pharmacy (admin managed)
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS page_settings (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            page_key TEXT NOT NULL,
            label TEXT,
            group_name TEXT,
            icon TEXT,
            enabled INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pharmacy_id, page_key)
        )
    ''')

    db.execute(f'''
        CREATE TABLE IF NOT EXISTS categories (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(pharmacy_id, name)
        )
    ''')

    # Products per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS products (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            sku TEXT NOT NULL,
            category_id INTEGER,
            category_name TEXT DEFAULT 'Uncategorized',
            description TEXT,
            price REAL DEFAULT 0,
            cost_price REAL DEFAULT 0,
            stock REAL DEFAULT 0,
            reorder_level REAL DEFAULT 10,
            expiry TEXT,
            prices TEXT,
            default_pkg_sale TEXT DEFAULT 'pkt',
            default_pkg_receive TEXT DEFAULT 'pkt',
            packaging_types TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pharmacy_id, sku)
        )
    ''')
    try:
        db.execute('ALTER TABLE products ADD COLUMN packaging_types TEXT')
    except Exception:
        pass
    # Sales per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS sales (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            customer_id INTEGER,
            customer_name TEXT,
            items TEXT,
            subtotal REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            total REAL DEFAULT 0,
            payment_method TEXT DEFAULT 'cash',
            amount_tendered REAL DEFAULT 0,
            account_amount REAL DEFAULT 0,
            change REAL DEFAULT 0,
            cashier TEXT,
            notes TEXT
        )
    ''')
    # Customers per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS customers (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            cust_id TEXT,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            balance REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        db.execute('ALTER TABLE customers ADD COLUMN balance REAL DEFAULT 0')
    except Exception:
        pass
    try:
        db.execute('ALTER TABLE sales ADD COLUMN status TEXT DEFAULT \'completed\'')
    except Exception:
        pass
    try:
        db.execute('ALTER TABLE sales ADD COLUMN account_amount REAL DEFAULT 0')
    except Exception:
        pass
    # Audit log per pharmacy. An older database may still carry the legacy
    # columns (entity, user), so the table is created with the current schema
    # and migrated in place.
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS audit_log (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            user_id INTEGER,
            user_name TEXT,
            action TEXT,
            entity_type TEXT,
            entity_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        _audit_columns = {row['name'] for row in db.execute('PRAGMA table_info(audit_log)').fetchall()}
    except Exception:
        _audit_columns = set()
    for _col, _ddl in (
        ('user_id', 'INTEGER'),
        ('user_name', 'TEXT'),
        ('entity_type', 'TEXT'),
        ('ip_address', 'TEXT'),
    ):
        if _col not in _audit_columns:
            try:
                db.execute(f'ALTER TABLE audit_log ADD COLUMN {_col} {_ddl}')
            except Exception:
                pass
    try:
        if 'entity' in _audit_columns:
            db.execute('UPDATE audit_log SET entity_type = entity WHERE entity_type IS NULL AND entity IS NOT NULL')
        if 'user' in _audit_columns:
            db.execute('UPDATE audit_log SET user_name = user WHERE user_name IS NULL AND user IS NOT NULL')
    except Exception:
        pass
    # Employees per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS employees (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            emp_id TEXT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            position TEXT,
            department TEXT,
            status TEXT DEFAULT 'active',
            salary REAL DEFAULT 0,
            hire_date TEXT,
            employment_type TEXT DEFAULT 'full-time',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Inventory per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS inventory (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            product_id INTEGER,
            quantity REAL DEFAULT 0,
            location TEXT,
            batch_number TEXT,
            expiry_date TEXT,
            cost_price REAL,
            selling_price REAL,
            last_restocked TEXT,
            reorder_level REAL DEFAULT 10
        )
    ''')
    # Expenses per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS expenses (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            category TEXT,
            description TEXT,
            amount REAL DEFAULT 0,
            receipt_number TEXT,
            created_by TEXT
        )
    ''')
    # Receiving history per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS receiving (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            date TEXT,
            ref TEXT,
            supplier_id INTEGER,
            supplier_name TEXT,
            items TEXT NOT NULL DEFAULT '[]',
            total REAL DEFAULT 0,
            notes TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Payments / Accounts per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS payments (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            paymentId TEXT,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            customer INTEGER,
            supplier INTEGER,
            invoice TEXT,
            amount REAL DEFAULT 0,
            method TEXT,
            status TEXT DEFAULT 'paid',
            notes TEXT,
            created_by TEXT
        )
    ''')
    # Locations per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS locations (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            manager TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')
    # Appointments per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS appointments (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            customer_name TEXT,
            customer_phone TEXT,
            date TEXT,
            time TEXT,
            service TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Gift cards per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS giftcards (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            code TEXT UNIQUE NOT NULL,
            amount REAL DEFAULT 0,
            balance REAL DEFAULT 0,
            customer_name TEXT,
            customer_phone TEXT,
            expiry_date TEXT,
            status TEXT DEFAULT 'active',
            issued_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Messages per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS messages (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            from_user TEXT,
            to_user TEXT,
            subject TEXT,
            body TEXT,
            status TEXT DEFAULT 'unread',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Deliveries per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS deliveries (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            sale_id INTEGER,
            customer_name TEXT,
            address TEXT,
            phone TEXT,
            status TEXT DEFAULT 'pending',
            delivery_date TEXT,
            driver TEXT,
            notes TEXT
        )
    ''')
    # Invoices per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS invoices (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            invoice_number TEXT UNIQUE NOT NULL,
            customer_name TEXT,
            customer_phone TEXT,
            customer_email TEXT,
            items TEXT,
            subtotal REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            total REAL DEFAULT 0,
            status TEXT DEFAULT 'unpaid',
            due_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Suppliers per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS suppliers (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            contact_person TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Store config per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS store_config (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL UNIQUE,
            config TEXT NOT NULL DEFAULT '{{}}',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Roles per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS roles (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            permissions TEXT NOT NULL DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pharmacy_id, name)
        )
    ''')


    # Shifts per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS shifts (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            cashier_id INTEGER,
            cashier_name TEXT,
            opening_float REAL DEFAULT 0,
            total_sales REAL DEFAULT 0,
            total_cash REAL DEFAULT 0,
            total_card REAL DEFAULT 0,
            total_store_account REAL DEFAULT 0,
            total_pos REAL DEFAULT 0,
            total_gift_card REAL DEFAULT 0,
            expected_cash REAL DEFAULT 0,
            actual_cash REAL DEFAULT 0,
            variance REAL DEFAULT 0,
            status TEXT DEFAULT 'open',
            start_time TEXT DEFAULT CURRENT_TIMESTAMP,
            end_time TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Purchase orders per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            supplier_id INTEGER,
            supplier_name TEXT,
            po_number TEXT,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            items TEXT,
            subtotal REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            total REAL DEFAULT 0,
            status TEXT DEFAULT 'draft',
            notes TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Bank reconciliation records per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS bank_records (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            bank_name TEXT,
            account_number TEXT,
            transaction_ref TEXT,
            amount REAL DEFAULT 0,
            type TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Stock transfers per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS stock_transfers (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            from_location_id INTEGER,
            to_location_id INTEGER,
            from_location_name TEXT,
            to_location_name TEXT,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            items TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Tax rules per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS tax_rules (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            rate REAL DEFAULT 0,
            type TEXT DEFAULT 'percentage',
            applicable_categories TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Expiry batches per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS expiry_batches (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT,
            batch_number TEXT,
            expiry_date TEXT,
            quantity REAL DEFAULT 0,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Stock counts (stock take sheets) per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS stock_counts (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            reference TEXT,
            location TEXT,
            status TEXT DEFAULT 'draft',
            counted_by TEXT,
            notes TEXT,
            total_items INTEGER DEFAULT 0,
            counted_items INTEGER DEFAULT 0,
            total_variance REAL DEFAULT 0,
            value_variance REAL DEFAULT 0,
            applied INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        )
    ''')
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS stock_count_items (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            count_id INTEGER,
            product_id INTEGER,
            product_name TEXT,
            sku TEXT,
            location TEXT,
            batch_number TEXT,
            expiry_date TEXT,
            system_qty REAL DEFAULT 0,
            counted_qty REAL,
            variance REAL DEFAULT 0,
            unit_cost REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Prescriptions per pharmacy
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS prescriptions (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            prescription_number TEXT,
            patient_name TEXT,
            patient_age INTEGER,
            patient_gender TEXT,
            doctor_name TEXT,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            items TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Audit log table is created and migrated above.


    # Branches (enhanced locations with isolation)
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS branches (
            id {id_col()},
            pharmacy_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            manager TEXT,
            timezone TEXT DEFAULT 'Africa/Lagos',
            currency TEXT DEFAULT 'NGN',
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ---------- Marketing site content (public landing page) ----------

    # Pricing plans shown on the landing page
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS plans (
            id {id_col()},
            key TEXT UNIQUE,
            name TEXT NOT NULL,
            tagline TEXT,
            price_monthly REAL DEFAULT 0,
            price_yearly REAL DEFAULT 0,
            currency TEXT DEFAULT 'NGN',
            features TEXT,
            highlight INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Leads captured from the landing page (newsletter / demo requests)
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS leads (
            id {id_col()},
            email TEXT NOT NULL,
            name TEXT,
            pharmacy TEXT,
            message TEXT,
            source TEXT DEFAULT 'landing',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Customer testimonials published on the landing page
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS testimonials (
            id {id_col()},
            author_name TEXT NOT NULL,
            author_role TEXT,
            business TEXT,
            quote TEXT,
            rating INTEGER DEFAULT 5,
            is_published INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Release notes shown as "Latest updates" on the landing page
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS changelog (
            id {id_col()},
            version TEXT NOT NULL,
            released_on TEXT,
            title TEXT,
            summary TEXT,
            items TEXT,
            is_published INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Platform administrators: the accounts allowed to create and manage
    # tenant stores. They are separate from every tenant's own admin account.
    db.execute(f'''
        CREATE TABLE IF NOT EXISTS platform_admins (
            id {id_col()},
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            salt TEXT,
            name TEXT,
            role TEXT DEFAULT 'platform_admin',
            active INTEGER DEFAULT 1,
            last_login TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    _seed_platform_admin(db)
    _seed_marketing_content(db)

    db.commit()

# ---------- Auth Middleware ----------

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        db = get_db()
        pharmacy = db.execute('SELECT * FROM pharmacies WHERE api_key = ?', (api_key,)).fetchone()
        if not pharmacy:
            return jsonify({'error': 'Invalid API key'}), 401
        g.pharmacy_id = pharmacy['id']
        g.pharmacy = dict(pharmacy)
        return f(*args, **kwargs)
    return decorated

def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            username = request.headers.get('X-Username', '')
            db = get_db()
            user = db.execute(
                'SELECT * FROM users WHERE pharmacy_id = ? AND username = ?',
                (g.pharmacy_id, username)
            ).fetchone()
            if not user:
                return jsonify({'error': 'User not found'}), 401
            if roles and user['role'] not in roles:
                return jsonify({'error': 'Access denied'}), 403
            g.user = dict(user)
            return f(*args, **kwargs)
        return decorated
    return decorator

SUPER_ADMIN_KEY = os.environ.get('SUPER_ADMIN_API_KEY', 'shedrack')

PLATFORM_TOKEN_TTL = int(os.environ.get('PLATFORM_TOKEN_TTL', str(8 * 60 * 60)))


def _secret_key():
    return str(app.config.get('SECRET_KEY') or 'change-me-set-a-real-secret-key')


def _platform_token_for(admin):
    """Signed, expiring token that proves a platform administrator is signed in."""
    payload = json.dumps({
        'id': admin['id'],
        'u': admin['username'],
        'exp': int(time.time()) + PLATFORM_TOKEN_TTL
    })
    raw = base64.urlsafe_b64encode(payload.encode('utf-8')).decode('ascii').rstrip('=')
    signature = hmac.new(_secret_key().encode('utf-8'), raw.encode('ascii'), hashlib.sha256).hexdigest()
    return raw + '.' + signature


def _platform_admin_from_token(token):
    if not token or '.' not in token:
        return None
    raw, signature = token.rsplit('.', 1)
    expected = hmac.new(_secret_key().encode('utf-8'), raw.encode('ascii'), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        padding = '=' * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(raw + padding).decode('utf-8'))
    except Exception:
        return None
    if int(payload.get('exp', 0)) < int(time.time()):
        return None
    try:
        admin = get_db().execute('SELECT * FROM platform_admins WHERE id = ?', (payload.get('id'),)).fetchone()
    except Exception:
        return None
    if not admin:
        return None
    if 'active' in admin.keys() and not admin['active']:
        return None
    return dict(admin)


def _request_platform_token():
    token = request.headers.get('X-Platform-Token') or request.args.get('platform_token', '')
    if not token:
        data = request.get_json(silent=True) or {}
        token = data.get('platform_token', '') or ''
    return str(token or '').strip()


def require_platform_admin(f):
    """Only a signed-in platform administrator may create or manage tenant stores."""
    @wraps(f)
    def decorated(*args, **kwargs):
        admin = _platform_admin_from_token(_request_platform_token())
        if not admin:
            return jsonify({'error': 'Platform administrator sign-in required'}), 401
        g.platform_admin = admin
        return f(*args, **kwargs)
    return decorated


def _is_user_active(user):
    try:
        if 'active' not in user.keys():
            return True
        value = user['active']
        return value is not None and bool(value)
    except Exception:
        return True

def _touch_last_login(user_id):
    try:
        db = get_db()
        db.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), user_id))
        db.commit()
    except Exception:
        pass


def require_super_admin(f):
    """Platform administrator token, or the legacy super admin key for automation."""
    @wraps(f)
    def decorated(*args, **kwargs):
        admin = _platform_admin_from_token(_request_platform_token())
        if admin:
            g.platform_admin = admin
            return f(*args, **kwargs)
        key = request.headers.get('X-Super-Admin-Key') or request.args.get('super_admin_key', '')
        if not SUPER_ADMIN_KEY or key != SUPER_ADMIN_KEY:
            return jsonify({'error': 'Super admin access required'}), 401
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Only administrators of the current tenant may call the route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        username = request.headers.get('X-Username', '')
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE pharmacy_id = ? AND username = ?',
            (g.pharmacy_id, username)
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 401
        if 'active' in user.keys() and not user['active']:
            return jsonify({'error': 'This account has been disabled'}), 403
        if str(user['role'] or '').strip().lower() not in ADMIN_ROLES:
            return jsonify({'error': 'Administrator access required'}), 403
        g.user = dict(user)
        return f(*args, **kwargs)
    return decorated

# ---------- Subscription Routes ----------

@app.route('/api/auth/platform-login', methods=['POST'])
def platform_login():
    """Sign in the platform administrator: the account that creates tenant stores."""
    data = request.get_json(silent=True) or {}
    username = str(data.get('username') or '').strip().lower()
    password = str(data.get('password') or '')
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    db = get_db()
    admin = db.execute('SELECT * FROM platform_admins WHERE username = ?', (username,)).fetchone()
    if not admin or not _is_user_active(admin):
        return jsonify({'error': 'Invalid platform administrator credentials'}), 401
    salt = admin['salt'] if 'salt' in admin.keys() else ''
    if not hmac.compare_digest(admin['password'] or '', _hash_secret(password, salt)):
        return jsonify({'error': 'Invalid platform administrator credentials'}), 401
    db.execute('UPDATE platform_admins SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), admin['id']))
    db.commit()
    return jsonify({
        'token': _platform_token_for(admin),
        'user': {
            'id': admin['id'],
            'username': admin['username'],
            'name': admin['name'] or admin['username'],
            'role': admin['role'] or 'platform_admin'
        }
    }), 200


@app.route('/api/auth/platform-logout', methods=['POST'])
@require_platform_admin
def platform_logout():
    return jsonify({'ok': True})


@app.route('/api/auth/register', methods=['POST'])
@require_platform_admin
def register_pharmacy():
    """Create a tenant store. Only a platform administrator can do this.

    Step 1 of 2: the store details are saved as a *pending* store and a setup
    token is handed back. No login exists yet, so the store cannot be used yet.
    The store administrator sets their own login on the setup page
    (``/api/auth/complete-setup``) and only then is the account activated.
    """
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    address = data.get('address', '')
    phone = data.get('phone', '')
    email = data.get('email', '')
    business_type = str(data.get('business_type', 'pharmacy') or 'pharmacy').strip().lower()

    if not name:
        return jsonify({'error': 'Business name is required'}), 400
    if business_type not in BUSINESS_TYPES:
        business_type = 'other'

    # Staff logins prepared by the platform administrator. They are created
    # together with the administrator login when the setup is completed.
    pending_accounts = []
    extra_accounts = data.get('accounts', [])
    if not isinstance(extra_accounts, list):
        extra_accounts = []
    seen = set()
    for entry in extra_accounts[:MAX_ACCOUNTS_PER_STORE - 1]:
        if not isinstance(entry, dict):
            continue
        username = str(entry.get('username') or '').strip()
        password = str(entry.get('password') or '')
        if not username and not password:
            continue  # empty row, ignore it
        if not username or not password:
            return jsonify({'error': 'Every account needs a username and a password'}), 400
        if username.lower() in seen:
            return jsonify({'error': 'Duplicate username "' + username + '" for this store'}), 400
        if len(password) < 4:
            return jsonify({'error': 'Password for "' + username + '" must be at least 4 characters'}), 400
        seen.add(username.lower())
        role = str(entry.get('role') or 'staff').strip().lower()
        pending_accounts.append({
            'username': username,
            'password': password,
            'name': str(entry.get('name') or username).strip(),
            'role': role if role in STORE_ROLES else 'staff'
        })

    api_key = secrets.token_urlsafe(32)
    setup_token = secrets.token_urlsafe(24)
    try:
        db = get_db()
        cursor = db.execute(
            'INSERT INTO pharmacies (name, address, phone, email, api_key, business_type, status, setup_token, pending_accounts) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (name, address, phone, email, api_key, business_type, 'pending', setup_token,
             json.dumps(pending_accounts))
        )
        pharmacy_id = cursor.lastrowid
        db.commit()
        return jsonify({
            'pharmacy_id': pharmacy_id,
            'name': name,
            'business_type': business_type,
            'business_label': BUSINESS_TYPES[business_type]['label'],
            'status': 'pending',
            'setup_token': setup_token,
            'setup_path': '/admin-setup.html?token=' + setup_token,
            'created_by': (g.platform_admin or {}).get('username', ''),
            'staff_accounts': len(pending_accounts),
            'account_count': 1 + len(pending_accounts),
            'message': 'Store created. The store administrator now sets their login to activate the account.'
        }), 201
    except IntegrityError:
        db.rollback()
        return jsonify({'error': 'Could not create the store, please try again'}), 400

@app.route('/api/auth/complete-setup', methods=['POST'])
def complete_store_setup():
    """Step 2 of the store sign-up: the administrator sets their own login.

    The store only becomes usable here: the administrator account and any
    staff logins prepared by the platform administrator are created, and the
    store is switched to active. The setup token is single use.
    """
    data = request.get_json(silent=True) or {}
    setup_token = str(data.get('setup_token') or data.get('token') or '').strip()
    admin_username = str(data.get('admin_username') or data.get('username') or '').strip()
    admin_password = str(data.get('admin_password') or data.get('password') or '')
    admin_name = str(data.get('admin_name') or admin_username).strip()

    if not setup_token:
        return jsonify({'error': 'Setup link is missing. Please create the store account again.'}), 400
    if not admin_username:
        return jsonify({'error': 'Administrator username is required'}), 400
    if len(admin_password) < 4:
        return jsonify({'error': 'Administrator password must be at least 4 characters'}), 400

    db = get_db()
    pharmacy = db.execute('SELECT * FROM pharmacies WHERE setup_token = ?', (setup_token,)).fetchone()
    if not pharmacy:
        return jsonify({'error': 'This setup link is not valid. Please create the store account again.'}), 404
    if (pharmacy['status'] or 'active') != 'pending':
        return jsonify({'error': 'This store account has already been set up. Please sign in.'}), 400

    accounts = [{
        'username': admin_username,
        'password': admin_password,
        'name': admin_name or admin_username,
        'role': 'admin'
    }]
    try:
        pending_accounts = json.loads(pharmacy['pending_accounts'] or '[]')
    except Exception:
        pending_accounts = []
    if not isinstance(pending_accounts, list):
        pending_accounts = []
    seen = {admin_username.lower()}
    for entry in pending_accounts:
        if not isinstance(entry, dict):
            continue
        username = str(entry.get('username') or '').strip()
        password = str(entry.get('password') or '')
        if not username or not password:
            continue
        if username.lower() in seen:
            return jsonify({'error': 'Username "' + username + '" is already used for this store'}), 400
        seen.add(username.lower())
        accounts.append({
            'username': username,
            'password': password,
            'name': str(entry.get('name') or username).strip(),
            'role': str(entry.get('role') or 'staff').strip().lower()
        })

    # The store sign-in screen looks a user up by username and password, so the
    # same pair must not already belong to a different store.
    for account in accounts:
        clash = db.execute(
            'SELECT pharmacy_id FROM users WHERE username = ? AND password = ? LIMIT 1',
            (account['username'], account['password'])
        ).fetchone()
        if clash:
            return jsonify({
                'error': 'The login "%s" already belongs to another store. Use a different '
                         'username or password.' % account['username']
            }), 400

    try:
        for account in accounts:
            db.execute(
                'INSERT INTO users (pharmacy_id, username, password, name, role, store) VALUES (?, ?, ?, ?, ?, ?)',
                (pharmacy['id'], account['username'], account['password'], account['name'],
                 account['role'], 'main')
            )
        db.execute(
            "UPDATE pharmacies SET status = 'active', setup_token = NULL, pending_accounts = NULL WHERE id = ?",
            (pharmacy['id'],)
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return jsonify({'error': 'One of the usernames already exists, please try again'}), 400
    except Exception as e:
        db.rollback()
        app.logger.warning('store setup failed: %s' % e)
        return jsonify({'error': 'Could not finish the setup, please try again'}), 500

    user = db.execute(
        'SELECT * FROM users WHERE pharmacy_id = ? AND username = ? LIMIT 1',
        (pharmacy['id'], admin_username)
    ).fetchone()
    _touch_last_login(user['id'])
    return jsonify({
        'user': {
            'id': user['id'],
            'username': user['username'],
            'name': user['name'],
            'role': user['role'],
            'store': user['store']
        },
        'pharmacy': _business_payload(db, pharmacy['id'], pharmacy),
        'account_count': len(accounts),
        'message': 'Store account created. Welcome to SHANKS SHOP MANAGEMENT.'
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    api_key = data.get('api_key', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    db = get_db()
    
    # If API key provided, look up pharmacy first
    if api_key:
        pharmacy = db.execute('SELECT * FROM pharmacies WHERE api_key = ?', (api_key,)).fetchone()
        if not pharmacy:
            return jsonify({'error': 'Invalid API key'}), 401
        user = db.execute(
            'SELECT * FROM users WHERE pharmacy_id = ? AND username = ? AND password = ?',
            (pharmacy['id'], username, password)
        ).fetchone()
        if not user:
            return jsonify({'error': 'Invalid username or password'}), 401
        if not _is_user_active(user):
            return jsonify({'error': 'This account has been disabled. Contact your administrator.'}), 403
        _touch_last_login(user['id'])
        return jsonify({
            'user': {
                'id': user['id'],
                'username': user['username'],
                'name': user['name'],
                'role': user['role'],
                'store': user['store']
            },
            'pharmacy': _business_payload(db, pharmacy['id'], pharmacy)
        }), 200
    else:
        users = db.execute(
            'SELECT u.*, p.api_key, p.name as pharmacy_name, p.address, p.phone, p.email, p.business_type, p.business_modules FROM users u JOIN pharmacies p ON u.pharmacy_id = p.id WHERE u.username = ? AND u.password = ?',
            (username, password)
        ).fetchall()
    if not users:
        return jsonify({'error': 'Invalid username or password'}), 401

    user = users[0]
    if not _is_user_active(user):
        return jsonify({'error': 'This account has been disabled. Contact your administrator.'}), 403
    _touch_last_login(user['id'])
    return jsonify({
        'user': {
            'id': user['id'],
            'username': user['username'],
            'name': user['name'],
            'role': user['role'],
            'store': user['store']
        },
        'pharmacy': _business_payload(db, user['pharmacy_id'], {
            'id': user['pharmacy_id'],
            'name': user['pharmacy_name'],
            'api_key': user['api_key'],
            'address': user['address'],
            'phone': user['phone'],
            'email': user['email'],
            'business_type': user['business_type'],
            'business_modules': user['business_modules']
        })
    }), 200
@app.route('/api/auth/staff-login', methods=['POST'])
def staff_login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    db = get_db()
    users = db.execute(
        'SELECT u.*, p.api_key, p.name as pharmacy_name, p.address, p.phone, p.email, p.business_type, p.business_modules FROM users u JOIN pharmacies p ON u.pharmacy_id = p.id WHERE u.username = ? AND u.password = ?',
        (username, password)
    ).fetchall()
    if not users:
        return jsonify({'error': 'Invalid username or password'}), 401

    user = users[0]
    if not _is_user_active(user):
        return jsonify({'error': 'This account has been disabled. Contact your administrator.'}), 403
    _touch_last_login(user['id'])
    return jsonify({
        'user': {
            'id': user['id'],
            'username': user['username'],
            'name': user['name'],
            'role': user['role'],
            'store': user['store']
        },
        'pharmacy': _business_payload(db, user['pharmacy_id'], {
            'id': user['pharmacy_id'],
            'name': user['pharmacy_name'],
            'api_key': user['api_key'],
            'address': user['address'],
            'phone': user['phone'],
            'email': user['email'],
            'business_type': user['business_type'],
            'business_modules': user['business_modules']
        })
    }), 200

@app.route('/api/auth/admin-setup-login', methods=['POST'])
def admin_setup_login():
    """Sign in the store's own administrator. The platform administrator that
    created the store is a separate account and cannot sign in here."""
    data = request.get_json(silent=True) or {}
    api_key = str(data.get('api_key') or '').strip()
    admin_username = str(data.get('admin_username') or data.get('master_username') or data.get('username') or '').strip()
    admin_password = str(data.get('admin_password') or data.get('master_password') or data.get('password') or '')

    if not api_key:
        return jsonify({'error': 'API key is required'}), 400
    if not admin_username or not admin_password:
        return jsonify({'error': 'Administrator username and password are required'}), 400

    db = get_db()
    pharmacy = db.execute('SELECT * FROM pharmacies WHERE api_key = ?', (api_key,)).fetchone()
    if not pharmacy:
        return jsonify({'error': 'Invalid business'}), 404

    user = db.execute(
        'SELECT * FROM users WHERE pharmacy_id = ? AND username = ?',
        (pharmacy['id'], admin_username)
    ).fetchone()
    if not user or user['password'] != admin_password:
        return jsonify({'error': 'Invalid administrator credentials for this store'}), 401
    if str(user['role'] or '').strip().lower() not in ADMIN_ROLES:
        return jsonify({'error': 'This account is not the store administrator'}), 403
    if not _is_user_active(user):
        return jsonify({'error': 'This account has been disabled. Contact your administrator.'}), 403
    _touch_last_login(user['id'])

    return jsonify({
        'user': {
            'id': user['id'],
            'username': user['username'],
            'name': user['name'],
            'role': user['role'],
            'store': user['store']
        },
        'pharmacy': _business_payload(db, pharmacy['id'], pharmacy)
    }), 200

@app.route('/api/auth/check', methods=['GET'])
@require_auth
def check_auth():
    db = get_db()
    return jsonify({
        'pharmacy_id': g.pharmacy_id,
        'name': g.pharmacy['name']
    }), 200

@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        db = get_db()
        db.execute('SELECT 1').fetchone()
        db_status = 'ok'
    except Exception as e:
        db_status = f'error: {str(e)}'
    return jsonify({
        'status': 'ok',
        'database': db_status,
        'db_path': app.config['DB_PATH']
    }), 200

# ---------- Branch Routes ----------

@app.route('/api/branches', methods=['GET'])
@require_auth
def get_branches():
    db = get_db()
    rows = db.execute('SELECT * FROM branches WHERE pharmacy_id = ? ORDER BY name ASC', (g.pharmacy_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/branches', methods=['POST'])
@require_auth
def create_branch():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('branches', data)

@app.route('/api/branches/<int:bid>', methods=['PUT'])
@require_auth
def update_branch(bid):
    data = request.get_json()
    return table_update('branches', bid, data)

@app.route('/api/branches/<int:bid>', methods=['DELETE'])
@require_auth
def delete_branch(bid):
    return table_delete('branches', bid)

# ---------- Super Admin Routes ----------

@app.route('/api/admin/tenants', methods=['GET'])
@require_super_admin
def list_tenants():
    db = get_db()
    rows = db.execute('''
        SELECT p.*,
            (SELECT COUNT(*) FROM users u WHERE u.pharmacy_id = p.id) as user_count,
            s.id as subscription_id,
            s.status as sub_status,
            s.trial_ends_at,
            s.current_period_start,
            s.current_period_end,
            sp.name as plan_name,
            sp.slug as plan_slug,
            sp.price_monthly as plan_price_monthly,
            sp.price_yearly as plan_price_yearly
        FROM pharmacies p
        LEFT JOIN subscriptions s ON s.pharmacy_id = p.id
        LEFT JOIN subscription_plans sp ON sp.id = s.plan_id
        ORDER BY p.created_at DESC
    ''').fetchall()
    result = []
    for r in rows:
        item = dict(r)
        business_type = (item.get('business_type') or 'pharmacy').strip().lower()
        if business_type not in BUSINESS_TYPES:
            business_type = 'other'
        item['business_type'] = business_type
        item['business_label'] = BUSINESS_TYPES[business_type]['label']
        item.pop('api_key', None)
        # A store that has not been set up yet still needs its setup link so
        # the administrator can be given the page where they set their login.
        if (item.get('status') or 'active') == 'pending' and item.get('setup_token'):
            item['setup_path'] = '/admin-setup.html?token=' + item['setup_token']
        else:
            item.pop('setup_token', None)
            item.pop('pending_accounts', None)
        # Normalise subscription fields for the frontend
        item['sub_status'] = item.get('sub_status') or 'none'
        item['plan_name'] = item.get('plan_name') or '-'
        item['plan_slug'] = item.get('plan_slug') or '-'
        result.append(item)
    return jsonify(result)

@app.route('/api/admin/tenants/<int:tid>/suspend', methods=['POST'])
@require_super_admin
def suspend_tenant(tid):
    """Suspend a tenant store (blocks sign-in) due to non-payment or policy."""
    db = get_db()
    pharmacy = db.execute('SELECT * FROM pharmacies WHERE id = ?', (tid,)).fetchone()
    if not pharmacy:
        return jsonify({'error': 'Tenant not found'}), 404
    if (pharmacy['status'] or 'active') == 'suspended':
        return jsonify({'error': 'Tenant is already suspended'}), 400
    db.execute('UPDATE pharmacies SET status = ? WHERE id = ?', ('suspended', tid))
    db.commit()
    return jsonify({'suspended': True, 'tenant_id': tid, 'status': 'suspended'})

@app.route('/api/admin/tenants/<int:tid>/reactivate', methods=['POST'])
@require_super_admin
def reactivate_tenant(tid):
    """Reactivate a suspended tenant store."""
    db = get_db()
    pharmacy = db.execute('SELECT * FROM pharmacies WHERE id = ?', (tid,)).fetchone()
    if not pharmacy:
        return jsonify({'error': 'Tenant not found'}), 404
    if (pharmacy['status'] or 'active') == 'active':
        return jsonify({'error': 'Tenant is already active'}), 400
    db.execute('UPDATE pharmacies SET status = ? WHERE id = ?', ('active', tid))
    db.commit()
    return jsonify({'reactivated': True, 'tenant_id': tid, 'status': 'active'})

@app.route('/api/admin/tenants/<int:tid>/notify-subscription', methods=['POST'])
@require_super_admin
def notify_subscription(tid):
    """Send a subscription reminder notification to a tenant."""
    data = request.get_json(silent=True) or {}
    subject = data.get('subject', 'Subscription reminder')
    body = data.get('body', '')
    db = get_db()
    pharmacy = db.execute('SELECT * FROM pharmacies WHERE id = ?', (tid,)).fetchone()
    if not pharmacy:
        return jsonify({'error': 'Tenant not found'}), 404
    sub = db.execute('''
        SELECT s.*, sp.name as plan_name
        FROM subscriptions s
        LEFT JOIN subscription_plans sp ON sp.id = s.plan_id
        WHERE s.pharmacy_id = ?
        ORDER BY s.created_at DESC LIMIT 1
    ''', (tid,)).fetchone()
    if not body:
        if sub:
            plan_name = sub['plan_name'] or 'your plan'
            sub_status = sub['status'] or 'unknown'
            expiry = sub['current_period_end'] or sub['trial_ends_at'] or 'unknown'
            body = 'Hello %s, this is a reminder that your %s subscription (%s) %s. Please renew to avoid service interruption.' % (
                pharmacy['name'], plan_name, sub_status, 'expires on %s' % expiry if expiry != 'unknown' else 'is due for renewal')
        else:
            body = 'Hello %s, your store does not have an active subscription. Please contact support to set one up.' % pharmacy['name']
    try:
        db.execute(
            'INSERT INTO messages (pharmacy_id, from_user, to_user, subject, body, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (tid, 'Platform Admin', 'Staff', subject, body, 'unread', __import__('datetime').datetime.now().isoformat())
        )
        db.commit()
    except Exception:
        pass
    return jsonify({'notified': True, 'tenant_id': tid, 'subject': subject})

# ---------- Subscription plan assignment / change ----------

@app.route('/api/admin/tenants/<int:tid>/plan', methods=['POST'])
@require_super_admin
def assign_plan_to_tenant(tid):
    """Assign or change a tenant's subscription plan."""
    data = request.get_json(silent=True) or {}
    plan_id = data.get('plan_id')
    if not plan_id:
        return jsonify({'error': 'plan_id is required'}), 400
    db = get_db()
    pharmacy = db.execute('SELECT * FROM pharmacies WHERE id = ?', (tid,)).fetchone()
    if not pharmacy:
        return jsonify({'error': 'Tenant not found'}), 404
    plan = db.execute('SELECT * FROM subscription_plans WHERE id = ?', (plan_id,)).fetchone()
    if not plan:
        return jsonify({'error': 'Plan not found'}), 400
    now = datetime.now().isoformat()
    # End any existing active subscription
    db.execute(
        'UPDATE subscriptions SET status = ?, cancelled_at = ? WHERE pharmacy_id = ? AND status IN (?, ?)',
        ('cancelled', now, tid, 'active', 'trial')
    )
    # Create new subscription
    db.execute(
        'INSERT INTO subscriptions (pharmacy_id, plan_id, status, current_period_start, current_period_end, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (tid, plan_id, 'active', now, now, now, now)
    )
    db.commit()
    return jsonify({'assigned': True, 'tenant_id': tid, 'plan_id': plan_id, 'plan_name': plan['name']})

# ---------- Bulk actions ----------

@app.route('/api/admin/tenants/bulk', methods=['POST'])
@require_super_admin
def bulk_tenant_action():
    """Perform an action on multiple tenants at once."""
    data = request.get_json(silent=True) or {}
    ids = data.get('ids', [])
    action = data.get('action', '')
    if not isinstance(ids, list) or not ids:
        return jsonify({'error': 'ids list is required'}), 400
    if action not in ('suspend', 'reactivate', 'delete'):
        return jsonify({'error': 'Invalid action'}), 400
    db = get_db()
    processed = 0
    for tid in ids:
        if action == 'suspend':
            cur = db.execute('UPDATE pharmacies SET status = ? WHERE id = ? AND status != ?', ('suspended', tid, 'suspended'))
        elif action == 'reactivate':
            cur = db.execute('UPDATE pharmacies SET status = ? WHERE id = ? AND status != ?', ('active', tid, 'active'))
        elif action == 'delete':
            cur = db.execute('SELECT id FROM pharmacies WHERE id = ?', (tid,))
            if cur.fetchone():
                # Clear all related data
                for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                    table = row[0]
                    if table.startswith('sqlite_'):
                        continue
                    cols = {r[1] for r in db.execute('PRAGMA table_info("%s")' % table).fetchall()}
                    if 'pharmacy_id' in cols:
                        db.execute('DELETE FROM "%s" WHERE pharmacy_id = ?' % table, (tid,))
                db.execute('DELETE FROM pharmacies WHERE id = ?', (tid,))
        processed += cur.rowcount or (1 if action == 'delete' else 0)
    db.commit()
    return jsonify({'processed': processed, 'action': action})

# ---------- Usage stats per tenant ----------

@app.route('/api/admin/tenants/stats', methods=['GET'])
@require_super_admin
def tenant_usage_stats():
    """Return usage stats for all tenants (users, products, branches, sales)."""
    db = get_db()
    rows = db.execute('''
        SELECT p.id, p.name, p.status,
            (SELECT COUNT(*) FROM users u WHERE u.pharmacy_id = p.id) as user_count,
            (SELECT COUNT(*) FROM products pr WHERE pr.pharmacy_id = p.id) as product_count,
            (SELECT COUNT(*) FROM branches b WHERE b.pharmacy_id = p.id) as branch_count,
            (SELECT COUNT(*) FROM sales s WHERE s.pharmacy_id = p.id) as sale_count,
            (SELECT COALESCE(SUM(s.total), 0) FROM sales s WHERE s.pharmacy_id = p.id) as total_sales
        FROM pharmacies p
        ORDER BY p.created_at DESC
    ''').fetchall()
    result = []
    for r in rows:
        item = dict(r)
        try:
            item['total_sales'] = float(item['total_sales'] or 0)
        except Exception:
            item['total_sales'] = 0
        result.append(item)
    return jsonify(result)

# ---------- Payment tracking ----------

@app.route('/api/admin/payments', methods=['GET'])
@require_super_admin
def list_admin_payments():
    """List all payments across tenants, optionally filtered by pharmacy."""
    db = get_db()
    pharmacy_id = request.args.get('pharmacy_id')
    if pharmacy_id:
        rows = db.execute(
            'SELECT * FROM payments WHERE pharmacy_id = ? ORDER BY date DESC', (pharmacy_id,)
        ).fetchall()
    else:
        rows = db.execute('SELECT * FROM payments ORDER BY date DESC').fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/admin/payments', methods=['POST'])
@require_super_admin
def record_admin_payment():
    """Record a payment for a tenant."""
    data = request.get_json(silent=True) or {}
    pharmacy_id = data.get('pharmacy_id')
    amount = data.get('amount')
    method = data.get('method', 'other')
    reference = data.get('reference', '')
    description = data.get('description', '')
    if not pharmacy_id or not amount:
        return jsonify({'error': 'pharmacy_id and amount are required'}), 400
    db = get_db()
    pharmacy = db.execute('SELECT * FROM pharmacies WHERE id = ?', (pharmacy_id,)).fetchone()
    if not pharmacy:
        return jsonify({'error': 'Tenant not found'}), 404
    now = datetime.now().isoformat()
    cur = db.execute(
        'INSERT INTO payments (pharmacy_id, date, type, amount, method, reference, description, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (pharmacy_id, now, 'subscription', amount, method, reference, description, 'Platform Admin')
    )
    db.commit()
    return jsonify({'recorded': True, 'id': cur.lastrowid, 'pharmacy_id': pharmacy_id, 'amount': amount})

# ---------- Export ----------

@app.route('/api/admin/tenants/export', methods=['GET'])
@require_super_admin
def export_tenants():
    """Export tenant list with subscription info as CSV."""
    import csv, io
    db = get_db()
    rows = db.execute('''
        SELECT p.id, p.name, p.address, p.phone, p.email, p.business_type, p.status, p.created_at,
            s.status as sub_status, s.current_period_end, sp.name as plan_name
        FROM pharmacies p
        LEFT JOIN subscriptions s ON s.pharmacy_id = p.id
        LEFT JOIN subscription_plans sp ON sp.id = s.plan_id
        ORDER BY p.created_at DESC
    ''').fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Address', 'Phone', 'Email', 'Business Type', 'Status', 'Plan', 'Sub Status', 'Expiry', 'Created'])
    for r in rows:
        writer.writerow([
            r['id'], r['name'], r['address'] or '', r['phone'] or '', r['email'] or '',
            r['business_type'] or '', r['status'] or 'active',
            r['plan_name'] or '-', r['sub_status'] or '-', r['current_period_end'] or '-', r['created_at'] or ''
        ])
    csv_data = output.getvalue()
    output.close()
    return csv_data, 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename=tenants_export.csv'
    }

# ---------- Scheduled auto-suspend ----------

@app.route('/api/admin/tenants/auto-suspend', methods=['POST'])
@require_super_admin
def auto_suspend_expired():
    """Suspend tenants whose subscription has expired. Returns count suspended."""
    db = get_db()
    now = datetime.now().isoformat()
    # Find active subscriptions past their period end
    expired = db.execute('''
        SELECT s.pharmacy_id FROM subscriptions s
        WHERE s.status = 'active' AND s.current_period_end IS NOT NULL AND s.current_period_end < ?
    ''', (now,)).fetchall()
    count = 0
    for row in expired:
        tid = row['pharmacy_id']
        cur = db.execute('UPDATE pharmacies SET status = ? WHERE id = ? AND status != ?', ('suspended', tid, 'suspended'))
        count += cur.rowcount
        # Mark subscription as cancelled
        db.execute('UPDATE subscriptions SET status = ?, cancelled_at = ? WHERE pharmacy_id = ? AND status = ?',
            ('cancelled', now, tid, 'active'))
    db.commit()
    return jsonify({'suspended': count})

# ---------- Platform-admin plan management ----------

@app.route('/api/platform/admin/plans', methods=['GET'])
@require_super_admin
def platform_list_plans():
    """List all subscription plans (platform admin)."""
    db = get_db()
    rows = db.execute('SELECT * FROM subscription_plans ORDER BY id ASC').fetchall()
    plans = []
    for row in rows:
        plan = dict(row)
        try:
            plan['features'] = json.loads(plan.get('features') or '[]')
        except Exception:
            plan['features'] = []
        plans.append(plan)
    return jsonify(plans)

@app.route('/api/platform/admin/plans', methods=['POST'])
@require_super_admin
def platform_create_plan():
    """Create a subscription plan (platform admin)."""
    data = request.get_json(silent=True) or {}
    name = str(data.get('name') or '').strip()
    slug = str(data.get('slug') or '').strip()
    if not name or not slug:
        return jsonify({'error': 'Name and slug are required'}), 400
    db = get_db()
    cur = db.execute(
        'INSERT INTO subscription_plans (name, slug, description, price_monthly, price_yearly, max_users, max_products, max_branches, max_storage_mb, features, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (name, slug, str(data.get('description') or ''), float(data.get('price_monthly') or 0),
         float(data.get('price_yearly') or 0), int(data.get('max_users') or 5),
         int(data.get('max_products') or 100), int(data.get('max_branches') or 1),
         int(data.get('max_storage_mb') or 100), json.dumps(data.get('features') or []),
         int(data.get('is_active') or 1), datetime.now().isoformat())
    )
    db.commit()
    return jsonify({'created': True, 'id': cur.lastrowid}), 201

@app.route('/api/platform/admin/plans/<int:pid>', methods=['PUT'])
@require_super_admin
def platform_update_plan(pid):
    """Update a subscription plan (platform admin)."""
    data = request.get_json(silent=True) or {}
    db = get_db()
    plan = db.execute('SELECT * FROM subscription_plans WHERE id = ?', (pid,)).fetchone()
    if not plan:
        return jsonify({'error': 'Plan not found'}), 404
    sets = []
    values = []
    for k in ['name', 'slug', 'description', 'price_monthly', 'price_yearly', 'max_users', 'max_products', 'max_branches', 'max_storage_mb', 'features', 'is_active']:
        if k in data:
            v = data[k]
            if k == 'features':
                v = json.dumps(v if isinstance(v, list) else [v])
            sets.append(k + ' = ?')
            values.append(v)
    if not sets:
        return jsonify({'error': 'No valid fields to update'}), 400
    values.append(pid)
    db.execute('UPDATE subscription_plans SET ' + ', '.join(sets) + ' WHERE id = ?', values)
    db.commit()
    return jsonify({'updated': True})

@app.route('/api/platform/admin/plans/<int:pid>', methods=['DELETE'])
@require_super_admin
def platform_delete_plan(pid):
    """Delete a subscription plan (platform admin)."""
    db = get_db()
    db.execute('DELETE FROM subscription_plans WHERE id = ?', (pid,))
    db.commit()
    return jsonify({'deleted': True})

@app.route('/api/admin/tenants/<int:tid>', methods=['PUT'])
@require_super_admin
def update_tenant(tid):
    data = request.get_json()
    db = get_db()
    sets = []
    values = []
    allowed = ['name', 'address', 'phone', 'email', 'status']
    if data.get('business_type'):
        business_type = str(data['business_type']).strip().lower()
        if business_type not in BUSINESS_TYPES:
            return jsonify({'error': 'Unknown business type'}), 400
        allowed.append('business_type')
        data['business_type'] = business_type
    if data.get('business_modules') is not None:
        allowed.append('business_modules')
        data['business_modules'] = json.dumps(_normalise_modules(data['business_modules'], []))
    for k, v in data.items():
        if k in allowed:
            sets.append(f'{k} = ?')
            values.append(v)
    if not sets:
        return jsonify({'error': 'No valid fields to update'}), 400
    values.append(tid)
    db.execute(f"UPDATE pharmacies SET {', '.join(sets)} WHERE id = ?", values)
    db.commit()
    return jsonify({'updated': True})

@app.route('/api/admin/tenants/<int:tid>', methods=['DELETE'])
@require_super_admin
def delete_tenant(tid):
    db = get_db()
    if USE_POSTGRES:
        table_rows = db.execute(
            "SELECT table_name AS name FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall()
    else:
        table_rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    cleared = []
    for row in table_rows:
        table = row['name']
        if table.startswith('sqlite_'):
            continue
        if USE_POSTGRES:
            col_rows = db.execute(
                "SELECT column_name AS name FROM information_schema.columns WHERE table_name = %s",
                (table,)
            ).fetchall()
            columns = {r['name'] for r in col_rows}
        else:
            columns = {r['name'] for r in db.execute(f'PRAGMA table_info("{table}")').fetchall()}
        if 'pharmacy_id' not in columns:
            continue
        db.execute(f'DELETE FROM "{table}" WHERE pharmacy_id = ?', (tid,))
        cleared.append(table)
    db.execute('DELETE FROM pharmacies WHERE id = ?', (tid,))
    db.commit()
    return jsonify({'deleted': True, 'tables_cleared': cleared})

# ---------- Generic CRUD helper ----------

def table_response(table, extra_filter='', params=()):
    db = get_db()
    rows = db.execute(
        f'SELECT * FROM {table} WHERE pharmacy_id = ? {extra_filter}',
        (g.pharmacy_id,) + params
    ).fetchall()
    return jsonify([dict(r) for r in rows])

def table_create(table, data):
    try:
        db = get_db()
        cursor = db.execute(f'PRAGMA table_info({table})')
        valid_columns = {row['name'] for row in cursor.fetchall()}
        filtered_data = {k: v for k, v in data.items() if k in valid_columns and k != 'id'}
        keys = list(filtered_data.keys())
        placeholders = ['?'] * len(keys)
        values = list(filtered_data.values())
        sql = f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({', '.join(placeholders)})"
        cursor = db.execute(sql, values)
        db.commit()
        result = dict(filtered_data)
        result['id'] = cursor.lastrowid
        result['pharmacy_id'] = g.pharmacy_id
        return jsonify(result), 201
    except Exception as e:
        return jsonify({'error': f'Database insert failed: {str(e)}'}), 500

def table_update(table, record_id, data):
    try:
        db = get_db()
        cursor = db.execute(f'PRAGMA table_info({table})')
        valid_columns = {row['name'] for row in cursor.fetchall()}
        sets = []
        values = []
        for k, v in data.items():
            if k != 'id' and k in valid_columns:
                sets.append(f'{k} = ?')
                values.append(v)
        values.append(g.pharmacy_id)
        values.append(record_id)
        sql = f"UPDATE {table} SET {', '.join(sets)} WHERE pharmacy_id = ? AND id = ?"
        db.execute(sql, values)
        db.commit()
        return jsonify({'id': record_id, 'updated': True}), 200
    except Exception as e:
        return jsonify({'error': f'Database update failed: {str(e)}'}), 500

def table_delete(table, record_id):
    try:
        db = get_db()
        db.execute(f'DELETE FROM {table} WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, record_id))
        db.commit()
        return jsonify({'deleted': True})
    except Exception as e:
        return jsonify({'error': f'Database delete failed: {str(e)}'}), 500

def package_base_units(db, pharmacy_id, product_id, pkg_type, explicit_qty=None):
    """How many base units (e.g. individual packets) one package holds.

    A product's packaging_types carry a `qty` multiplier: a "Carton" with
    qty=12 means one carton contains 12 base units. Stock is always tracked
    in base units, so every stock movement is converted with this multiplier.
    An explicit qty sent by the client wins, so a sale keeps the multiplier
    that was in force when it was recorded even if the product changes later.
    """
    try:
        if explicit_qty is not None:
            mult = float(explicit_qty)
            if mult > 0:
                return mult
    except (TypeError, ValueError):
        pass
    if not pkg_type or not product_id:
        return 1.0
    try:
        row = db.execute(
            'SELECT packaging_types FROM products WHERE pharmacy_id = ? AND id = ?',
            (pharmacy_id, product_id)
        ).fetchone()
    except Exception:
        return 1.0
    if not row:
        return 1.0
    raw = row['packaging_types']
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return 1.0
    if not isinstance(raw, list):
        return 1.0
    for pkg in raw:
        if not isinstance(pkg, dict):
            continue
        if str(pkg.get('id')) == str(pkg_type):
            try:
                mult = float(pkg.get('qty') or 0)
            except (TypeError, ValueError):
                mult = 0
            return mult if mult > 0 else 1.0
    return 1.0


def package_cost_price(db, pharmacy_id, product_id, pkg_type, pkg_qty=None):
    """Cost of ONE package (e.g. one carton) of a product.

    Profit is calculated on the cost price of the package type that was
    actually sold, so a carton sold at N5 12,000 with a cost price of
    N9,000 books N3,000 profit - not the margin of a single packet.

    A package type without its own cost price falls back to the product's
    base-unit cost multiplied by the number of base units the package holds.
    """
    if not product_id:
        return 0.0
    try:
        row = db.execute(
            'SELECT cost_price, packaging_types FROM products WHERE pharmacy_id = ? AND id = ?',
            (pharmacy_id, product_id)
        ).fetchone()
    except Exception:
        return 0.0
    if not row:
        return 0.0
    try:
        base_cost = float(row['cost_price'] or 0)
    except (TypeError, ValueError):
        base_cost = 0.0
    units = 1.0
    raw = row['packaging_types']
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = []
    if isinstance(raw, list):
        for pkg in raw:
            if not isinstance(pkg, dict):
                continue
            if str(pkg.get('id')) == str(pkg_type) or (
                    pkg.get('name') and str(pkg.get('name')) == str(pkg_type)):
                try:
                    units = float(pkg.get('qty') or 0)
                except (TypeError, ValueError):
                    units = 0
                if units <= 0:
                    units = 1.0
                try:
                    own_cost = float(pkg.get('cost_price') or 0)
                except (TypeError, ValueError):
                    own_cost = 0.0
                if own_cost > 0:
                    return own_cost
                break
    if pkg_qty:
        try:
            explicit = float(pkg_qty)
            if explicit > 0:
                units = explicit
        except (TypeError, ValueError):
            pass
    return base_cost * units


def resolve_sale_item_costs(db, pharmacy_id, items):
    """Pin the cost price of every sold package onto the sale line.

    The client may send a cost price of its own (taken when the sale was
    rung up); otherwise the cost price of the package type is read from the
    product catalogue. Storing it with the line keeps historic profit stable
    when product costs change later.
    """
    for it in items or []:
        if not isinstance(it, dict):
            continue
        pid = it.get('product_id') or it.get('id')
        if not pid:
            continue
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            continue
        try:
            qty = float(it.get('qty') or 0)
        except (TypeError, ValueError):
            qty = 0.0
        try:
            sent_cost = float(it.get('cost_price') or 0)
        except (TypeError, ValueError):
            sent_cost = 0.0
        if sent_cost <= 0:
            sent_cost = package_cost_price(
                db, pharmacy_id, pid,
                it.get('pkg_type') or it.get('pkgType'),
                it.get('pkg_qty')
            )
        it['cost_price'] = sent_cost
        it['cost_total'] = sent_cost * qty
    return items

def adjust_stock_for_items(db, pharmacy_id, items, sign):
    """Move stock for a set of sale lines.

    ``sign`` is -1 to take stock out (a sale) and +1 to put it back (a void
    or the original lines of an edited sale). Quantities are converted to
    base units with the package size the line was recorded with, so a sale
    of 2 cartons of 12 tablets takes 24 base units out of stock.
    """
    for it in items or []:
        if not isinstance(it, dict):
            continue
        pid = it.get('product_id') or it.get('id')
        if not pid:
            continue
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            continue
        try:
            qty = float(it.get('qty') or 0)
        except (TypeError, ValueError):
            qty = 0.0
        if qty <= 0:
            continue
        mult = package_base_units(
            db, pharmacy_id, pid,
            it.get('pkg_type') or it.get('pkgType'), it.get('pkg_qty')
        )
        base_qty = qty * (mult if mult else 1)
        if base_qty <= 0:
            continue
        if sign > 0:
            db.execute(
                'UPDATE products SET stock = stock + ? WHERE pharmacy_id = ? AND id = ?',
                (base_qty, pharmacy_id, pid)
            )
        else:
            db.execute(
                'UPDATE products SET stock = stock - ? WHERE pharmacy_id = ? AND id = ?',
                (base_qty, pharmacy_id, pid)
            )

def sale_account_amount(payment_method, account_amount, total):
    """Portion of a sale that is charged to the customer's store account.

    A sale can be settled partly in cash and partly on the customer's
    account: the cash received is `amount_tendered` and whatever the customer
    did not pay in cash is `account_amount`. A sale paid entirely on the
    account carries no account_amount, so the payment method decides.
    """
    try:
        amount = float(account_amount or 0)
    except (TypeError, ValueError):
        amount = 0
    if amount > 0:
        return amount
    if (payment_method or '') == 'store_account':
        try:
            return float(total or 0)
        except (TypeError, ValueError):
            return 0
    return 0

# ========== API Routes ==========

# --- Products ---
@app.route('/api/products', methods=['GET'])
@require_auth
def get_products():
    db = get_db()
    rows = db.execute('SELECT * FROM products WHERE pharmacy_id = ?', (g.pharmacy_id,)).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        if row.get('prices') and isinstance(row['prices'], str):
            try:
                row['prices'] = json.loads(row['prices'])
            except Exception:
                row['prices'] = {}
        if row.get('packaging_types') and isinstance(row['packaging_types'], str):
            try:
                row['packaging_types'] = json.loads(row['packaging_types'])
            except Exception:
                row['packaging_types'] = []
        result.append(row)
    return jsonify(result)

@app.route('/api/products', methods=['POST'])
@require_auth
def create_product():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    if 'prices' in data and isinstance(data['prices'], dict):
        data['prices'] = json.dumps(data['prices'])
    if 'packaging_types' in data and isinstance(data['packaging_types'], list):
        data['packaging_types'] = json.dumps(data['packaging_types'])
    result = table_create('products', data)
    if result[1] == 201:
        resp_data = result[0].get_json()
        if resp_data.get('prices') and isinstance(resp_data['prices'], str):
            try:
                resp_data['prices'] = json.loads(resp_data['prices'])
            except Exception:
                pass
        if resp_data.get('packaging_types') and isinstance(resp_data['packaging_types'], str):
            try:
                resp_data['packaging_types'] = json.loads(resp_data['packaging_types'])
            except Exception:
                pass
        return jsonify(resp_data), 201
    return result

@app.route('/api/products/<int:pid>', methods=['PUT'])
@require_auth
def update_product(pid):
    data = request.get_json()
    if 'prices' in data and isinstance(data['prices'], dict):
        data['prices'] = json.dumps(data['prices'])
    if 'packaging_types' in data and isinstance(data['packaging_types'], list):
        data['packaging_types'] = json.dumps(data['packaging_types'])
    result = table_update('products', pid, data)
    if result[1] == 200:
        resp_data = result[0].get_json()
        return jsonify(resp_data), 200
    return result

@app.route('/api/products/<int:pid>', methods=['DELETE'])
@require_auth
def delete_product(pid):
    return table_delete('products', pid)

# --- Receiving ---
@app.route('/api/receiving', methods=['GET'])
@require_auth
def list_receiving():
    db = get_db()
    rows = db.execute(
        'SELECT * FROM receiving WHERE pharmacy_id = ? ORDER BY id DESC LIMIT 200',
        (g.pharmacy_id,)
    ).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        if row.get('items') and isinstance(row['items'], str):
            try:
                row['items'] = json.loads(row['items'])
            except Exception:
                row['items'] = []
        result.append(row)
    return jsonify(result)

@app.route('/api/receiving', methods=['POST'])
@require_auth
def create_receiving():
    try:
        db = get_db()
        data = request.get_json() or {}
        items = data.get('items', [])
        if not isinstance(items, list) or not items:
            return jsonify({'error': 'items array is required'}), 400
        supplier_id = data.get('supplier_id') or data.get('supplier')
        supplier_name = data.get('supplier_name') or ''
        if supplier_id and not supplier_name:
            s = db.execute(
                'SELECT name FROM suppliers WHERE pharmacy_id = ? AND id = ?',
                (g.pharmacy_id, supplier_id)
            ).fetchone()
            if s:
                supplier_name = s['name']
        enriched_items = []
        total = 0.0
        for it in items:
            pid = it.get('product_id') or it.get('id')
            if not pid:
                continue
            try:
                pid = int(pid)
            except (TypeError, ValueError):
                continue
            prod = db.execute(
                'SELECT id, name, sku, stock, cost_price FROM products WHERE pharmacy_id = ? AND id = ?',
                (g.pharmacy_id, pid)
            ).fetchone()
            if not prod:
                continue
            qty = float(it.get('qty') or 0)
            if qty <= 0:
                continue
            unit_cost = float(it.get('cost_price') or prod['cost_price'] or 0)
            # Stock is held in base units, so a line of N cartons of 12 units
            # each adds N * 12 to stock. The unit cost is quoted per package,
            # so it is stored per base unit to keep stock valuation correct.
            mult = package_base_units(
                db, g.pharmacy_id, pid,
                it.get('pkg_type') or it.get('pkgType'), it.get('pkg_qty')
            )
            base_qty = qty * mult
            base_cost = unit_cost / mult if mult else unit_cost
            new_stock = float(prod['stock'] or 0) + base_qty
            db.execute(
                'UPDATE products SET stock = ?, cost_price = ? WHERE pharmacy_id = ? AND id = ?',
                (new_stock, base_cost, g.pharmacy_id, pid)
            )
            line_total = unit_cost * qty
            total += line_total
            enriched_items.append({
                'product_id': pid,
                'name': prod['name'],
                'sku': prod['sku'],
                'qty': qty,
                'pkg_qty': mult,
                'base_qty': base_qty,
                'cost_price': unit_cost,
                'pkg_type': it.get('pkg_type') or it.get('pkgType'),
                'expiry': it.get('expiry') or None,
                'line_total': round(line_total, 2)
            })
        if not enriched_items:
            return jsonify({'error': 'No valid items to receive'}), 400
        cur = db.execute(
            'INSERT INTO receiving (pharmacy_id, date, ref, supplier_id, supplier_name, items, total, notes, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                g.pharmacy_id,
                data.get('date') or datetime.utcnow().isoformat(),
                data.get('ref') or '',
                supplier_id,
                supplier_name,
                json.dumps(enriched_items),
                round(total, 2),
                data.get('notes') or '',
                request.headers.get('X-Username')
            )
        )
        new_id = cur.lastrowid
        try:
            db.execute(
                'INSERT INTO audit_log (pharmacy_id, user_name, action, entity_type, entity_id, details, ip_address) VALUES (?,?,?,?,?,?,?)',
                (
                    g.pharmacy_id, request.headers.get('X-Username'), 'create_receiving', 'receiving', new_id,
                    json.dumps({'supplier': supplier_name, 'total': round(total, 2), 'items': len(enriched_items)}),
                    request.remote_addr
                )
            )
        except Exception as audit_err:
            app.logger.warning('audit log write failed: %s' % audit_err)
        db.commit()
        record = db.execute('SELECT * FROM receiving WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, new_id)).fetchone()
        if not record:
            return jsonify({'id': new_id, 'status': 'ok'}), 201
        result = dict(record)
        try:
            result['items'] = json.loads(result['items'])
        except Exception:
            result['items'] = []
        return jsonify(result), 201
    except Exception as e:
        app.logger.exception('create_receiving failed')
        return jsonify({'error': 'Server error: ' + str(e)}), 500

# --- Sales ---
@app.route('/api/sales', methods=['GET'])
@require_auth
def get_sales():
    db = get_db()
    rows = db.execute(
        'SELECT * FROM sales WHERE pharmacy_id = ? ORDER BY date DESC',
        (g.pharmacy_id,)
    ).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        if row.get('items') and isinstance(row['items'], str):
            try:
                row['items'] = json.loads(row['items'])
            except Exception:
                row['items'] = []
        result.append(row)
    return jsonify(result)

@app.route('/api/sales', methods=['POST'])
@require_auth
def create_sale():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    db = get_db()
    items = data.get('items') or []
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            items = []
    if not isinstance(items, list):
        items = []
    # Pin each line's package multiplier so stock moves in base units and the
    # same amount can be restored later if the sale is voided.
    for it in items:
        if not isinstance(it, dict):
            continue
        pid = it.get('product_id') or it.get('id')
        if not pid:
            continue
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            continue
        it['pkg_qty'] = package_base_units(
            db, g.pharmacy_id, pid,
            it.get('pkg_type') or it.get('pkgType'), it.get('pkg_qty')
        )
    # Pin the cost price of the package that was sold so profit is reported
    # on the package cost, not on the cost of a single base unit.
    resolve_sale_item_costs(db, g.pharmacy_id, items)
    if 'items' in data:
        data['items'] = json.dumps(items)
    result = table_create('sales', data)
    if result[1] == 201:
        account_amount = sale_account_amount(
            data.get('payment_method'), data.get('account_amount'), data.get('total', 0)
        )
        if account_amount > 0 and data.get('customer_id'):
            db.execute(
                'UPDATE customers SET balance = balance + ? WHERE pharmacy_id = ? AND id = ?',
                (account_amount, g.pharmacy_id, data['customer_id'])
            )
        for it in items:
            adjust_stock_for_items(db, g.pharmacy_id, [it], -1)
    db.commit()
    if result[1] == 201:
        body = result[0].get_json()
        if isinstance(body, dict) and isinstance(body.get('items'), str):
            try:
                body['items'] = json.loads(body['items'])
            except Exception:
                body['items'] = []
            result = (jsonify(body), 201)
    return result

@app.route('/api/sales/<int:sid>', methods=['GET'])
@require_auth
def get_sale(sid):
    db = get_db()
    sale = db.execute('SELECT * FROM sales WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, sid)).fetchone()
    if not sale:
        return jsonify({'error': 'Sale not found'}), 404
    row = dict(sale)
    if row.get('items') and isinstance(row['items'], str):
        row['items'] = json.loads(row['items'])
    return jsonify(row)

@app.route('/api/sales/<int:sid>', methods=['PUT'])
@require_auth
def update_sale(sid):
    data = request.get_json()
    db = get_db()
    if 'items' in data and isinstance(data['items'], list):
        items = data['items']
        for it in items:
            if not isinstance(it, dict):
                continue
            pid = it.get('product_id') or it.get('id')
            if not pid:
                continue
            try:
                pid = int(pid)
            except (TypeError, ValueError):
                continue
            it['pkg_qty'] = package_base_units(
                db, g.pharmacy_id, pid,
                it.get('pkg_type') or it.get('pkgType'), it.get('pkg_qty')
            )
        resolve_sale_item_costs(db, g.pharmacy_id, items)
        data['items'] = json.dumps(items)
    db = get_db()
    # The lines the sale was recorded with. They are needed after the update
    # to put their stock back before the new lines are taken out again.
    old_sale = db.execute(
        'SELECT status, items FROM sales WHERE pharmacy_id = ? AND id = ?',
        (g.pharmacy_id, sid)
    ).fetchone()
    old_items = []
    if old_sale:
        old_items = old_sale['items']
        if isinstance(old_items, str):
            try:
                old_items = json.loads(old_items)
            except Exception:
                old_items = []
        if not isinstance(old_items, list):
            old_items = []
    allowed = ['customer_id', 'customer_name', 'payment_method', 'discount_amount',
               'tax', 'notes', 'cashier', 'amount_tendered', 'change', 'items', 'subtotal',
               'account_amount']
    clean = {k: v for k, v in data.items() if k in allowed}
    if 'discount_amount' in clean or 'tax' in clean or 'subtotal' in clean:
        sale = db.execute('SELECT subtotal, discount_amount, tax, total FROM sales WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, sid)).fetchone()
        if sale:
            subtotal = float(clean.get('subtotal', sale['subtotal'] or 0))
            disc = float(clean.get('discount_amount', sale['discount_amount'] or 0))
            tax = float(clean.get('tax', sale['tax'] or 0))
            clean['total'] = round(subtotal - disc + tax, 2)
    # Reconcile store-account customer balance + record an audit trail.
    try:
        old = db.execute('SELECT status, payment_method, customer_id, customer_name, total, account_amount FROM sales WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, sid)).fetchone()
        if old:
            old_pm = (old['payment_method'] or 'cash')
            old_cust = old['customer_id']
            old_cname = old['customer_name']
            old_total = float(old['total'] or 0)
            old_account = sale_account_amount(old_pm, old['account_amount'], old_total)
            new_pm = clean.get('payment_method', old_pm)
            new_cust = clean.get('customer_id', old_cust)
            new_cname = clean.get('customer_name', old_cname)
            new_total = float(clean.get('total', old_total) or 0)
            new_account = sale_account_amount(
                new_pm, clean.get('account_amount', old['account_amount']), new_total
            )

            def change(cust_id, delta):
                if not cust_id:
                    return
                c = db.execute('SELECT balance FROM customers WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, cust_id)).fetchone()
                if not c:
                    return
                nb = max(0.0, (float(c['balance'] or 0)) + delta)
                db.execute('UPDATE customers SET balance = ? WHERE pharmacy_id = ? AND id = ?', (nb, g.pharmacy_id, cust_id))

            # Only the part of the sale that sits on an account moves a
            # customer balance, so a part-cash sale credits just that part.
            # A voided sale has already been reversed, so it is left alone.
            if (old['status'] or 'completed') != 'void':
                if old_cust == new_cust:
                    change(new_cust, new_account - old_account)
                else:
                    change(old_cust, -old_account)
                    change(new_cust, new_account)

            details = json.dumps({
                'old_total': old_total, 'new_total': new_total,
                'old_account': old_account, 'new_account': new_account,
                'old_customer': old_cname, 'new_customer': new_cname,
                'old_payment': old_pm, 'new_payment': new_pm
            })
            db.execute(
                'INSERT INTO audit_log (pharmacy_id, user_name, action, entity_type, entity_id, details, ip_address) VALUES (?,?,?,?,?,?,?)',
                (
                    g.pharmacy_id, request.headers.get('X-Username'), 'edit_sale', 'sale', sid,
                    details, request.remote_addr
                )
            )
    except Exception as e:
        app.logger.warning('store-account balance reconcile failed: %s' % e)
    result = table_update('sales', sid, clean)
    # Keep stock in step with the sale: the original lines go back into stock
    # and the edited lines are taken out again. A voided sale has already been
    # reversed, so it is left alone. A request that does not carry items (a
    # payment-only edit) leaves stock untouched.
    try:
        if old_sale and 'items' in clean and (old_sale['status'] or 'completed') != 'void':
            new_items = clean.get('items')
            if isinstance(new_items, str):
                try:
                    new_items = json.loads(new_items)
                except Exception:
                    new_items = []
            if not isinstance(new_items, list):
                new_items = []
            adjust_stock_for_items(db, g.pharmacy_id, old_items, 1)
            adjust_stock_for_items(db, g.pharmacy_id, new_items, -1)
            db.commit()
    except Exception as e:
        app.logger.warning('sale stock reconcile failed: %s' % e)
    return result

@app.route('/api/sales/<int:sid>/void', methods=['POST'])
@require_auth
def void_sale(sid):
    db = get_db()
    sale = db.execute('SELECT * FROM sales WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, sid)).fetchone()
    if not sale:
        return jsonify({'error': 'Sale not found'}), 404
    if sale['status'] == 'void':
        return jsonify({'error': 'Already voided'}), 400
    items = sale['items']
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            items = []
    # Give back exactly what was taken: base units for the package the sale
    # was recorded with.
    adjust_stock_for_items(db, g.pharmacy_id, items, 1)
    account_amount = sale_account_amount(
        sale['payment_method'], sale['account_amount'], sale['total']
    )
    if account_amount > 0 and sale['customer_id']:
        c = db.execute('SELECT balance FROM customers WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, sale['customer_id'])).fetchone()
        if c:
            db.execute('UPDATE customers SET balance = ? WHERE pharmacy_id = ? AND id = ?',
                       (max(0.0, float(c['balance'] or 0) - account_amount), g.pharmacy_id, sale['customer_id']))
    db.execute('UPDATE sales SET status = ? WHERE pharmacy_id = ? AND id = ?', ('void', g.pharmacy_id, sid))
    details = json.dumps({'total': sale['total'], 'customer': sale['customer_name'], 'payment': sale['payment_method']})
    db.execute('INSERT INTO audit_log (pharmacy_id, user_name, action, entity_type, entity_id, details, ip_address) VALUES (?,?,?,?,?,?,?)',
               (g.pharmacy_id, request.headers.get('X-Username'), 'void_sale', 'sale', sid, details, request.remote_addr))
    db.commit()
    return jsonify({'id': sid, 'status': 'void', 'updated': True})

@app.route('/api/audit', methods=['GET'])
@require_auth
def get_audit():
    db = get_db()
    rows = db.execute('SELECT * FROM audit_log WHERE pharmacy_id = ? ORDER BY created_at DESC LIMIT 300', (g.pharmacy_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

# --- Customers ---
@app.route('/api/customers', methods=['GET'])
@require_auth
def get_customers():
    db = get_db()
    rows = db.execute('SELECT * FROM customers WHERE pharmacy_id = ?', (g.pharmacy_id,)).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        row['firstName'] = row.get('first_name', '')
        row['lastName'] = row.get('last_name', '')
        row['fullName'] = (row.get('first_name', '') + ' ' + row.get('last_name', '')).strip()
        result.append(row)
    return jsonify(result)

@app.route('/api/customers', methods=['POST'])
@require_auth
def create_customer():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('customers', data)

@app.route('/api/customers/<int:cid>', methods=['PUT'])
@require_auth
def update_customer(cid):
    data = request.get_json()
    return table_update('customers', cid, data)

@app.route('/api/customers/<int:cid>', methods=['DELETE'])
@require_auth
def delete_customer(cid):
    return table_delete('customers', cid)

# --- Employees ---
@app.route('/api/employees', methods=['GET'])
@require_auth
def get_employees():
    return table_response('employees')

@app.route('/api/employees', methods=['POST'])
@require_auth
def create_employee():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('employees', data)

@app.route('/api/employees/<int:eid>', methods=['PUT'])
@require_auth
def update_employee(eid):
    data = request.get_json()
    return table_update('employees', eid, data)

@app.route('/api/employees/<int:eid>', methods=['DELETE'])
@require_auth
def delete_employee(eid):
    return table_delete('employees', eid)

# --- Inventory ---
@app.route('/api/inventory', methods=['GET'])
@require_auth
def get_inventory():
    db = get_db()
    rows = db.execute(
        '''SELECT i.*, p.name as product_name, p.sku, p.category_name
           FROM inventory i
           LEFT JOIN products p ON i.product_id = p.id AND p.pharmacy_id = i.pharmacy_id
           WHERE i.pharmacy_id = ?''',
        (g.pharmacy_id,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/inventory', methods=['POST'])
@require_auth
def create_inventory():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('inventory', data)

@app.route('/api/inventory/<int:iid>', methods=['PUT'])
@require_auth
def update_inventory(iid):
    data = request.get_json()
    return table_update('inventory', iid, data)

# --- Expenses ---
@app.route('/api/expenses', methods=['GET'])
@require_auth
def get_expenses():
    return table_response('expenses', ' ORDER BY date DESC')

@app.route('/api/expenses', methods=['POST'])
@require_auth
def create_expense():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('expenses', data)

@app.route('/api/expenses/<int:eid>', methods=['DELETE'])
@require_auth
def delete_expense(eid):
    return table_delete('expenses', eid)

# --- Payments ---
@app.route('/api/payments', methods=['GET'])
@require_auth
def get_payments():
    return table_response('payments', ' ORDER BY date DESC')

@app.route('/api/payments', methods=['POST'])
@require_auth
def create_payment():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    result = table_create('payments', data)
    if result[1] == 201 and data.get('customer'):
        db = get_db()
        db.execute(
            'UPDATE customers SET balance = balance - ? WHERE pharmacy_id = ? AND id = ?',
            (data.get('amount', 0), g.pharmacy_id, data['customer'])
        )
        db.commit()
    return result

@app.route('/api/payments/<int:pid>', methods=['PUT'])
@require_auth
def update_payment(pid):
    data = request.get_json()
    return table_update('payments', pid, data)

@app.route('/api/payments/<int:pid>', methods=['DELETE'])
@require_auth
def delete_payment(pid):
    return table_delete('payments', pid)

# --- Locations ---
@app.route('/api/locations', methods=['GET'])
@require_auth
def get_locations():
    return table_response('locations')

@app.route('/api/locations', methods=['POST'])
@require_auth
def create_location():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('locations', data)

@app.route('/api/locations/<int:lid>', methods=['PUT'])
@require_auth
def update_location(lid):
    data = request.get_json()
    return table_update('locations', lid, data)

@app.route('/api/locations/<int:lid>', methods=['DELETE'])
@require_auth
def delete_location(lid):
    return table_delete('locations', lid)

# --- Appointments ---
@app.route('/api/appointments', methods=['GET'])
@require_auth
def get_appointments():
    return table_response('appointments', ' ORDER BY date ASC, time ASC')

@app.route('/api/appointments', methods=['POST'])
@require_auth
def create_appointment():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('appointments', data)

@app.route('/api/appointments/<int:aid>', methods=['PUT'])
@require_auth
def update_appointment(aid):
    data = request.get_json()
    return table_update('appointments', aid, data)

@app.route('/api/appointments/<int:aid>', methods=['DELETE'])
@require_auth
def delete_appointment(aid):
    return table_delete('appointments', aid)

# --- Gift Cards ---
@app.route('/api/giftcards', methods=['GET'])
@require_auth
def get_giftcards():
    return table_response('giftcards')

@app.route('/api/giftcards', methods=['POST'])
@require_auth
def create_giftcard():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('giftcards', data)

@app.route('/api/giftcards/<int:gid>', methods=['PUT'])
@require_auth
def update_giftcard(gid):
    data = request.get_json()
    # Map frontend fields to database fields
    if 'cardNumber' in data:
        data['code'] = data.pop('cardNumber')
    if 'recipient' in data:
        data['customer_name'] = data.pop('recipient')
    if 'expiry' in data:
        data['expiry_date'] = data.pop('expiry')
    return table_update('giftcards', gid, data)

@app.route('/api/giftcards/<int:gid>', methods=['DELETE'])
@require_auth
def delete_giftcard(gid):
    return table_delete('giftcards', gid)

# --- Messages ---
@app.route('/api/messages', methods=['GET'])
@require_auth
def get_messages():
    return table_response('messages', ' ORDER BY created_at DESC')

@app.route('/api/messages', methods=['POST'])
@require_auth
def create_message():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('messages', data)

@app.route('/api/messages/<int:mid>', methods=['DELETE'])
@require_auth
def delete_message(mid):
    return table_delete('messages', mid)

# --- Deliveries ---
@app.route('/api/deliveries', methods=['GET'])
@require_auth
def get_deliveries():
    return table_response('deliveries')

@app.route('/api/deliveries', methods=['POST'])
@require_auth
def create_delivery():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('deliveries', data)

# --- Invoices ---
@app.route('/api/invoices', methods=['GET'])
@require_auth
def get_invoices():
    return table_response('invoices')

@app.route('/api/invoices', methods=['POST'])
@require_auth
def create_invoice():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    if 'items' in data and isinstance(data['items'], list):
        data['items'] = json.dumps(data['items'])
    return table_create('invoices', data)

# --- Suppliers ---
@app.route('/api/suppliers', methods=['GET'])
@require_auth
def get_suppliers():
    return table_response('suppliers')

@app.route('/api/suppliers', methods=['POST'])
@require_auth
def create_supplier():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('suppliers', data)

@app.route('/api/suppliers/<int:sid>', methods=['PUT'])
@require_auth
def update_supplier(sid):
    data = request.get_json()
    return table_update('suppliers', sid, data)

@app.route('/api/suppliers/<int:sid>', methods=['DELETE'])
@require_auth
def delete_supplier(sid):
    return table_delete('suppliers', sid)

# --- Dashboard / Stats ---
@app.route('/api/dashboard', methods=['GET'])
@require_auth
def dashboard():
    db = get_db()
    pid = g.pharmacy_id
    total_sales = db.execute(
        'SELECT COALESCE(SUM(total), 0) as s FROM sales WHERE pharmacy_id = ?', (pid,)
    ).fetchone()['s']
    total_transactions = db.execute(
        'SELECT COUNT(*) as c FROM sales WHERE pharmacy_id = ?', (pid,)
    ).fetchone()['c']
    total_products = db.execute(
        'SELECT COUNT(*) as c FROM products WHERE pharmacy_id = ?', (pid,)
    ).fetchone()['c']
    total_customers = db.execute(
        'SELECT COUNT(*) as c FROM customers WHERE pharmacy_id = ?', (pid,)
    ).fetchone()['c']
    low_stock = db.execute(
        'SELECT COUNT(*) as c FROM products WHERE pharmacy_id = ? AND stock > 0 AND stock <= reorder_level',
        (pid,)
    ).fetchone()['c']
    return jsonify({
        'total_sales': total_sales,
        'total_transactions': total_transactions,
        'total_products': total_products,
        'total_customers': total_customers,
        'low_stock': low_stock
    })

# --- Reports ---
@app.route('/api/reports/sales-by-category', methods=['GET'])
@require_auth
def sales_by_category():
    db = get_db()
    pid = g.pharmacy_id
    rows = db.execute('''
        SELECT COALESCE(category_name, 'Other') as category, SUM(total) as total
        FROM sales WHERE pharmacy_id = ?
        GROUP BY category_name
    ''', (pid,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/reports/sales-trend', methods=['GET'])
@require_auth
def sales_trend():
    db = get_db()
    pid = g.pharmacy_id
    thirty_days_ago = (datetime.now() - __import__('datetime').timedelta(days=30)).strftime('%Y-%m-%d')
    rows = db.execute('''
        SELECT date as day, SUM(total) as total
        FROM sales WHERE pharmacy_id = ? AND date >= ?
        GROUP BY date ORDER BY date ASC
    ''', (pid, thirty_days_ago)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/reports/profit', methods=['GET'])
@require_auth
def profit_report():
    """Profit computed on the cost price of the package type that was sold.

    Each sale line carries the cost price of the package that was rung up
    (pinned when the sale was recorded). Lines recorded before that was kept
    fall back to the current cost price of the product's package type.
    """
    db = get_db()
    pid = g.pharmacy_id
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    query = 'SELECT id, date, total, tax, items, status FROM sales WHERE pharmacy_id = ?'
    params = [pid]
    if date_from:
        query += ' AND substr(date, 1, 10) >= ?'
        params.append(date_from)
    if date_to:
        query += ' AND substr(date, 1, 10) <= ?'
        params.append(date_to)
    rows = db.execute(query, tuple(params)).fetchall()

    products = {}
    for r in db.execute('SELECT id, cost_price, packaging_types FROM products WHERE pharmacy_id = ?', (pid,)).fetchall():
        products[str(r['id'])] = {'cost_price': r['cost_price'], 'packaging_types': r['packaging_types']}

    revenue = 0.0
    tax = 0.0
    cogs = 0.0
    count = 0
    for r in rows:
        if (r['status'] or 'completed') == 'void':
            continue
        count += 1
        revenue += float(r['total'] or 0)
        tax += float(r['tax'] or 0)
        items = r['items']
        if isinstance(items, str):
            try:
                items = json.loads(items)
            except Exception:
                items = []
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                qty = float(it.get('qty') or 0)
            except (TypeError, ValueError):
                qty = 0.0
            unit = None
            if it.get('cost_price') is not None:
                try:
                    unit = float(it.get('cost_price') or 0)
                except (TypeError, ValueError):
                    unit = None
            if not unit:
                pid_key = str(it.get('product_id') or it.get('id') or '')
                product = products.get(pid_key)
                if product:
                    unit = package_cost_price(
                        db, pid, it.get('product_id') or it.get('id'),
                        it.get('pkg_type') or it.get('pkgType'), it.get('pkg_qty')
                    )
            cogs += (unit or 0.0) * qty
    profit = revenue - cogs
    return jsonify({
        'revenue': round(revenue, 2),
        'cogs': round(cogs, 2),
        'tax': round(tax, 2),
        'profit': round(profit, 2),
        'margin': round((profit / revenue) * 100, 2) if revenue > 0 else 0,
        'transactions': count
    })

# --- Register endpoint for staff (users within pharmacy) ---
@app.route('/api/users/register', methods=['POST'])
@require_auth
@require_admin
def register_staff():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    name = data.get('name', username)
    role = data.get('role', 'staff')
    store = data.get('store', 'main')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    try:
        db = get_db()
        db.execute(
            'INSERT INTO users (pharmacy_id, username, password, name, role, store) VALUES (?, ?, ?, ?, ?, ?)',
            (g.pharmacy_id, username, password, name, role, store)
        )
        db.commit()
        return jsonify({'message': 'Staff account created', 'username': username}), 201
    except IntegrityError:
        return jsonify({'error': 'Username already exists for this pharmacy'}), 400

@app.route('/api/users', methods=['GET'])
@require_auth
def list_users():
    db = get_db()
    users = db.execute(
        'SELECT id, username, name, role, store, email, phone, active, last_login, page_access, created_at FROM users WHERE pharmacy_id = ?',
        (g.pharmacy_id,)
    ).fetchall()
    result = []
    for u in users:
        d = dict(u)
        d.pop('password', None)
        d['active'] = d.get('active') is not None and bool(d.get('active'))
        d['page_access'] = _parse_page_access(d.get('page_access'))
        result.append(d)
    return jsonify(result)

@app.route('/api/users/<int:uid>', methods=['PUT'])
@require_auth
@require_admin
def update_user(uid):
    data = request.get_json()
    sets = []
    values = []
    for k, v in data.items():
        if k not in ('id', 'pharmacy_id', 'password'):
            sets.append(f'{k} = ?')
            values.append(v)
    if 'password' in data and data['password']:
        sets.append('password = ?')
        values.append(data['password'])
    values.extend([g.pharmacy_id, uid])
    db = get_db()
    db.execute(f"UPDATE users SET {', '.join(sets)} WHERE pharmacy_id = ? AND id = ?", values)
    db.commit()
    return jsonify({'updated': True})

@app.route('/api/users/<int:uid>', methods=['DELETE'])
@require_auth
@require_admin
def delete_user(uid):
    db = get_db()
    db.execute('DELETE FROM users WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, uid))
    db.commit()
    return jsonify({'deleted': True})

# --- Categories ---
@app.route('/api/categories', methods=['GET'])
@require_auth
def get_categories():
    db = get_db()
    cats = db.execute('SELECT * FROM categories WHERE pharmacy_id = ?', (g.pharmacy_id,)).fetchall()
    return jsonify([dict(c) for c in cats])

@app.route('/api/categories', methods=['POST'])
@require_auth
def create_category():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    try:
        return table_create('categories', data)
    except IntegrityError:
        return jsonify({'error': 'Category already exists'}), 400

# --- Catalogue PDF info ---
@app.route('/api/catalogue', methods=['GET'])
@require_auth
def get_catalogue():
    db = get_db()
    products = db.execute(
        'SELECT * FROM products WHERE pharmacy_id = ?', (g.pharmacy_id,)
    ).fetchall()
    return jsonify([dict(p) for p in products])

# --- Roles ---
@app.route('/api/roles', methods=['GET'])
@require_auth
def get_roles():
    db = get_db()
    rows = db.execute('SELECT * FROM roles WHERE pharmacy_id = ?', (g.pharmacy_id,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d.get('permissions') and isinstance(d['permissions'], str):
            try:
                d['permissions'] = json.loads(d['permissions'])
            except Exception:
                d['permissions'] = []
        result.append(d)
    return jsonify(result)

@app.route('/api/roles', methods=['POST'])
@require_auth
@require_admin
def create_role():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Role name is required'}), 400
    permissions = data.get('permissions', [])
    if not isinstance(permissions, list):
        permissions = []
    db = get_db()
    try:
        cursor = db.execute(
            'INSERT INTO roles (pharmacy_id, name, description, permissions) VALUES (?, ?, ?, ?)',
            (g.pharmacy_id, name, data.get('description', ''), json.dumps(permissions))
        )
        db.commit()
        data['id'] = cursor.lastrowid
        data['pharmacy_id'] = g.pharmacy_id
        return jsonify(data), 201
    except IntegrityError:
        return jsonify({'error': 'Role already exists'}), 400

@app.route('/api/roles/<int:rid>', methods=['PUT'])
@require_auth
@require_admin
def update_role(rid):
    data = request.get_json()
    db = get_db()
    sets = []
    values = []
    if 'name' in data:
        sets.append('name = ?')
        values.append(data['name'].strip())
    if 'description' in data:
        sets.append('description = ?')
        values.append(data['description'])
    if 'permissions' in data:
        sets.append('permissions = ?')
        values.append(json.dumps(data['permissions'] if isinstance(data['permissions'], list) else []))
    values.extend([g.pharmacy_id, rid])
    db.execute(f"UPDATE roles SET {', '.join(sets)} WHERE pharmacy_id = ? AND id = ?", values)
    db.commit()
    return jsonify({'updated': True})

@app.route('/api/roles/<int:rid>', methods=['DELETE'])
@require_auth
@require_admin
def delete_role(rid):
    db = get_db()
    db.execute('DELETE FROM roles WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, rid))
    db.commit()
    return jsonify({'deleted': True})

# --- Store Config ---
@app.route('/api/store-config', methods=['GET'])
@require_auth
def get_store_config():
    db = get_db()
    row = db.execute('SELECT config FROM store_config WHERE pharmacy_id = ?', (g.pharmacy_id,)).fetchone()
    if row and row['config']:
        try:
            return jsonify(json.loads(row['config']))
        except Exception:
            pass
    return jsonify({})

@app.route('/api/store-config', methods=['PUT'])
@require_auth
def update_store_config():
    data = request.get_json()
    config_json = json.dumps(data)
    db = get_db()
    db.execute('INSERT OR REPLACE INTO store_config (pharmacy_id, config, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)', (g.pharmacy_id, config_json))
    db.commit()
    return jsonify(data)


# --- Shifts ---
@app.route('/api/shifts', methods=['GET'])
@require_auth
def get_shifts():
    db = get_db()
    rows = db.execute('SELECT * FROM shifts WHERE pharmacy_id = ? ORDER BY start_time DESC', (g.pharmacy_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/shifts', methods=['POST'])
@require_auth
def create_shift():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('shifts', data)

@app.route('/api/shifts/<int:sid>', methods=['PUT'])
@require_auth
def update_shift(sid):
    data = request.get_json()
    return table_update('shifts', sid, data)

@app.route('/api/shifts/<int:sid>', methods=['DELETE'])
@require_auth
def delete_shift(sid):
    return table_delete('shifts', sid)

# --- Purchase Orders ---
@app.route('/api/purchase-orders', methods=['GET'])
@require_auth
def get_purchase_orders():
    db = get_db()
    rows = db.execute('SELECT * FROM purchase_orders WHERE pharmacy_id = ? ORDER BY date DESC', (g.pharmacy_id,)).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        if row.get('items') and isinstance(row['items'], str):
            try:
                row['items'] = json.loads(row['items'])
            except Exception:
                row['items'] = []
        result.append(row)
    return jsonify(result)

@app.route('/api/purchase-orders', methods=['POST'])
@require_auth
def create_purchase_order():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    if 'items' in data and isinstance(data['items'], list):
        data['items'] = json.dumps(data['items'])
    return table_create('purchase_orders', data)

@app.route('/api/purchase-orders/<int:pid>', methods=['PUT'])
@require_auth
def update_purchase_order(pid):
    data = request.get_json()
    if 'items' in data and isinstance(data['items'], list):
        data['items'] = json.dumps(data['items'])
    return table_update('purchase_orders', pid, data)

@app.route('/api/purchase-orders/<int:pid>', methods=['DELETE'])
@require_auth
def delete_purchase_order(pid):
    return table_delete('purchase_orders', pid)

# --- Bank Records ---
@app.route('/api/bank-records', methods=['GET'])
@require_auth
def get_bank_records():
    db = get_db()
    rows = db.execute('SELECT * FROM bank_records WHERE pharmacy_id = ? ORDER BY date DESC', (g.pharmacy_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/bank-records', methods=['POST'])
@require_auth
def create_bank_record():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('bank_records', data)

@app.route('/api/bank-records/<int:bid>', methods=['PUT'])
@require_auth
def update_bank_record(bid):
    data = request.get_json()
    return table_update('bank_records', bid, data)

@app.route('/api/bank-records/<int:bid>', methods=['DELETE'])
@require_auth
def delete_bank_record(bid):
    return table_delete('bank_records', bid)

# --- Stock Transfers ---
@app.route('/api/stock-transfers', methods=['GET'])
@require_auth
def get_stock_transfers():
    db = get_db()
    rows = db.execute('SELECT * FROM stock_transfers WHERE pharmacy_id = ? ORDER BY date DESC', (g.pharmacy_id,)).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        if row.get('items') and isinstance(row['items'], str):
            try:
                row['items'] = json.loads(row['items'])
            except Exception:
                row['items'] = []
        result.append(row)
    return jsonify(result)

@app.route('/api/stock-transfers', methods=['POST'])
@require_auth
def create_stock_transfer():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    if 'items' in data and isinstance(data['items'], list):
        data['items'] = json.dumps(data['items'])
    return table_create('stock_transfers', data)

@app.route('/api/stock-transfers/<int:tid>', methods=['PUT'])
@require_auth
def update_stock_transfer(tid):
    data = request.get_json()
    if 'items' in data and isinstance(data['items'], list):
        data['items'] = json.dumps(data['items'])
    return table_update('stock_transfers', tid, data)

@app.route('/api/stock-transfers/<int:tid>', methods=['DELETE'])
@require_auth
def delete_stock_transfer(tid):
    return table_delete('stock_transfers', tid)

# --- Stock Counts (stock take) ---
def _stock_count_items(db, count_id):
    rows = db.execute(
        'SELECT * FROM stock_count_items WHERE pharmacy_id = ? AND count_id = ? ORDER BY product_name',
        (g.pharmacy_id, count_id)
    ).fetchall()
    return [dict(r) for r in rows]


def _stock_count_totals(items):
    total_items = len(items)
    counted = 0
    variance = 0.0
    value_variance = 0.0
    for item in items:
        if item.get('counted_qty') is not None:
            counted += 1
        v = float(item.get('variance') or 0)
        variance += v
        value_variance += v * float(item.get('unit_cost') or 0)
    return total_items, counted, round(variance, 3), round(value_variance, 2)


@app.route('/api/stock-counts', methods=['GET'])
@require_auth
def get_stock_counts():
    db = get_db()
    rows = db.execute(
        'SELECT * FROM stock_counts WHERE pharmacy_id = ? ORDER BY id DESC LIMIT 100',
        (g.pharmacy_id,)
    ).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        row['items'] = _stock_count_items(db, row['id'])
        result.append(row)
    return jsonify(result)


@app.route('/api/stock-counts/<int:cid>', methods=['GET'])
@require_auth
def get_stock_count(cid):
    db = get_db()
    row = db.execute(
        'SELECT * FROM stock_counts WHERE pharmacy_id = ? AND id = ?',
        (g.pharmacy_id, cid)
    ).fetchone()
    if not row:
        return jsonify({'error': 'Stock count not found'}), 404
    result = dict(row)
    result['items'] = _stock_count_items(db, cid)
    return jsonify(result)


@app.route('/api/stock-counts', methods=['POST'])
@require_auth
def create_stock_count():
    data = request.get_json(silent=True) or {}
    items = data.get('items') if isinstance(data.get('items'), list) else []
    db = get_db()

    reference = str(data.get('reference', '')).strip()
    if not reference:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        reference = f'SC-{stamp}'

    location = str(data.get('location', '')).strip()
    notes = str(data.get('notes', '')).strip()
    username = request.headers.get('X-Username', '')

    try:
        cursor = db.execute(
            'INSERT INTO stock_counts (pharmacy_id, reference, location, status, counted_by, notes) VALUES (?, ?, ?, ?, ?, ?)',
            (g.pharmacy_id, reference, location, 'draft', username, notes)
        )
        count_id = cursor.lastrowid
        for item in items:
            system_qty = float(item.get('system_qty') or 0)
            counted_qty = item.get('counted_qty')
            counted_qty = float(counted_qty) if counted_qty not in (None, '') else None
            variance = round((counted_qty - system_qty), 3) if counted_qty is not None else 0
            db.execute(
                'INSERT INTO stock_count_items (pharmacy_id, count_id, product_id, product_name, sku, location, batch_number, expiry_date, system_qty, counted_qty, variance, unit_cost) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    g.pharmacy_id, count_id,
                    item.get('product_id'),
                    str(item.get('product_name', '')),
                    str(item.get('sku', '')),
                    str(item.get('location', '') or location),
                    item.get('batch_number'),
                    item.get('expiry_date'),
                    system_qty,
                    counted_qty,
                    variance,
                    float(item.get('unit_cost') or 0)
                )
            )
        totals = _stock_count_totals(_stock_count_items(db, count_id))
        db.execute(
            'UPDATE stock_counts SET total_items = ?, counted_items = ?, total_variance = ?, value_variance = ? WHERE pharmacy_id = ? AND id = ?',
            (totals[0], totals[1], totals[2], totals[3], g.pharmacy_id, count_id)
        )
        db.commit()
        return jsonify({'created': True, 'id': count_id, 'reference': reference}), 201
    except Exception as e:
        return jsonify({'error': f'Could not save the stock count: {str(e)}'}), 500


@app.route('/api/stock-counts/<int:cid>', methods=['PUT'])
@require_auth
def update_stock_count(cid):
    data = request.get_json(silent=True) or {}
    db = get_db()
    existing = db.execute(
        'SELECT * FROM stock_counts WHERE pharmacy_id = ? AND id = ?',
        (g.pharmacy_id, cid)
    ).fetchone()
    if not existing:
        return jsonify({'error': 'Stock count not found'}), 404
    if existing['applied']:
        return jsonify({'error': 'This count has already been applied to stock'}), 400

    items = data.get('items') if isinstance(data.get('items'), list) else None
    if items is not None:
        db.execute('DELETE FROM stock_count_items WHERE pharmacy_id = ? AND count_id = ?', (g.pharmacy_id, cid))
        location = str(data.get('location', existing['location'] or '')).strip()
        for item in items:
            system_qty = float(item.get('system_qty') or 0)
            counted_qty = item.get('counted_qty')
            counted_qty = float(counted_qty) if counted_qty not in (None, '') else None
            variance = round((counted_qty - system_qty), 3) if counted_qty is not None else 0
            db.execute(
                'INSERT INTO stock_count_items (pharmacy_id, count_id, product_id, product_name, sku, location, batch_number, expiry_date, system_qty, counted_qty, variance, unit_cost) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    g.pharmacy_id, cid,
                    item.get('product_id'),
                    str(item.get('product_name', '')),
                    str(item.get('sku', '')),
                    str(item.get('location', '') or location),
                    item.get('batch_number'),
                    item.get('expiry_date'),
                    system_qty,
                    counted_qty,
                    variance,
                    float(item.get('unit_cost') or 0)
                )
            )

    sets = []
    values = []
    for field in ('reference', 'location', 'notes', 'status'):
        if field in data and data[field] is not None:
            sets.append(f'{field} = ?')
            values.append(str(data[field]).strip())
    if sets:
        db.execute(f"UPDATE stock_counts SET {', '.join(sets)} WHERE pharmacy_id = ? AND id = ?", values + [g.pharmacy_id, cid])

    totals = _stock_count_totals(_stock_count_items(db, cid))
    db.execute(
        'UPDATE stock_counts SET total_items = ?, counted_items = ?, total_variance = ?, value_variance = ? WHERE pharmacy_id = ? AND id = ?',
        (totals[0], totals[1], totals[2], totals[3], g.pharmacy_id, cid)
    )
    db.commit()
    result = dict(db.execute('SELECT * FROM stock_counts WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, cid)).fetchone())
    result['items'] = _stock_count_items(db, cid)
    return jsonify({'updated': True, 'count': result})


@app.route('/api/stock-counts/<int:cid>/apply', methods=['POST'])
@require_auth
def apply_stock_count(cid):
    """Post the counted quantities to product stock and close the count."""
    db = get_db()
    count = db.execute(
        'SELECT * FROM stock_counts WHERE pharmacy_id = ? AND id = ?',
        (g.pharmacy_id, cid)
    ).fetchone()
    if not count:
        return jsonify({'error': 'Stock count not found'}), 404
    if count['applied']:
        return jsonify({'error': 'This count has already been applied to stock'}), 400

    items = _stock_count_items(db, cid)
    counted = [i for i in items if i.get('counted_qty') is not None]
    if not counted:
        return jsonify({'error': 'Enter at least one counted quantity before applying'}), 400

    location = (count['location'] or '').strip()
    username = request.headers.get('X-Username', '')
    applied = 0
    try:
        for item in counted:
            product_id = item.get('product_id')
            counted_qty = float(item.get('counted_qty') or 0)
            if product_id:
                db.execute(
                    'UPDATE products SET stock = ? WHERE pharmacy_id = ? AND id = ?',
                    (counted_qty, g.pharmacy_id, product_id)
                )
            if location:
                inv = db.execute(
                    'SELECT id FROM inventory WHERE pharmacy_id = ? AND product_id = ? AND location = ?',
                    (g.pharmacy_id, product_id, location)
                ).fetchone()
                if not inv:
                    inv = db.execute(
                        'SELECT id FROM inventory WHERE pharmacy_id = ? AND product_id = ? AND location IS NULL',
                        (g.pharmacy_id, product_id)
                    ).fetchone()
                if inv:
                    db.execute(
                        'UPDATE inventory SET quantity = ? WHERE pharmacy_id = ? AND id = ?',
                        (counted_qty, g.pharmacy_id, inv['id'])
                    )
                else:
                    db.execute(
                        'INSERT INTO inventory (pharmacy_id, product_id, quantity, location, cost_price, selling_price, last_restocked) '
                        'VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)',
                        (g.pharmacy_id, product_id, counted_qty, location,
                         float(item.get('unit_cost') or 0), 0)
                    )
            applied += 1
        totals = _stock_count_totals(items)
        db.execute(
            'UPDATE stock_counts SET status = ?, applied = 1, counted_items = ?, total_variance = ?, value_variance = ?, completed_at = ? '
            'WHERE pharmacy_id = ? AND id = ?',
            ('completed', totals[1], totals[2], totals[3], datetime.now().isoformat(), g.pharmacy_id, cid)
        )
        db.execute(
            'INSERT INTO audit_log (pharmacy_id, user_name, action, entity_type, entity_id, details, ip_address) VALUES (?,?,?,?,?,?,?)',
            (g.pharmacy_id, username, 'stock_count_applied', 'stock_count', cid,
             f'{applied} product(s) adjusted, variance {totals[2]}', request.remote_addr)
        )
        db.commit()
        return jsonify({
            'applied': True,
            'id': cid,
            'products_updated': applied,
            'total_variance': totals[2],
            'value_variance': totals[3]
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': f'Could not apply the stock count: {str(e)}'}), 500


@app.route('/api/stock-counts/<int:cid>', methods=['DELETE'])
@require_auth
def delete_stock_count(cid):
    db = get_db()
    db.execute('DELETE FROM stock_count_items WHERE pharmacy_id = ? AND count_id = ?', (g.pharmacy_id, cid))
    db.execute('DELETE FROM stock_counts WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, cid))
    db.commit()
    return jsonify({'deleted': True})


# --- Tax Rules ---
@app.route('/api/tax-rules', methods=['GET'])
@require_auth
def get_tax_rules():
    db = get_db()
    rows = db.execute('SELECT * FROM tax_rules WHERE pharmacy_id = ?', (g.pharmacy_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/tax-rules', methods=['POST'])
@require_auth
def create_tax_rule():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('tax_rules', data)

@app.route('/api/tax-rules/<int:tid>', methods=['PUT'])
@require_auth
def update_tax_rule(tid):
    data = request.get_json()
    return table_update('tax_rules', tid, data)

@app.route('/api/tax-rules/<int:tid>', methods=['DELETE'])
@require_auth
def delete_tax_rule(tid):
    return table_delete('tax_rules', tid)

# --- Expiry Batches ---
@app.route('/api/expiry-batches', methods=['GET'])
@require_auth
def get_expiry_batches():
    db = get_db()
    rows = db.execute('SELECT * FROM expiry_batches WHERE pharmacy_id = ? ORDER BY expiry_date ASC', (g.pharmacy_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/expiry-batches', methods=['POST'])
@require_auth
def create_expiry_batch():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('expiry_batches', data)

@app.route('/api/expiry-batches/<int:bid>', methods=['PUT'])
@require_auth
def update_expiry_batch(bid):
    data = request.get_json()
    return table_update('expiry_batches', bid, data)

@app.route('/api/expiry-batches/<int:bid>', methods=['DELETE'])
@require_auth
def delete_expiry_batch(bid):
    return table_delete('expiry_batches', bid)

# --- Prescriptions ---
@app.route('/api/prescriptions', methods=['GET'])
@require_auth
def get_prescriptions():
    db = get_db()
    rows = db.execute('SELECT * FROM prescriptions WHERE pharmacy_id = ? ORDER BY date DESC', (g.pharmacy_id,)).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        if row.get('items') and isinstance(row['items'], str):
            try:
                row['items'] = json.loads(row['items'])
            except Exception:
                row['items'] = []
        result.append(row)
    return jsonify(result)

@app.route('/api/prescriptions', methods=['POST'])
@require_auth
def create_prescription():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    if 'items' in data and isinstance(data['items'], list):
        data['items'] = json.dumps(data['items'])
    return table_create('prescriptions', data)

@app.route('/api/prescriptions/<int:pid>', methods=['PUT'])
@require_auth
def update_prescription(pid):
    data = request.get_json()
    if 'items' in data and isinstance(data['items'], list):
        data['items'] = json.dumps(data['items'])
    return table_update('prescriptions', pid, data)

@app.route('/api/prescriptions/<int:pid>', methods=['DELETE'])
@require_auth
def delete_prescription(pid):
    return table_delete('prescriptions', pid)

# --- Audit Log ---
@app.route('/api/audit-log', methods=['GET'])
@require_auth
def get_audit_log():
    db = get_db()
    rows = db.execute('SELECT * FROM audit_log WHERE pharmacy_id = ? ORDER BY created_at DESC', (g.pharmacy_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/audit-log', methods=['POST'])
@require_auth
def create_audit_log():
    data = request.get_json()
    data['pharmacy_id'] = g.pharmacy_id
    return table_create('audit_log', data)

# ========== Admin Panel ==========

# Canonical catalog of application pages. Admins can rename, reorder,
# re-group, show or hide each page from the Admin Panel.
# 'module' groups pages so a business type can switch off whole areas
# (for example a restaurant does not need prescriptions or expiry batches).
PAGE_CATALOG = [
    {'key': 'index.html', 'label': 'Home', 'group': 'Main', 'icon': 'fa-home', 'module': 'core'},
    {'key': 'dashboard.html', 'label': 'Dashboard', 'group': 'Main', 'icon': 'fa-home', 'module': 'core'},
    {'key': 'sales.html', 'label': 'SALES', 'group': 'Main', 'icon': 'fa-shopping-cart', 'module': 'core'},
    {'key': 'suspended-sales.html', 'label': 'Suspended Sales', 'group': 'Main', 'icon': 'fa-pause', 'module': 'core'},
    {'key': 'variations.html', 'label': 'Add Product', 'group': 'Main', 'icon': 'fa-plus-circle', 'module': 'stock'},
    {'key': 'inventory.html', 'label': 'Inventory', 'group': 'Main', 'icon': 'fa-boxes', 'module': 'stock'},
    {'key': 'receiving.html', 'label': 'Receiving', 'group': 'Main', 'icon': 'fa-file-import', 'module': 'stock'},
    {'key': 'reports.html', 'label': 'Reports', 'group': 'Main', 'icon': 'fa-chart-bar', 'module': 'core'},

    {'key': 'customers.html', 'label': 'Customers', 'group': 'Customers', 'icon': 'fa-users', 'module': 'crm'},
    {'key': 'suppliers.html', 'label': 'Suppliers', 'group': 'Stock', 'icon': 'fa-truck', 'module': 'stock'},
    {'key': 'locations.html', 'label': 'Locations', 'group': 'Stock', 'icon': 'fa-store', 'module': 'stock'},
    {'key': 'product-variations.html', 'label': 'Product Variations', 'group': 'Stock', 'icon': 'fa-layer-group', 'module': 'stock'},

    {'key': 'prescriptions.html', 'label': 'Prescriptions / Rx', 'group': 'Pharmacy', 'icon': 'fa-prescription', 'module': 'pharmacy'},
    {'key': 'expiry-alerts.html', 'label': 'Expiry & Batch Alerts', 'group': 'Pharmacy', 'icon': 'fa-triangle-exclamation', 'module': 'expiry'},
    {'key': 'drug-categories.html', 'label': 'Drug Categories', 'group': 'Pharmacy', 'icon': 'fa-tags', 'module': 'pharmacy'},

    {'key': 'payments.html', 'label': 'Payments', 'group': 'Finance', 'icon': 'fa-credit-card', 'module': 'finance'},
    {'key': 'store_account_payment.html', 'label': 'Store Account', 'group': 'Finance', 'icon': 'fa-wallet', 'module': 'finance'},
    {'key': 'bank-reconciliation.html', 'label': 'Bank Reconciliation', 'group': 'Finance', 'icon': 'fa-building-columns', 'module': 'finance'},
    {'key': 'tax-settings.html', 'label': 'Tax & Vat', 'group': 'Finance', 'icon': 'fa-percent', 'module': 'finance'},
    {'key': 'promo-engine.html', 'label': 'Promos & Discounts', 'group': 'Finance', 'icon': 'fa-tags', 'module': 'finance'},
    {'key': 'expenses.html', 'label': 'Expenses', 'group': 'Finance', 'icon': 'fa-receipt', 'module': 'finance'},
    {'key': 'invoices.html', 'label': 'Invoices', 'group': 'Finance', 'icon': 'fa-file-invoice', 'module': 'finance'},
    {'key': 'purchase-orders.html', 'label': 'Purchase Orders', 'group': 'Finance', 'icon': 'fa-file-invoice-dollar', 'module': 'stock'},

    {'key': 'employees.html', 'label': 'Employees', 'group': 'Operations', 'icon': 'fa-user-tie', 'module': 'admin'},
    {'key': 'user-roles.html', 'label': 'User Roles', 'group': 'Operations', 'icon': 'fa-user-shield', 'module': 'admin'},
    {'key': 'appointments.html', 'label': 'Appointments', 'group': 'Operations', 'icon': 'fa-calendar', 'module': 'crm'},
    {'key': 'shifts.html', 'label': 'Shift Manager', 'group': 'Operations', 'icon': 'fa-clock', 'module': 'core'},
    {'key': 'receipt.html', 'label': 'Receipt', 'group': 'Operations', 'icon': 'fa-receipt', 'module': 'core'},
    {'key': 'todays-receipts.html', 'label': "Today's Receipts", 'group': 'Operations', 'icon': 'fa-receipt', 'module': 'core'},
    {'key': 'audit.html', 'label': 'Audit Log', 'group': 'Operations', 'icon': 'fa-clipboard-list', 'module': 'admin'},
    {'key': 'giftcards.html', 'label': 'Gift Cards', 'group': 'Operations', 'icon': 'fa-gift', 'module': 'crm'},
    {'key': 'deliveries.html', 'label': 'Deliveries', 'group': 'Operations', 'icon': 'fa-truck-loading', 'module': 'stock'},
    {'key': 'cashier-closeout.html', 'label': 'Cashier Closeout', 'group': 'Operations', 'icon': 'fa-calculator', 'module': 'core'},
    {'key': 'daily-summary.html', 'label': 'Daily Sales Summary', 'group': 'Operations', 'icon': 'fa-calendar-day', 'module': 'core'},
    {'key': 'sales-returns.html', 'label': 'Sales Returns', 'group': 'Operations', 'icon': 'fa-rotate-left', 'module': 'stock'},
    {'key': 'stock-transfer.html', 'label': 'Stock Transfer', 'group': 'Operations', 'icon': 'fa-truck-ramp-box', 'module': 'stock'},
    {'key': 'stock-count.html', 'label': 'Stock Count', 'group': 'Operations', 'icon': 'fa-clipboard-check', 'module': 'stock'},
    {'key': 'messages.html', 'label': 'Messages', 'group': 'Operations', 'icon': 'fa-envelope', 'module': 'core'},

    {'key': 'audit-log.html', 'label': 'Audit Log', 'group': 'Reports', 'icon': 'fa-clipboard-list', 'module': 'admin'},
    {'key': 'backups.html', 'label': 'System Backups', 'group': 'Reports', 'icon': 'fa-download', 'module': 'admin'},
    {'key': 'config.html', 'label': 'Store Config', 'group': 'Reports', 'icon': 'fa-cog', 'module': 'admin'},
    {'key': 'customer-history.html', 'label': 'Customer History', 'group': 'Reports', 'icon': 'fa-user-clock', 'module': 'crm'},

    {'key': 'admin.html', 'label': 'Admin Panel', 'group': 'Administration', 'icon': 'fa-shield-halved', 'module': 'admin', 'admin_only': True},

    {'key': 'login.html', 'label': 'Logout', 'group': 'Session', 'icon': 'fa-sign-out-alt', 'module': 'session'},
]

# Business types. Each type enables a set of modules, and the admin can
# fine-tune the module switches for the business.
BUSINESS_TYPES = {
    'general': {'label': 'General Business', 'icon': 'fa-briefcase', 'modules': ['core', 'stock', 'crm', 'finance', 'admin', 'session']},
    'pharmacy': {'label': 'Pharmacy / Health Store', 'icon': 'fa-clinic-medical', 'modules': ['core', 'stock', 'crm', 'finance', 'pharmacy', 'expiry', 'admin', 'session']},
    'retail': {'label': 'Retail Store', 'icon': 'fa-store', 'modules': ['core', 'stock', 'crm', 'finance', 'admin', 'session']},
    'supermarket': {'label': 'Supermarket', 'icon': 'fa-cart-shopping', 'modules': ['core', 'stock', 'crm', 'finance', 'admin', 'session']},
    'boutique': {'label': 'Boutique / Fashion', 'icon': 'fa-shirt', 'modules': ['core', 'stock', 'crm', 'finance', 'admin', 'session']},
    'electronics': {'label': 'Electronics / Gadgets', 'icon': 'fa-mobile-screen', 'modules': ['core', 'stock', 'crm', 'finance', 'admin', 'session']},
    'hardware': {'label': 'Hardware / Building Materials', 'icon': 'fa-hammer', 'modules': ['core', 'stock', 'crm', 'finance', 'admin', 'session']},
    'restaurant': {'label': 'Restaurant / Cafe', 'icon': 'fa-utensils', 'modules': ['core', 'crm', 'finance', 'admin', 'session']},
    'services': {'label': 'Services / Salon / Clinic', 'icon': 'fa-scissors', 'modules': ['core', 'crm', 'finance', 'admin', 'session']},
    'other': {'label': 'Other Business', 'icon': 'fa-ellipsis', 'modules': ['core', 'stock', 'crm', 'finance', 'admin', 'session']},
}

BUSINESS_MODULES = [
    {'key': 'core', 'label': 'Sales & Operations', 'icon': 'fa-cash-register', 'description': 'Point of sale, dashboard, receipts, shifts, messages'},
    {'key': 'stock', 'label': 'Products & Stock', 'icon': 'fa-boxes', 'description': 'Products, inventory, receiving, suppliers, deliveries, purchase orders'},
    {'key': 'crm', 'label': 'Customers & Appointments', 'icon': 'fa-users', 'description': 'Customers, history, appointments, gift cards'},
    {'key': 'finance', 'label': 'Finance', 'icon': 'fa-chart-pie', 'description': 'Payments, expenses, invoices, tax, promos, bank reconciliation'},
    {'key': 'pharmacy', 'label': 'Pharmacy Only', 'icon': 'fa-prescription', 'description': 'Prescriptions and drug categories'},
    {'key': 'expiry', 'label': 'Expiry & Batches', 'icon': 'fa-triangle-exclamation', 'description': 'Expiry alerts and batch tracking'},
    {'key': 'admin', 'label': 'Administration', 'icon': 'fa-user-shield', 'description': 'Staff, roles, audit log, backups, settings, admin panel'},
    {'key': 'session', 'label': 'Session', 'icon': 'fa-right-from-bracket', 'description': 'Sign out'}
]

BUSINESS_MODULES_BY_KEY = {m['key']: m for m in BUSINESS_MODULES}

# Sales and sign out are always available so a business can never lock itself out.
ALWAYS_ON_MODULES = ('core', 'session')


def _normalise_modules(raw, fallback=None):
    """Clean a module list coming from JSON, a string or a form payload."""
    fallback = list(fallback or [])
    if raw is None:
        return fallback
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = [part.strip() for part in raw.split(',') if part.strip()]
    if not isinstance(raw, list):
        return fallback
    cleaned = []
    for item in raw:
        key = str(item).strip().lower()
        if key in BUSINESS_MODULES_BY_KEY and key not in cleaned:
            cleaned.append(key)
    for key in ALWAYS_ON_MODULES:
        if key not in cleaned:
            cleaned.append(key)
    order = {m['key']: i for i, m in enumerate(BUSINESS_MODULES)}
    return sorted(cleaned, key=lambda k: order.get(k, 99))


def _business_modules_for(db, pharmacy_id):
    """Effective module list for a tenant (explicit override or type default)."""
    row = db.execute(
        'SELECT business_type, business_modules FROM pharmacies WHERE id = ?',
        (pharmacy_id,)
    ).fetchone()
    business_type = 'pharmacy'
    raw_modules = None
    if row:
        business_type = (row['business_type'] or 'pharmacy').strip().lower()
        raw_modules = row['business_modules']
    if business_type not in BUSINESS_TYPES:
        business_type = 'other'
    default = list(BUSINESS_TYPES[business_type]['modules'])
    if raw_modules is None or raw_modules == '':
        return _normalise_modules(default, default)
    return _normalise_modules(raw_modules, default)


def _business_payload(db, pharmacy_id, pharmacy_row=None):
    """Business details returned with logins and profile calls."""
    if pharmacy_row is None:
        pharmacy_row = db.execute('SELECT * FROM pharmacies WHERE id = ?', (pharmacy_id,)).fetchone()
    row = dict(pharmacy_row) if pharmacy_row else {}
    business_type = (row.get('business_type') or 'pharmacy').strip().lower()
    if business_type not in BUSINESS_TYPES:
        business_type = 'other'
    modules = _business_modules_for(db, pharmacy_id)
    return {
        'id': row.get('id'),
        'name': row.get('name', ''),
        'api_key': row.get('api_key', ''),
        'address': row.get('address', ''),
        'phone': row.get('phone', ''),
        'email': row.get('email', ''),
        'business_type': business_type,
        'business_label': BUSINESS_TYPES[business_type]['label'],
        'business_icon': BUSINESS_TYPES[business_type]['icon'],
        'modules': modules
    }

# Page access presets per staff role. None means "every page".
ROLE_PAGE_PRESETS = {
    'admin': None,
    'manager': [
        'index.html', 'dashboard.html', 'sales.html', 'suspended-sales.html', 'variations.html',
        'inventory.html', 'receiving.html', 'reports.html', 'customers.html', 'suppliers.html',
        'locations.html', 'product-variations.html', 'prescriptions.html', 'expiry-alerts.html',
        'drug-categories.html', 'payments.html', 'store_account_payment.html', 'bank-reconciliation.html',
        'tax-settings.html', 'promo-engine.html', 'expenses.html', 'invoices.html', 'purchase-orders.html',
        'employees.html', 'appointments.html', 'shifts.html', 'receipt.html', 'todays-receipts.html',
        'audit.html', 'giftcards.html', 'deliveries.html', 'cashier-closeout.html', 'daily-summary.html',
        'sales-returns.html', 'stock-transfer.html', 'stock-count.html', 'messages.html', 'customer-history.html'
    ],
    'staff': [
        'index.html', 'dashboard.html', 'sales.html', 'suspended-sales.html', 'variations.html',
        'inventory.html', 'receiving.html', 'customers.html', 'locations.html', 'product-variations.html',
        'prescriptions.html', 'expiry-alerts.html', 'drug-categories.html', 'payments.html',
        'store_account_payment.html', 'receipt.html', 'todays-receipts.html', 'giftcards.html',
        'deliveries.html', 'appointments.html', 'sales-returns.html', 'stock-count.html', 'messages.html',
        'customer-history.html'
    ],
    'cashier': [
        'index.html', 'dashboard.html', 'sales.html', 'suspended-sales.html', 'customers.html',
        'receipt.html', 'todays-receipts.html', 'payments.html', 'store_account_payment.html',
        'giftcards.html', 'appointments.html', 'deliveries.html'
    ]
}

# Roles offered when creating an account
STAFF_ROLE_PRESETS = ['admin', 'manager', 'staff', 'cashier']


def _parse_page_access(raw):
    if raw is None or raw == '':
        return None
    if isinstance(raw, list):
        return [str(p) for p in raw]
    try:
        parsed = json.loads(raw)
        return [str(p) for p in parsed] if isinstance(parsed, list) else None
    except Exception:
        return None


def log_admin_action(action, entity_type, entity_id, details=''):
    try:
        db = get_db()
        db.execute(
            'INSERT INTO audit_log (pharmacy_id, user_id, user_name, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (g.pharmacy_id, g.user.get('id'), g.user.get('username'), action, entity_type, str(entity_id), details, request.remote_addr)
        )
        db.commit()
    except Exception:
        pass


def _admin_count_users(db, where='1=1', params=()):
    row = db.execute(f'SELECT COUNT(*) as c FROM users WHERE pharmacy_id = ? AND {where}', (g.pharmacy_id,) + tuple(params)).fetchone()
    return row['c'] if row else 0


@app.route('/api/admin/overview', methods=['GET'])
@require_auth
@require_admin
def admin_overview():
    db = get_db()
    settings = db.execute('SELECT * FROM page_settings WHERE pharmacy_id = ?', (g.pharmacy_id,)).fetchall()
    overrides = {r['page_key']: dict(r) for r in settings}
    active_modules = _business_modules_for(db, g.pharmacy_id)
    enabled = 0
    for i, item in enumerate(PAGE_CATALOG):
        ov = overrides.get(item['key'])
        module_on = item.get('module', 'core') in active_modules
        if module_on and (not ov or ov.get('enabled', 1)):
            enabled += 1
    total_pages = len(PAGE_CATALOG)
    audit_row = db.execute('SELECT COUNT(*) as c FROM audit_log WHERE pharmacy_id = ?', (g.pharmacy_id,)).fetchone()
    role_row = db.execute('SELECT COUNT(*) as c FROM roles WHERE pharmacy_id = ?', (g.pharmacy_id,)).fetchone()
    recent = db.execute(
        'SELECT id, user_name, action, entity_type, entity_id, details, created_at FROM audit_log WHERE pharmacy_id = ? ORDER BY created_at DESC, id DESC LIMIT 8',
        (g.pharmacy_id,)
    ).fetchall()
    business = _business_payload(db, g.pharmacy_id, g.pharmacy)
    return jsonify({
        'users': _admin_count_users(db),
        'active_users': _admin_count_users(db, 'COALESCE(active, 1) = 1'),
        'disabled_users': _admin_count_users(db, 'COALESCE(active, 1) = 0'),
        'admins': _admin_count_users(db, "LOWER(COALESCE(role, '')) IN ('admin', 'administrator', 'owner', 'super_admin', 'superadmin')"),
        'roles': role_row['c'] if role_row else 0,
        'pages_total': total_pages,
        'pages_enabled': enabled,
        'pages_disabled': total_pages - enabled,
        'audit_entries': audit_row['c'] if audit_row else 0,
        'recent_activity': [dict(r) for r in recent],
        'pharmacy': {'id': g.pharmacy_id, 'name': g.pharmacy['name']},
        'business': {
            'id': business['id'],
            'name': business['name'],
            'business_type': business['business_type'],
            'business_label': business['business_label'],
            'business_icon': business['business_icon'],
            'modules': business['modules']
        },
        'admin_user': {'id': g.user.get('id'), 'username': g.user.get('username'), 'name': g.user.get('name')}
    })


@app.route('/api/business-types', methods=['GET'])
def list_business_types():
    """Public catalog used by the registration form."""
    return jsonify({
        'types': [
            {'key': key, 'label': value['label'], 'icon': value['icon'], 'modules': value['modules']}
            for key, value in BUSINESS_TYPES.items()
        ],
        'modules': BUSINESS_MODULES,
        'max_accounts': MAX_ACCOUNTS_PER_STORE,
        'account_roles': sorted(STORE_ROLES)
    })


@app.route('/api/business-profile', methods=['GET'])
@require_auth
def business_profile():
    db = get_db()
    profile = _business_payload(db, g.pharmacy_id, g.pharmacy)
    profile['module_catalog'] = BUSINESS_MODULES
    profile['business_types'] = [
        {'key': key, 'label': value['label'], 'icon': value['icon'], 'modules': value['modules']}
        for key, value in BUSINESS_TYPES.items()
    ]
    return jsonify(profile)


@app.route('/api/business-profile', methods=['PUT'])
@require_auth
@require_admin
def update_business_profile():
    data = request.get_json(silent=True) or {}
    db = get_db()
    sets = []
    values = []

    business_type = str(data.get('business_type', '')).strip().lower()
    if business_type:
        if business_type not in BUSINESS_TYPES:
            return jsonify({'error': 'Unknown business type'}), 400
        sets.append('business_type = ?')
        values.append(business_type)

    name = str(data.get('name', '')).strip()
    if name:
        sets.append('name = ?')
        values.append(name)

    for field in ('address', 'phone', 'email'):
        if field in data:
            sets.append(f'{field} = ?')
            values.append(str(data.get(field) or ''))

    modules = data.get('modules')
    if modules is not None:
        sets.append('business_modules = ?')
        values.append(json.dumps(_normalise_modules(modules, [])))

    if sets:
        db.execute(f"UPDATE pharmacies SET {', '.join(sets)} WHERE id = ?", values + [g.pharmacy_id])
        db.commit()
        log_admin_action('update_business', 'business', g.pharmacy_id,
                         f"type={business_type or 'unchanged'} name={name or 'unchanged'}")

    profile = _business_payload(db, g.pharmacy_id)
    profile['module_catalog'] = BUSINESS_MODULES
    profile['business_types'] = [
        {'key': key, 'label': value['label'], 'icon': value['icon'], 'modules': value['modules']}
        for key, value in BUSINESS_TYPES.items()
    ]
    return jsonify({'updated': True, 'profile': profile})


@app.route('/api/admin/pages', methods=['GET'])
@require_auth
def admin_list_pages():
    db = get_db()
    rows = db.execute('SELECT * FROM page_settings WHERE pharmacy_id = ?', (g.pharmacy_id,)).fetchall()
    overrides = {r['page_key']: dict(r) for r in rows}
    active_modules = _business_modules_for(db, g.pharmacy_id)
    pages = []
    for i, item in enumerate(PAGE_CATALOG):
        ov = overrides.get(item['key'])
        module = item.get('module', 'core')
        pages.append({
            'key': item['key'],
            'label': (ov.get('label') if ov and ov.get('label') else item['label']),
            'group': (ov.get('group_name') if ov and ov.get('group_name') else item['group']),
            'icon': (ov.get('icon') if ov and ov.get('icon') else item['icon']),
            'enabled': bool(ov.get('enabled', 1)) if ov else True,
            'sort_order': ov.get('sort_order', i) if ov else i,
            'admin_only': item.get('admin_only', False),
            'module': module,
            'module_label': BUSINESS_MODULES_BY_KEY.get(module, {}).get('label', module),
            'module_enabled': module in active_modules,
            'default_label': item['label'],
            'default_group': item['group'],
            'default_icon': item['icon'],
            'customised': bool(ov)
        })
    return jsonify(pages)


@app.route('/api/admin/pages/<path:page_key>', methods=['PUT'])
@require_auth
@require_admin
def admin_update_page(page_key):
    catalog = next((p for p in PAGE_CATALOG if p['key'] == page_key), None)
    if not catalog:
        return jsonify({'error': 'Unknown page'}), 404
    data = request.get_json(silent=True) or {}
    db = get_db()
    existing = db.execute(
        'SELECT * FROM page_settings WHERE pharmacy_id = ? AND page_key = ?',
        (g.pharmacy_id, page_key)
    ).fetchone()
    label = (data.get('label') if data.get('label') is not None else (existing['label'] if existing else catalog['label'])) or catalog['label']
    group = (data.get('group') if data.get('group') is not None else (existing['group_name'] if existing else catalog['group'])) or catalog['group']
    icon = (data.get('icon') if data.get('icon') is not None else (existing['icon'] if existing else catalog['icon'])) or catalog['icon']
    enabled = 1 if data.get('enabled', True) else 0
    sort_order = int(data.get('sort_order', existing['sort_order'] if existing else PAGE_CATALOG.index(catalog)))
    if existing:
        db.execute(
            'UPDATE page_settings SET label = ?, group_name = ?, icon = ?, enabled = ?, sort_order = ?, updated_at = CURRENT_TIMESTAMP WHERE pharmacy_id = ? AND page_key = ?',
            (label, group, icon, enabled, sort_order, g.pharmacy_id, page_key)
        )
    else:
        db.execute(
            'INSERT INTO page_settings (pharmacy_id, page_key, label, group_name, icon, enabled, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (g.pharmacy_id, page_key, label, group, icon, enabled, sort_order)
        )
    db.commit()
    log_admin_action('update_page', 'page', page_key, f'enabled={bool(enabled)} label={label} group={group}')
    return jsonify({
        'updated': True,
        'page': {'key': page_key, 'label': label, 'group': group, 'icon': icon, 'enabled': bool(enabled), 'sort_order': sort_order}
    })


@app.route('/api/admin/pages/reset', methods=['POST'])
@require_auth
@require_admin
def admin_reset_pages():
    db = get_db()
    db.execute('DELETE FROM page_settings WHERE pharmacy_id = ?', (g.pharmacy_id,))
    db.commit()
    log_admin_action('reset_pages', 'page', 'all', 'Restored default page settings')
    return jsonify({'reset': True})


@app.route('/api/admin/users', methods=['GET'])
@require_auth
@require_admin
def admin_list_users():
    db = get_db()
    rows = db.execute(
        'SELECT id, username, name, role, store, email, phone, active, last_login, page_access, created_at FROM users WHERE pharmacy_id = ? ORDER BY id',
        (g.pharmacy_id,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['active'] = d.get('active') is not None and bool(d.get('active'))
        d['page_access'] = _parse_page_access(d.get('page_access'))
        result.append(d)
    return jsonify(result)


@app.route('/api/admin/role-presets', methods=['GET'])
@require_auth
@require_admin
def admin_role_presets():
    all_pages = [p['key'] for p in PAGE_CATALOG]
    presets = {}
    for role in STAFF_ROLE_PRESETS:
        preset = ROLE_PAGE_PRESETS.get(role)
        presets[role] = all_pages if preset is None else list(preset)
    return jsonify({
        'roles': STAFF_ROLE_PRESETS,
        'presets': presets,
        'all_pages': all_pages
    })


@app.route('/api/me/access', methods=['GET'])
@require_auth
def my_access():
    db = get_db()
    username = request.headers.get('X-Username', '')
    user = db.execute(
        'SELECT id, username, name, role, page_access FROM users WHERE pharmacy_id = ? AND username = ?',
        (g.pharmacy_id, username)
    ).fetchone()
    if not user:
        return jsonify({'error': 'User not found'}), 401
    role = str(user['role'] or '').strip().lower()
    is_admin = role in ADMIN_ROLES
    pages = None
    if not is_admin:
        pages = _parse_page_access(user['page_access'])
    modules = _business_modules_for(db, g.pharmacy_id)
    business = _business_payload(db, g.pharmacy_id, g.pharmacy)
    return jsonify({
        'username': user['username'],
        'name': user['name'],
        'role': user['role'],
        'is_admin': is_admin,
        'pages': pages,
        'modules': modules,
        'business': business,
        'business_type': business['business_type'],
        'presets': ROLE_PAGE_PRESETS.get(role)
    })


@app.route('/api/admin/users', methods=['POST'])
@require_auth
@require_admin
def admin_create_user():
    data = request.get_json(silent=True) or {}
    username = str(data.get('username', '')).strip()
    password = str(data.get('password', ''))
    name = str(data.get('name', '')).strip() or username
    role = str(data.get('role', 'staff')).strip() or 'staff'
    store = str(data.get('store', 'main')).strip() or 'main'
    email = str(data.get('email', '')).strip()
    phone = str(data.get('phone', '')).strip()
    active = 1 if data.get('active', True) else 0
    page_access = data.get('page_access', None)
    if page_access is not None and not isinstance(page_access, list):
        page_access = None
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    db = get_db()
    try:
        cursor = db.execute(
            'INSERT INTO users (pharmacy_id, username, password, name, role, store, email, phone, active, page_access) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (g.pharmacy_id, username, password, name, role, store, email, phone, active,
             json.dumps(page_access) if page_access is not None else None)
        )
        db.commit()
        log_admin_action('create_user', 'user', cursor.lastrowid, f'Created account {username} ({role})')
        return jsonify({'created': True, 'id': cursor.lastrowid, 'username': username}), 201
    except IntegrityError:
        return jsonify({'error': 'Username already exists for this pharmacy'}), 400


@app.route('/api/admin/users/<int:uid>', methods=['PUT'])
@require_auth
@require_admin
def admin_update_user(uid):
    data = request.get_json(silent=True) or {}
    db = get_db()
    existing = db.execute('SELECT * FROM users WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, uid)).fetchone()
    if not existing:
        return jsonify({'error': 'User not found'}), 404

    current_role = str(existing['role'] or '').strip().lower()
    was_admin = current_role in ADMIN_ROLES
    target_role = str(data.get('role', existing['role'] or 'staff')).strip() or 'staff'
    target_active = 1 if data.get('active', bool(existing['active'])) else 0
    is_self = str(existing['username']) == str(g.user.get('username'))

    if was_admin and target_role.lower() not in ADMIN_ROLES:
        remaining = _admin_count_users(db, "LOWER(COALESCE(role, '')) IN ('admin', 'administrator', 'owner', 'super_admin', 'superadmin')")
        if remaining <= 1:
            return jsonify({'error': 'Cannot demote the last administrator'}), 400
    if was_admin and not target_active:
        remaining = _admin_count_users(db, "COALESCE(active, 1) = 1 AND LOWER(COALESCE(role, '')) IN ('admin', 'administrator', 'owner', 'super_admin', 'superadmin')")
        if remaining <= 1:
            return jsonify({'error': 'Cannot disable the last administrator'}), 400
    if is_self and not target_active:
        return jsonify({'error': 'You cannot disable your own account'}), 400

    sets = []
    values = []
    if 'name' in data:
        sets.append('name = ?')
        values.append(str(data.get('name') or '').strip())
    if 'username' in data:
        new_username = str(data.get('username') or '').strip()
        if not new_username:
            return jsonify({'error': 'Username is required'}), 400
        sets.append('username = ?')
        values.append(new_username)
    if 'role' in data:
        sets.append('role = ?')
        values.append(target_role)
    if 'store' in data:
        sets.append('store = ?')
        values.append(str(data.get('store') or 'main').strip())
    if 'email' in data:
        sets.append('email = ?')
        values.append(str(data.get('email') or '').strip())
    if 'phone' in data:
        sets.append('phone = ?')
        values.append(str(data.get('phone') or '').strip())
    if 'active' in data:
        sets.append('active = ?')
        values.append(target_active)
    if 'page_access' in data:
        sets.append('page_access = ?')
        pa = data.get('page_access')
        values.append(json.dumps([str(p) for p in pa]) if isinstance(pa, list) else None)
    if data.get('password'):
        if len(str(data['password'])) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        sets.append('password = ?')
        values.append(str(data['password']))
    if not sets:
        return jsonify({'updated': True, 'noop': True})
    values.extend([g.pharmacy_id, uid])
    try:
        db.execute(f"UPDATE users SET {', '.join(sets)} WHERE pharmacy_id = ? AND id = ?", values)
        db.commit()
    except IntegrityError:
        return jsonify({'error': 'Username already exists for this pharmacy'}), 400
    log_admin_action('update_user', 'user', uid, f'Updated account {existing["username"]}')
    return jsonify({'updated': True})


@app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
@require_auth
@require_admin
def admin_delete_user(uid):
    db = get_db()
    existing = db.execute('SELECT * FROM users WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, uid)).fetchone()
    if not existing:
        return jsonify({'error': 'User not found'}), 404
    if str(existing['username']) == str(g.user.get('username')):
        return jsonify({'error': 'You cannot delete your own account'}), 400
    if str(existing['role'] or '').strip().lower() in ADMIN_ROLES:
        remaining = _admin_count_users(db, "LOWER(COALESCE(role, '')) IN ('admin', 'administrator', 'owner', 'super_admin', 'superadmin')")
        if remaining <= 1:
            return jsonify({'error': 'Cannot delete the last administrator'}), 400
    db.execute('DELETE FROM users WHERE pharmacy_id = ? AND id = ?', (g.pharmacy_id, uid))
    db.commit()
    log_admin_action('delete_user', 'user', uid, f'Deleted account {existing["username"]}')
    return jsonify({'deleted': True})


# ========== Marketing Site (public landing page) ==========

@app.route('/api/plans', methods=['GET'])
def list_plans():
    """Public pricing plans shown on the landing page."""
    db = get_db()
    rows = db.execute('SELECT * FROM plans WHERE is_active = 1 ORDER BY sort_order ASC, id ASC').fetchall()
    plans = []
    for row in rows:
        plan = dict(row)
        try:
            plan['features'] = json.loads(plan.get('features') or '[]')
        except Exception:
            plan['features'] = []
        if not isinstance(plan['features'], list):
            plan['features'] = []
        plan['highlight'] = bool(plan.get('highlight'))
        plans.append(plan)
    return jsonify({'plans': plans})


@app.route('/api/testimonials', methods=['GET'])
def list_testimonials():
    """Public customer testimonials shown on the landing page."""
    db = get_db()
    rows = db.execute(
        'SELECT author_name, author_role, business, quote, rating FROM testimonials'
        ' WHERE is_published = 1 ORDER BY sort_order ASC, id ASC'
    ).fetchall()
    return jsonify({'testimonials': [dict(r) for r in rows]})


@app.route('/api/changelog', methods=['GET'])
def list_changelog():
    """Public release notes shown as "Latest updates" on the landing page."""
    db = get_db()
    rows = db.execute(
        'SELECT version, released_on, title, summary, items FROM changelog'
        ' WHERE is_published = 1 ORDER BY sort_order ASC, id DESC'
    ).fetchall()
    entries = []
    for row in rows:
        entry = dict(row)
        try:
            entry['items'] = json.loads(entry.get('items') or '[]')
        except Exception:
            entry['items'] = []
        if not isinstance(entry['items'], list):
            entry['items'] = []
        entries.append(entry)
    return jsonify({'changelog': entries})


@app.route('/api/public/stats', methods=['GET'])
def public_stats():
    """Live numbers for the landing page stats bar."""
    def count(table):
        try:
            row = get_db().execute(f'SELECT COUNT(*) AS c FROM {table}').fetchone()
            return int(row['c'] or 0)
        except Exception:
            return 0
    return jsonify({
        'stores': count('pharmacies'),
        'products': count('products'),
        'transactions': count('sales'),
        'staff': count('users'),
        'branches': count('branches'),
        'modules': len(BUSINESS_MODULES),
        'business_types': len(BUSINESS_TYPES),
        'generated_at': datetime.now().isoformat(),
    })


@app.route('/api/leads', methods=['POST'])
def create_lead():
    """Capture a newsletter / demo request from the landing page."""
    data = request.get_json(silent=True) or {}
    if str(data.get('website') or '').strip():
        return jsonify({'ok': True}), 200  # honeypot: pretend it worked
    email = str(data.get('email') or '').strip().lower()
    if not email or '@' not in email or len(email) > 190:
        return jsonify({'error': 'Enter a valid email address'}), 400
    name = str(data.get('name') or '').strip()[:120]
    pharmacy = str(data.get('pharmacy') or '').strip()[:160]
    message = str(data.get('message') or '').strip()[:2000]
    source = str(data.get('source') or 'landing').strip()[:60]
    db = get_db()
    existing = db.execute('SELECT id FROM leads WHERE email = ?', (email,)).fetchone()
    if existing:
        db.execute(
            'UPDATE leads SET name = ?, pharmacy = ?, message = ?, source = ?, created_at = ? WHERE id = ?',
            (name, pharmacy, message, source, datetime.now().isoformat(), existing['id'])
        )
        db.commit()
        return jsonify({'ok': True, 'updated': True}), 200
    db.execute(
        'INSERT INTO leads (email, name, pharmacy, message, source, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (email, name, pharmacy, message, source, datetime.now().isoformat())
    )
    db.commit()
    return jsonify({'ok': True}), 201


@app.route('/api/admin/plans', methods=['GET'])
@require_auth
@require_admin
def admin_list_plans():
    db = get_db()
    rows = db.execute('SELECT * FROM plans ORDER BY sort_order ASC, id ASC').fetchall()
    plans = []
    for row in rows:
        plan = dict(row)
        try:
            plan['features'] = json.loads(plan.get('features') or '[]')
        except Exception:
            plan['features'] = []
        plans.append(plan)
    return jsonify({'plans': plans})


@app.route('/api/admin/plans', methods=['POST'])
@require_auth
@require_admin
def admin_create_plan():
    data = request.get_json(silent=True) or {}
    name = str(data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Plan name is required'}), 400
    features = data.get('features') or []
    if isinstance(features, str):
        features = [f.strip() for f in features.split('\n') if f.strip()]
    db = get_db()
    cur = db.execute(
        'INSERT INTO plans (key, name, tagline, price_monthly, price_yearly, currency, features, highlight, sort_order, is_active)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (str(data.get('key') or name.lower().replace(' ', '-')),
         name,
         str(data.get('tagline') or ''),
         float(data.get('price_monthly') or 0),
         float(data.get('price_yearly') or 0),
         str(data.get('currency') or 'NGN'),
         json.dumps(features),
         1 if data.get('highlight') else 0,
         int(data.get('sort_order') or 0),
         0 if data.get('is_active') is False else 1)
    )
    db.commit()
    log_admin_action('create_plan', 'plan', cur.lastrowid, f'Created plan {name}')
    return jsonify({'created': True}), 201


@app.route('/api/admin/plans/<int:pid>', methods=['PUT'])
@require_auth
@require_admin
def admin_update_plan(pid):
    data = request.get_json(silent=True) or {}
    existing = get_db().execute('SELECT * FROM plans WHERE id = ?', (pid,)).fetchone()
    if not existing:
        return jsonify({'error': 'Plan not found'}), 404
    features = data.get('features')
    if isinstance(features, str):
        features = [f.strip() for f in features.split('\n') if f.strip()]
    if features is None:
        features = json.loads(existing['features'] or '[]')
    sets, values = [], []
    for field, column in (('name', 'name'), ('tagline', 'tagline'), ('key', 'key'), ('currency', 'currency')):
        if field in data:
            sets.append(f'{column} = ?')
            values.append(str(data.get(field) or ''))
    for field, column in (('price_monthly', 'price_monthly'), ('price_yearly', 'price_yearly'), ('sort_order', 'sort_order')):
        if field in data:
            sets.append(f'{column} = ?')
            values.append(float(data.get(field) or 0))
    if 'features' in data:
        sets.append('features = ?')
        values.append(json.dumps(features))
    if 'highlight' in data:
        sets.append('highlight = ?')
        values.append(1 if data.get('highlight') else 0)
    if 'is_active' in data:
        sets.append('is_active = ?')
        values.append(1 if data.get('is_active') else 0)
    if sets:
        get_db().execute(f"UPDATE plans SET {', '.join(sets)} WHERE id = ?", values + [pid])
        get_db().commit()
    log_admin_action('update_plan', 'plan', pid, f'Updated plan {existing["name"]}')
    return jsonify({'updated': True})


@app.route('/api/admin/plans/<int:pid>', methods=['DELETE'])
@require_auth
@require_admin
def admin_delete_plan(pid):
    db = get_db()
    existing = db.execute('SELECT * FROM plans WHERE id = ?', (pid,)).fetchone()
    if not existing:
        return jsonify({'error': 'Plan not found'}), 404
    db.execute('DELETE FROM plans WHERE id = ?', (pid,))
    db.commit()
    log_admin_action('delete_plan', 'plan', pid, f'Deleted plan {existing["name"]}')
    return jsonify({'deleted': True})


@app.route('/api/admin/testimonials', methods=['GET'])
@require_auth
@require_admin
def admin_list_testimonials():
    rows = get_db().execute('SELECT * FROM testimonials ORDER BY sort_order ASC, id ASC').fetchall()
    return jsonify({'testimonials': [dict(r) for r in rows]})


@app.route('/api/admin/testimonials', methods=['POST'])
@require_auth
@require_admin
def admin_create_testimonial():
    data = request.get_json(silent=True) or {}
    name = str(data.get('author_name') or '').strip()
    quote = str(data.get('quote') or '').strip()
    if not name or not quote:
        return jsonify({'error': 'Author name and quote are required'}), 400
    db = get_db()
    cur = db.execute(
        'INSERT INTO testimonials (author_name, author_role, business, quote, rating, is_published, sort_order)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?)',
        (name,
         str(data.get('author_role') or ''),
         str(data.get('business') or ''),
         quote,
         int(data.get('rating') or 5),
         0 if data.get('is_published') is False else 1,
         int(data.get('sort_order') or 0))
    )
    db.commit()
    log_admin_action('create_testimonial', 'testimonial', cur.lastrowid, f'Added testimonial from {name}')
    return jsonify({'created': True}), 201


@app.route('/api/admin/testimonials/<int:tid>', methods=['PUT'])
@require_auth
@require_admin
def admin_update_testimonial(tid):
    data = request.get_json(silent=True) or {}
    existing = get_db().execute('SELECT * FROM testimonials WHERE id = ?', (tid,)).fetchone()
    if not existing:
        return jsonify({'error': 'Testimonial not found'}), 404
    sets, values = [], []
    for field, column in (('author_name', 'author_name'), ('author_role', 'author_role'), ('business', 'business'), ('quote', 'quote')):
        if field in data:
            sets.append(f'{column} = ?')
            values.append(str(data.get(field) or ''))
    if 'rating' in data:
        sets.append('rating = ?')
        values.append(int(data.get('rating') or 5))
    if 'sort_order' in data:
        sets.append('sort_order = ?')
        values.append(int(data.get('sort_order') or 0))
    if 'is_published' in data:
        sets.append('is_published = ?')
        values.append(1 if data.get('is_published') else 0)
    if sets:
        get_db().execute(f"UPDATE testimonials SET {', '.join(sets)} WHERE id = ?", values + [tid])
        get_db().commit()
    log_admin_action('update_testimonial', 'testimonial', tid, f'Updated testimonial from {existing["author_name"]}')
    return jsonify({'updated': True})


@app.route('/api/admin/testimonials/<int:tid>', methods=['DELETE'])
@require_auth
@require_admin
def admin_delete_testimonial(tid):
    db = get_db()
    existing = db.execute('SELECT * FROM testimonials WHERE id = ?', (tid,)).fetchone()
    if not existing:
        return jsonify({'error': 'Testimonial not found'}), 404
    db.execute('DELETE FROM testimonials WHERE id = ?', (tid,))
    db.commit()
    log_admin_action('delete_testimonial', 'testimonial', tid, f'Deleted testimonial from {existing["author_name"]}')
    return jsonify({'deleted': True})


@app.route('/api/admin/changelog', methods=['GET'])
@require_auth
@require_admin
def admin_list_changelog():
    rows = get_db().execute('SELECT * FROM changelog ORDER BY sort_order ASC, id DESC').fetchall()
    entries = []
    for row in rows:
        entry = dict(row)
        try:
            entry['items'] = json.loads(entry.get('items') or '[]')
        except Exception:
            entry['items'] = []
        entries.append(entry)
    return jsonify({'changelog': entries})


@app.route('/api/admin/changelog', methods=['POST'])
@require_auth
@require_admin
def admin_create_changelog():
    data = request.get_json(silent=True) or {}
    version = str(data.get('version') or '').strip()
    title = str(data.get('title') or '').strip()
    if not version or not title:
        return jsonify({'error': 'Version and title are required'}), 400
    items = data.get('items') or []
    if isinstance(items, str):
        items = [i.strip() for i in items.split('\n') if i.strip()]
    db = get_db()
    cur = db.execute(
        'INSERT INTO changelog (version, released_on, title, summary, items, is_published, sort_order)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?)',
        (version,
         str(data.get('released_on') or ''),
         title,
         str(data.get('summary') or ''),
         json.dumps(items),
         0 if data.get('is_published') is False else 1,
         int(data.get('sort_order') or 0))
    )
    db.commit()
    log_admin_action('create_changelog', 'changelog', cur.lastrowid, f'Added release note {version}')
    return jsonify({'created': True}), 201


@app.route('/api/admin/changelog/<int:cid>', methods=['PUT'])
@require_auth
@require_admin
def admin_update_changelog(cid):
    data = request.get_json(silent=True) or {}
    existing = get_db().execute('SELECT * FROM changelog WHERE id = ?', (cid,)).fetchone()
    if not existing:
        return jsonify({'error': 'Release note not found'}), 404
    items = data.get('items')
    if isinstance(items, str):
        items = [i.strip() for i in items.split('\n') if i.strip()]
    if items is None:
        items = json.loads(existing['items'] or '[]')
    sets, values = [], []
    for field, column in (('version', 'version'), ('released_on', 'released_on'), ('title', 'title'), ('summary', 'summary')):
        if field in data:
            sets.append(f'{column} = ?')
            values.append(str(data.get(field) or ''))
    if 'items' in data:
        sets.append('items = ?')
        values.append(json.dumps(items))
    if 'is_published' in data:
        sets.append('is_published = ?')
        values.append(1 if data.get('is_published') else 0)
    if 'sort_order' in data:
        sets.append('sort_order = ?')
        values.append(int(data.get('sort_order') or 0))
    if sets:
        get_db().execute(f"UPDATE changelog SET {', '.join(sets)} WHERE id = ?", values + [cid])
        get_db().commit()
    log_admin_action('update_changelog', 'changelog', cid, f'Updated release note {existing["version"]}')
    return jsonify({'updated': True})


@app.route('/api/admin/changelog/<int:cid>', methods=['DELETE'])
@require_auth
@require_admin
def admin_delete_changelog(cid):
    db = get_db()
    existing = db.execute('SELECT * FROM changelog WHERE id = ?', (cid,)).fetchone()
    if not existing:
        return jsonify({'error': 'Release note not found'}), 404
    db.execute('DELETE FROM changelog WHERE id = ?', (cid,))
    db.commit()
    log_admin_action('delete_changelog', 'changelog', cid, f'Deleted release note {existing["version"]}')
    return jsonify({'deleted': True})


@app.route('/api/admin/leads', methods=['GET'])
@require_auth
@require_admin
def admin_list_leads():
    rows = get_db().execute('SELECT * FROM leads ORDER BY id DESC LIMIT 500').fetchall()
    return jsonify({'leads': [dict(r) for r in rows]})


# ========== Main ==========

@app.route('/')
def index():
    return send_file(os.path.join(os.path.dirname(__file__), 'login.html'))

@app.route('/<path:filename>')
def serve_static(filename):
    allowed = {'.html', '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.txt', '.xml', '.webmanifest'}
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed:
        return jsonify({'error': 'File type not allowed'}), 403
    filepath = os.path.join(os.path.dirname(__file__), filename)
    if os.path.isfile(filepath):
        return send_file(filepath)
    return jsonify({'error': 'Not found'}), 404

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key, X-Username'
    return response

@app.route('/api/admin/tenants', methods=['OPTIONS'])
@app.route('/api/admin/tenants/<path:path>', methods=['OPTIONS'])
@app.route('/api/admin/payments', methods=['OPTIONS'])
@app.route('/api/platform/admin/plans', methods=['OPTIONS'])
@app.route('/api/platform/admin/plans/<path:path>', methods=['OPTIONS'])
def handle_platform_options(path=''):
    return '', 204

with app.app_context():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

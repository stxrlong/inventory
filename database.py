# database.py
import sqlite3

DB_PATH = 'inventory.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

	# 货品主数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT UNIQUE NOT NULL,
            product_name TEXT NOT NULL
        )
    ''')
    
    # 订单详情表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_date DATE NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            is_completed BOOLEAN DEFAULT 0
        )
    ''')
    
    # 每日出货记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_date DATE NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            shipped_quantity INTEGER NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 支持 dict-like 访问
    return conn
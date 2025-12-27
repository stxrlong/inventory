# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = 'inventory_secret_key_2025'

# ======================
# 数据库初始化（内联，避免导入问题）
# ======================
DB_PATH = 'inventory.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT UNIQUE NOT NULL,
            product_name TEXT NOT NULL
        )
    ''')
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
    conn.row_factory = sqlite3.Row
    return conn

# 初始化数据库（启动时自动创建表）
init_db()

# ======================
# 路由
# ======================

@app.route('/')
def index():
    return redirect(url_for('summary'))

@app.route('/products', methods=['GET', 'POST'])
def products():
    conn = get_db_connection()
    if request.method == 'POST':
        pid = request.form['product_id'].strip()
        pname = request.form['product_name'].strip()
        if pid and pname:
            try:
                conn.execute('''
                    INSERT INTO products (product_id, product_name)
                    VALUES (?, ?)
                ''', (pid, pname))
                conn.commit()
                flash('货品添加成功！', 'success')
            except sqlite3.IntegrityError:
                flash('货品编号已存在！', 'error')
        return redirect(url_for('products'))
    
    product_list = conn.execute('SELECT * FROM products ORDER BY product_id').fetchall()
    conn.close()
    return render_template('products.html', products=product_list, today=date.today().isoformat())

@app.route('/orders', methods=['GET', 'POST'])
def orders():
    conn = get_db_connection()
    
    # === 处理新增订单 ===
    if request.method == 'POST':
        order_date = request.form['order_date']
        product_id = request.form['product_id'].strip()
        product_name = request.form['product_name'].strip()
        try:
            quantity = int(request.form['quantity'])
        except ValueError:
            quantity = 0

        if not product_id or not product_name or quantity <= 0:
            flash('请填写完整信息，数量必须大于0', 'error')
        else:
            conn.execute('''
                INSERT INTO order_details (order_date, product_id, product_name, quantity)
                VALUES (?, ?, ?, ?)
            ''', (order_date, product_id, product_name, quantity))
            conn.commit()
            flash('订单添加成功！', 'success')
        return redirect(url_for('orders'))
    
    # === 查询所有订单 ===
    orders_list = conn.execute('SELECT * FROM order_details ORDER BY order_date DESC').fetchall()
    
    # === 查询每个货品的缺口量（总订单 - 总出货）===
    shortfall_data = {}
    shortfall_rows = conn.execute('''
        SELECT
            od.product_id,
            (SUM(od.quantity) - COALESCE(s.total_shipped, 0)) AS shortfall
        FROM order_details od
        LEFT JOIN (
            SELECT product_id, SUM(shipped_quantity) AS total_shipped
            FROM daily_shipments
            GROUP BY product_id
        ) s ON od.product_id = s.product_id
        GROUP BY od.product_id
    ''').fetchall()
    
    for row in shortfall_rows:
        shortfall_data[row['product_id']] = max(0, row['shortfall'])  # 不显示负数
    
    conn.close()
    
    return render_template(
        'orders.html',
        orders=orders_list,
        today=date.today().isoformat(),
        shortfall_map=shortfall_data  # 传递缺口映射
    )

@app.route('/shipments', methods=['GET', 'POST'])
def shipments():
    conn = get_db_connection()
    
    # 获取所有货品（用于前端搜索）
    all_products = conn.execute('SELECT product_id, product_name FROM products ORDER BY product_id').fetchall()
    
    if request.method == 'POST':
        shipment_date = request.form['shipment_date']
        product_id = request.form['product_id'].strip()
        product_name = request.form['product_name'].strip()
        try:
            shipped_quantity = int(request.form['shipped_quantity'])
        except ValueError:
            shipped_quantity = 0

        if not product_id or not product_name or shipped_quantity <= 0:
            flash('请填写完整信息，出货量必须大于0', 'error')
        else:
            # 插入出货记录（名称可从订单表自动获取，但这里允许手动输入）
            conn.execute('''
                INSERT INTO daily_shipments (shipment_date, product_id, product_name, shipped_quantity)
                VALUES (?, ?, ?, ?)
            ''', (shipment_date, product_id, product_name, shipped_quantity))
            
            # 计算该货品的总订单量和总出货量
            total_order = conn.execute('''
                SELECT SUM(quantity) FROM order_details WHERE product_id = ?
            ''', (product_id,)).fetchone()[0] or 0
            
            total_ship = conn.execute('''
                SELECT SUM(shipped_quantity) FROM daily_shipments WHERE product_id = ?
            ''', (product_id,)).fetchone()[0] or 0
            
            # 如果出货 ≥ 订单，则标记该货品所有订单为完成
            if total_order > 0 and total_ship >= total_order:
                conn.execute('''
                    UPDATE order_details SET is_completed = 1 WHERE product_id = ?
                ''', (product_id,))
            
            conn.commit()
            flash('出货记录已添加，并自动更新订单状态！', 'success')
        return redirect(url_for('shipments'))
    
    shipments_list = conn.execute('SELECT * FROM daily_shipments ORDER BY shipment_date DESC').fetchall()
    conn.close()
    return render_template(
        'shipments.html',
        shipments=shipments_list,
        today=date.today().isoformat(),
        all_products=all_products  # 传给模板
    )

from datetime import date

@app.route('/summary')
def summary():
    conn = get_db_connection()
    
    # 生成动态月份标题，例如 "2025年12月累计出货量"
    current_month_str = date.today().strftime('%Y年%m月累计出货量')
    current_year_month = date.today().strftime('%%Y-%%m')  # 用于SQL查询
    
    query = '''
    SELECT
        od.product_id,
        od.product_name,
        SUM(od.quantity) AS total_order,
        COALESCE(s.total_shipped, 0) AS total_shipped,
        SUM(od.quantity) - COALESCE(s.total_shipped, 0) AS pending,
        COALESCE(s.monthly_shipped, 0) AS monthly_shipped
    FROM order_details od
    LEFT JOIN (
        SELECT
            product_id,
            SUM(shipped_quantity) AS total_shipped,
            SUM(CASE 
                WHEN strftime('%%Y-%%m', shipment_date) = ?
                THEN shipped_quantity ELSE 0 
            END) AS monthly_shipped
        FROM daily_shipments
        GROUP BY product_id
    ) s ON od.product_id = s.product_id
    GROUP BY od.product_id, od.product_name
    ORDER BY od.product_id
    '''
    
    summary_data = conn.execute(query, (current_year_month,)).fetchall()
    conn.close()
    
    return render_template(
        'summary.html',
        summary=summary_data,
        monthly_column_title=current_month_str  # ← 传入动态列名
    )

# ======================
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
from flask import Flask, request, jsonify, session, render_template, render_template_string, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import db
import query_processor
import pymysql


app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_db_connection():
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='foodbot123',
        database='foodbot',
        cursorclass=pymysql.cursors.DictCursor
    )
    return conn


@app.route('/')
def index():
    return render_template('index.html')

def get_username_from_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        return user['username']
    else:
        return None


@app.route('/get_login_status', methods=['GET'])
def get_login_status():
    user_id = session.get('user_id')
    if user_id:
        username = get_username_from_id(user_id)
        return jsonify({'logged_in': True, 'username': username})
    else:
        return jsonify({'logged_in': False})
    
@app.route('/perform_login', methods=['POST'])
def perform_login():
    username = request.form['username']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        return jsonify({'status': 'success', 'message': 'Logged in successfully.'})
    else:
        return jsonify({'status': 'error', 'message': 'Invalid username or password'}), 401

    
@app.route('/perform_registration', methods=['POST'])
def perform_registration():
    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Username and password are required'})

    password_hash = generate_password_hash(password)

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = 'INSERT INTO users (username, password_hash) VALUES (%s, %s)'
            cursor.execute(sql, (username, password_hash))
        conn.commit()

        # Log the user in by setting up the session
        session['user_id'] = cursor.lastrowid
        session['username'] = username

        return jsonify({'status': 'success', 'message': 'Registered successfully'})
    except pymysql.err.IntegrityError:
        return jsonify({'status': 'error', 'message': 'Username already exists'})
    finally:
        conn.close()

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'})

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/menu', methods=['GET'])
def get_menu():
    menu_items = db.get_menu_items()
    return jsonify(menu_items)

@app.route('/order', methods=['POST'])
def order():
    return db.process_order(request)

@app.route('/query', methods=['POST'])
def handle_query():
    return query_processor.handle_query(request)

@app.route('/add_to_order', methods=['POST'])
def add_to_order():
    # Check if the user is logged in
    if 'user_id' not in session:
        return jsonify({'message': 'You need to log in to place an order'}), 401

    # Get the order details from the request
    item_id = request.form['item_id']
    quantity = request.form['quantity']
    user_id = session['user_id']

    # Add the order to the database associated with the user_id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (item_id, quantity, user_id) VALUES (%s, %s, %s)',
                   (item_id, quantity, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'message': 'Item added to order successfully'})

@app.route('/get_order', methods=['GET'])
def get_order():
    # Check if the user is logged in
    if 'user_id' not in session:
        return jsonify({'message': 'You need to log in to view your order'}), 401

    user_id = session['user_id']
    
    # Retrieve the order from the database associated with the user_id
    conn = get_db_connection()
    cursor = conn.cursor()
    # Updated SQL query to join with the menu table and fetch item names
    cursor.execute('''
        SELECT o.quantity, m.item_name
        FROM orders o
        JOIN menu m ON o.item_id = m.id
        WHERE o.user_id = %s
    ''', (user_id,))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(orders)

@app.route('/get_order_with_prices', methods=['GET'])
def get_order_with_prices():
    # Check if the user is logged in
    if 'user_id' not in session:
        return jsonify({'message': 'You need to log in to view your order'}), 401

    user_id = session['user_id']
    
    # Retrieve the order from the database along with prices
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT o.quantity, m.item_name, m.price * o.quantity as price
        FROM orders o
        JOIN menu m ON o.item_id = m.id
        WHERE o.user_id = %s
    ''', (user_id,))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert price to float for each order item
    for order in orders:
        order['price'] = float(order['price'])

    return jsonify(orders)


if __name__ == '__main__':
    app.run(debug=True)

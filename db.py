from flask import Flask, request, jsonify, render_template
import pymysql

# Database configuration
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASSWORD = 'foodbot123'
DB_NAME = 'foodbot'

def db_connection():
    conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    return conn, cursor

def get_menu_items():
    conn, cursor = db_connection()
    cursor.execute("SELECT * FROM menu")
    menu_items = cursor.fetchall()
    conn.close()
    return menu_items

def process_order(request):
    data = request.get_json()
    order_items = data.get('order_items', [])
    total_price = 0.0
    
    conn, cursor = db_connection()

    for item_id in order_items:
        cursor.execute("SELECT price FROM menu WHERE id=%s", (item_id,))
        result = cursor.fetchone()
        if result:
            total_price += result["price"]

    conn.close()

    return jsonify({
        "message": "Order placed successfully!",
        "total_price": total_price
    })

def insert_order_item(item_id, add_quantity, user_id):
    conn, cursor = db_connection()
    try:
        cursor.execute("SELECT quantity FROM orders WHERE item_id=%s AND user_id=%s", (item_id, user_id))
        result = cursor.fetchone()

        if result:
            new_quantity = result['quantity'] + add_quantity
            cursor.execute("UPDATE orders SET quantity=%s WHERE item_id=%s AND user_id=%s", (new_quantity, item_id, user_id))
        else:
            cursor.execute("INSERT INTO orders (item_id, quantity, user_id) VALUES (%s, %s, %s)", (item_id, add_quantity, user_id))

        conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        cursor.close()
        conn.close()

        
def remove_order_item(item_id, remove_quantity, user_id):
    conn, cursor = db_connection()
    try:
        cursor.execute("SELECT quantity FROM orders WHERE item_id=%s AND user_id=%s", (item_id, user_id))
        result = cursor.fetchone()

        if result:
            new_quantity = result['quantity'] - remove_quantity

            if new_quantity > 0:
                cursor.execute("UPDATE orders SET quantity=%s WHERE item_id=%s AND user_id=%s", (new_quantity, item_id, user_id))
            else:
                cursor.execute("DELETE FROM orders WHERE item_id=%s AND user_id=%s", (item_id, user_id))

            conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        cursor.close()
        conn.close()
        
def get_order(user_id):
    conn, cursor = db_connection()
    cursor.execute("""
        SELECT orders.item_id, orders.quantity, menu.item_name 
        FROM orders 
        JOIN menu ON orders.item_id = menu.id 
        WHERE orders.user_id = %s
    """, (user_id,))
    orders = cursor.fetchall()
    conn.close()
    return orders


def clear_orders():
    try:
        conn, cursor = db_connection()
        cursor.execute("DELETE FROM orders")
        conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()
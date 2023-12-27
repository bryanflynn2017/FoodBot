from flask import Flask, request, jsonify, render_template, session
from decimal import Decimal
import spacy
import db

nlp = spacy.load("en_core_web_sm")

def generate_greeting_response():
    example_prompts = [
        "- Try asking: <br>'What's on the menu today?'<br>",
        "- You can order by saying: <br>'I would like to order a burger.'<br>",
        "Type 'help' for more information."
    ]
    greeting_response = "Hello! Here are some things you can ask me:\n <br><br>" + "<br>".join(example_prompts)
    return greeting_response

def generate_help_response():
    help_prompts = [
        "- To inquire about the menu, ask: <br>'What's on the menu today?'<br>",
        "- To place an order, say something like: <br>'I want to order two sodas.'<br>",
        "- If you need to remove an item from your order, say: <br>'Remove one burger.'<br>",
        "- To clear your entire order, you can say: <br>'Clear my order.'<br>",
        "- For pricing inquiries, ask: <br>'How much does a cheeseburger cost?'<br>",
        "- To complete your order, say: <br>'Finalize my order.'<br>"
    ]
    help_response = "Here are some examples of what you can ask me:\n <br><br>" + "<br>".join(help_prompts)
    return help_response


def get_menu():
    conn, cursor = db.db_connection()
    # Corrected SQL query
    cursor.execute("SELECT item_name, price, calories FROM menu")
    menu_items = cursor.fetchall()
    conn.close()

    if menu_items:
        menu_response = "Menu:<br>"
        for item in menu_items:
            capitalized_item_name = item['item_name'].capitalize()
            # Ensure the menu item display includes calories
            menu_response += f"- {capitalized_item_name}: ${item['price']} ({item['calories']} cal)<br>"
        return menu_response
    else:
        return "Sorry, the menu is currently unavailable."



def handle_query(request):
    data = request.get_json()
    user_query = data.get('query', '').lower()
    action = None
    item_name = None
    quantity = 1
    
    # Add greetings handling
    greetings = ["hi", "hello", "hey", "greetings"]
    if any(greeting in user_query for greeting in greetings):
        return jsonify({"answer": generate_greeting_response()})
    
    # Check for help command
    if "help" in user_query:
        return jsonify({"answer": generate_help_response()})
    
    # Check if user asks for the menu
    if "menu" in user_query:
        return jsonify({"answer": get_menu()})
    
    # Mapping of spelled-out numbers to their numeric equivalents
    number_map = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    }

    # Process the user query
    doc = nlp(user_query)
    for token in doc:
        if token.lemma_ in ["add", "order", "want", "remove", "delete", "get rid of"]:
            action = token.lemma_
        if token.pos_ == "NOUN":
            item_name = token.lemma_
        if token.pos_ == "NUM" or token.text in number_map:
            try:
                quantity = int(token.text)
            except ValueError:
                quantity = number_map.get(token.text, 1)
                
    # Check if it's a calorie query
    if "calories" in user_query and item_name:
        conn, cursor = db.db_connection()
        cursor.execute("SELECT calories FROM menu WHERE item_name=%s", (item_name,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return jsonify({"answer": f"The {item_name} contains {result['calories']} calories."})
        else:
            return jsonify({"answer": "Sorry, I couldn't find that item."})
                
    # Handle clear order phrases
    clear_order_phrases = ["start over", "delete everything", "delete it all", "clear", "reset", "empty", "remove everything", "restart"]
    if any(phrase in user_query for phrase in clear_order_phrases):
        # Ask for confirmation before clearing the order
        return jsonify({"answer": "Are you sure you want to clear your entire order? Please confirm (Yes or No)."})

    # Handle confirmation for clearing the order
    if "yes" in user_query or "yeah" in user_query:
        db.clear_orders()  # Assuming db.clear_orders() is a function to clear all orders
        return jsonify({"answer": "Your order has been cleared."})
    
    # Handle negative response to clearing the order
    if "no" in user_query or "don't" in user_query or "do not" in user_query:
        return jsonify({"answer": "Alright, no changes were made. How else may I assist you?"})

    # Check if it's a price query
    if "price" in user_query and item_name:
        conn, cursor = db.db_connection()
        cursor.execute("SELECT price FROM menu WHERE item_name=%s", (item_name,))
        result = cursor.fetchone()
        conn.close()
        if result:
            total_price = quantity * result['price']
            return jsonify({"answer": f"The price of {quantity} {item_name}(s) is ${total_price}."})
        else:
            return jsonify({"answer": "Sorry, I couldn't find that item."})

    # Handle order related queries
    elif action and item_name:
        conn, cursor = db.db_connection()
        cursor.execute("SELECT id FROM menu WHERE item_name=%s", (item_name,))
        result = cursor.fetchone()
        conn.close()
        if result:
            item_id = result['id']
            if 'user_id' in session:
                user_id = session['user_id']
                if action in ["order", "want", "add"]:
                    db.insert_order_item(item_id, quantity, user_id)  # Add item
                    return jsonify({"answer": f"{quantity} {item_name}(s) added to your order."})
                elif action in ["remove", "delete", "get rid of"]:
                    db.remove_order_item(item_id, quantity, user_id)  # Remove item
                    return jsonify({"answer": f"{quantity} {item_name}(s) removed from your order."})
            else:
                return jsonify({"answer": "You need to be logged in to place an order."})
    
    # Handle item removal queries
    if action in ["remove", "delete", "get rid of"] and item_name:
        conn, cursor = db.db_connection()
        cursor.execute("SELECT id FROM menu WHERE item_name=%s", (item_name,))
        menu_result = cursor.fetchone()
        if menu_result:
            item_id = menu_result['id']
            if 'user_id' in session:
                user_id = session['user_id']
                cursor.execute("SELECT * FROM orders WHERE item_id=%s AND user_id=%s", (item_id, user_id))
                order_result = cursor.fetchone()
                if order_result:
                    db.remove_order_item(item_id, quantity, user_id)
                    return jsonify({"answer": f"{quantity} {item_name}(s) removed from your order."})
                else:
                    return jsonify({"answer": f"{item_name} is not in your order."})
            else:
                return jsonify({"answer": "You need to be logged in to modify an order."})
        else:
            return jsonify({"answer": "Sorry, I couldn't find that item in our menu."})
        conn.close()
    
    # Finalize the order
    elif "finalize" in user_query or "complete" in user_query or "check out" in user_query or "finish" in user_query:
        conn, cursor = db.db_connection()
        cursor.execute("SELECT menu.item_name, menu.price, orders.quantity FROM orders JOIN menu ON orders.item_id = menu.id")
        order_items = cursor.fetchall()
        conn.close()
    
        if order_items:
            order_summary = "Your finalized order:<br><br>"
            total_price = Decimal('0.00')
            for item in order_items:
                item_name = item['item_name']
                price = item['price']
                quantity = item['quantity']
    
                # Ensure quantity is an integer
                if not isinstance(quantity, int):
                    try:
                        quantity = int(quantity)
                    except (ValueError, TypeError):
                        return jsonify({"answer": f"Error in processing order: quantity is not a number."})
    
                line_total = price * Decimal(quantity)
                total_price += line_total
                order_summary += f"- {item_name} (x{quantity}): ${line_total:.2f}<br>"
    
            order_summary += f"_______________________<br>Total Price: ${total_price:.2f}<br><br>~ Thank You! ~"
            return jsonify({"answer": order_summary})
        else:
            return jsonify({"answer": "Your order is currently empty."})
        
    return jsonify({"answer": "Please specify a valid action. <br> Type 'help' for more information."})

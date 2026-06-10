from flask import Flask, render_template, abort, request, make_response, redirect, url_for
import json
import requests  # <-- Make sure to import requests
from fakeApi import data

app: Flask = Flask(__name__)

TELEGRAM_TOKEN_BOT = '8494492410:AAGWmIXOpMJVFvBNMaCXpZ6EBylhKMeapuI'
TELEGRAM_ID_CHAT = '-1003771965525'



@app.get('/')
def home():
    return render_template('front/index.html', products=data)


@app.get('/products')
def products():
    return render_template('front/products.html', products=data)


@app.get('/product/<int:product_id>')
def product(product_id):
    product_detail = next((p for p in data if p["id"] == product_id), None)

    if product_detail is None:
        abort(404)

    similar_products = [
        p for p in data
        if p["category"] == product_detail["category"] and p["id"] != product_detail["id"]
    ]
    similar_products = similar_products[:4]

    return render_template(
        'front/product.html',
        product=product_detail,
        related_products=similar_products
    )


@app.post('/add-to-cart/<int:product_id>')
def add_to_cart(product_id):
    existing_cart_cookie = request.cookies.get('shopping_cart')
    cart_list = []

    if existing_cart_cookie:
        try:
            cart_list = json.loads(existing_cart_cookie)
            # Safe-check: If the cookie format is outdated, reset it
            if cart_list and not isinstance(cart_list[0], dict):
                cart_list = []
        except json.JSONDecodeError:
            cart_list = []

    try:
        input_qty = int(request.form.get('quantity', 1))
    except (ValueError, TypeError):
        input_qty = 1

    product_exists = False
    for item in cart_list:
        if isinstance(item, dict) and item.get("id") == product_id:
            item["qty"] += input_qty
            product_exists = True
            break

    if not product_exists:
        cart_list.append({"id": product_id, "qty": input_qty})

    is_buy_now = request.form.get('action') == 'buy_now'
    target_url = url_for('checkout') if is_buy_now else url_for('cart')
    response = make_response(redirect(target_url))

    response.set_cookie('shopping_cart', json.dumps(cart_list), max_age=2592000, httponly=True)
    return response


@app.get('/cart')
def cart():
    cart_cookie = request.cookies.get('shopping_cart')
    cart_items = []
    subtotal = 0.0

    if cart_cookie:
        try:
            cookie_data = json.loads(cart_cookie)

            # FIX: If the data array structure is an old list format, ignore it
            if isinstance(cookie_data, list):
                for cookie_item in cookie_data:
                    # Double-check that the item is a dictionary to prevent crashes
                    if isinstance(cookie_item, dict):
                        product_lookup = next((p for p in data if p["id"] == cookie_item.get("id")), None)
                        if product_lookup:
                            item_copy = product_lookup.copy()
                            item_copy["quantity"] = cookie_item.get("qty", 1)

                            cart_items.append(item_copy)
                            subtotal += item_copy['price'] * item_copy['quantity']
        except json.JSONDecodeError:
            pass

    return render_template('front/cart.html', cart_items=cart_items, subtotal=subtotal, total=subtotal)


@app.post('/update-quantity-nojs/<int:product_id>')
def update_quantity_nojs(product_id):
    cart_cookie = request.cookies.get('shopping_cart')
    cart_list = []

    if cart_cookie:
        try:
            cart_list = json.loads(cart_cookie)
        except json.JSONDecodeError:
            pass

    # Read the data natively from the form submission payload
    change_direction = request.form.get('direction')  # Captures 'up' or 'down'

    for item in cart_list:
        if isinstance(item, dict) and item.get("id") == product_id:
            if change_direction == 'up':
                item["qty"] += 1
            elif change_direction == 'down' and item["qty"] > 1:
                item["qty"] -= 1
            break

    # Build response redirect back to the cart page
    response = make_response(redirect(url_for('cart')))

    # Save the updated cart state back inside browser cookie memory
    response.set_cookie('shopping_cart', json.dumps(cart_list), max_age=2592000, httponly=True)
    return response


@app.get('/remove-from-cart/<int:product_id>')
def remove_from_cart(product_id):
    cart_cookie = request.cookies.get('shopping_cart')
    cart_list = []

    if cart_cookie:
        try:
            cart_list = json.loads(cart_cookie)
        except json.JSONDecodeError:
            pass

    # Rebuild the list, filtering out the item matching our target product_id
    updated_cart = [
        item for item in cart_list
        if isinstance(item, dict) and item.get("id") != product_id
    ]

    # Build a native redirect response back to your main cart page view
    response = make_response(redirect(url_for('cart')))

    # Update the browser cookie with our newly trimmed array string
    response.set_cookie('shopping_cart', json.dumps(updated_cart), max_age=2592000, httponly=True)
    return response

@app.get('/checkout')
def checkout():
    cart_cookie = request.cookies.get('shopping_cart')
    cart_items = []
    subtotal = 0.0

    if cart_cookie:
        try:
            cookie_data = json.loads(cart_cookie)

            # FIX: Double-check that the item is a dictionary to prevent crashes
            if isinstance(cookie_data, list):
                for cookie_item in cookie_data:
                    if isinstance(cookie_item, dict):
                        product_lookup = next((p for p in data if p["id"] == cookie_item.get("id")), None)
                        if product_lookup:
                            item_copy = product_lookup.copy()
                            item_copy["quantity"] = cookie_item.get("qty", 1)
                            cart_items.append(item_copy)
                            subtotal += item_copy['price'] * item_copy['quantity']
        except json.JSONDecodeError:
            pass

    return render_template('front/checkout.html', cart_items=cart_items, subtotal=subtotal, total=subtotal)


@app.route('/telegram_order', methods=['POST'])  # FIX: Wrapped 'POST' in a list
def telegram_order():
    cart_cookie = request.cookies.get('shopping_cart')
    cart_items = []
    subtotal = 0.0

    # 1. Parse the cart items from cookies (similar to your /cart logic)
    if cart_cookie:
        try:
            cookie_data = json.loads(cart_cookie)
            if isinstance(cookie_data, list):
                for cookie_item in cookie_data:
                    if isinstance(cookie_item, dict):
                        product_lookup = next((p for p in data if p["id"] == cookie_item.get("id")), None)
                        if product_lookup:
                            item_copy = product_lookup.copy()
                            item_copy["quantity"] = cookie_item.get("qty", 1)
                            cart_items.append(item_copy)
                            subtotal += item_copy['price'] * item_copy['quantity']
        except json.JSONDecodeError:
            pass

    # Safety check: If cart is empty, redirect them back to the cart page
    if not cart_items:
        return redirect(url_for('cart'))

    # 2. Build a cleanly formatted text message for Telegram
    message = "🛍️ **NEW ORDER RECEIVED** 🛍️\n\n"
    message += "📦 **Items:**\n"
    
    for item in cart_items:
        item_total = item['price'] * item['quantity']
        message += f"- {item['title']} (x{item['quantity']}) — ${item_total:.2f}\n"
    
    message += f"\n💰 **Total Amount:** ${subtotal:.2f}"

    # 3. Push data to Telegram Bot API
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_BOT}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_ID_CHAT,
        "text": message,
        "parse_mode": "Markdown"  # Allows bolding, bullet points, and neat styling
    }

    try:
        telegram_response = requests.post(telegram_url, json=payload)
        telegram_response.raise_for_status()  # Throws an error if the API call failed
    except requests.exceptions.RequestException as e:
        print(f"Telegram API Error: {e}")
        # Option: Handle errors gracefully here (e.g., return an error page)

    # 4. Clear the cart cookie after a successful order submission, then redirect
    #    back to /cart with a query param so the success popup modal is shown there.
    response = make_response(redirect(url_for('cart', order_success=1)))
    response.delete_cookie('shopping_cart')
    return response

@app.get('/account')
def account():
    return render_template('front/account.html')


@app.get('/forget-password')
def forget_password():
    return render_template('front/forget-password.html')


@app.get('/login')
def login():
    return render_template('front/login.html')


@app.get('/create_user')
def create_user():
    return render_template('front/create-user.html')

@app.route('/contact')
def contact():
    if True:
        return render_template('front/contact.html')
    else:
        return render_template('404.html')


if __name__ == '__main__':
    app.run(debug=True)
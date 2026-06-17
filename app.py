import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, Dish, Order, OrderItem

app = Flask(__name__)
app.config['SECRET_KEY'] = 'home_cook_delivery_secret_key_2026'
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure Uploads
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Constants
GST_RATE = 0.05
DELIVERY_FEE = 30.0

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'index'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ============================================================
# AUTHENTICATION ROUTES
# ============================================================

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'customer':
            return redirect(url_for('customer_dashboard'))
        elif current_user.role == 'cook':
            return redirect(url_for('cook_dashboard'))
        elif current_user.role == 'delivery':
            return redirect(url_for('delivery_dashboard'))
    return render_template('index.html')

@app.route('/register/<role>', methods=['GET', 'POST'])
def register(role):
    if role not in ['customer', 'cook', 'delivery']:
        flash('Invalid role selected.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        address = request.form.get('address', '')

        if not all([name, email, phone, password]):
            flash('All fields are required.', 'error')
            return redirect(url_for('register', role=role))

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email already registered. Please login.', 'error')
            return redirect(url_for('register', role=role))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        new_user = User(
            role=role,
            name=name,
            email=email,
            phone=phone,
            password=hashed_password,
            address=address
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login', role=role))

    return render_template('register.html', role=role)

@app.route('/login/<role>', methods=['GET', 'POST'])
def login(role):
    if role not in ['customer', 'cook', 'delivery']:
        flash('Invalid role selected.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email, role=role).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Welcome back, {user.name}!', 'success')
            if role == 'customer':
                return redirect(url_for('customer_dashboard'))
            elif role == 'cook':
                return redirect(url_for('cook_dashboard'))
            elif role == 'delivery':
                return redirect(url_for('delivery_dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'error')

    return render_template('login.html', role=role)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('cart', None)
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

# ============================================================
# CUSTOMER ROUTES
# ============================================================

@app.route('/customer/dashboard')
@login_required
def customer_dashboard():
    if current_user.role != 'customer':
        return redirect(url_for('index'))

    search_query = request.args.get('search', '')
    category = request.args.get('category', 'All')

    query = Dish.query.filter_by(is_available=True)

    # Join with cook to check if cook is online
    query = query.join(User, Dish.cook_id == User.id).filter(User.is_online == True)

    if search_query:
        query = query.filter(
            db.or_(
                Dish.name.ilike(f'%{search_query}%'),
                Dish.description.ilike(f'%{search_query}%')
            )
        )

    if category and category != 'All':
        query = query.filter(Dish.category == category)

    dishes = query.all()
    cart = session.get('cart', {})
    cart_count = sum(item['quantity'] for item in cart.values()) if cart else 0

    return render_template('customer_dashboard.html', dishes=dishes,
                           search_query=search_query, category=category,
                           cart_count=cart_count)

@app.route('/add_to_cart/<int:dish_id>', methods=['POST'])
@login_required
def add_to_cart(dish_id):
    if current_user.role != 'customer':
        return redirect(url_for('index'))

    try:
        quantity = int(request.form.get('quantity', 1))
    except (ValueError, TypeError):
        quantity = 1
    dish = Dish.query.get_or_404(dish_id)

    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']
    dish_id_str = str(dish_id)

    if dish_id_str in cart:
        cart[dish_id_str]['quantity'] += quantity
    else:
        # Enforce single-cook per order
        if cart:
            first_item = list(cart.values())[0]
            if first_item['cook_id'] != dish.cook_id:
                flash('You can only order from one Home Cook at a time. Please clear your cart first.', 'error')
                return redirect(url_for('customer_dashboard'))

        cart[dish_id_str] = {
            'name': dish.name,
            'price': dish.price,
            'quantity': quantity,
            'cook_id': dish.cook_id,
            'image': dish.image_filename,
            'description': dish.description
        }

    session['cart'] = cart
    session.modified = True
    flash(f'{quantity}x {dish.name} added to cart!', 'success')
    return redirect(url_for('customer_dashboard'))

@app.route('/remove_from_cart/<dish_id>')
@login_required
def remove_from_cart(dish_id):
    if current_user.role != 'customer':
        return redirect(url_for('index'))

    cart = session.get('cart', {})
    if dish_id in cart:
        removed_name = cart[dish_id]['name']
        del cart[dish_id]
        session['cart'] = cart
        session.modified = True
        flash(f'{removed_name} removed from cart.', 'info')

    return redirect(url_for('view_cart'))

@app.route('/update_cart/<dish_id>', methods=['POST'])
@login_required
def update_cart(dish_id):
    if current_user.role != 'customer':
        return redirect(url_for('index'))

    cart = session.get('cart', {})
    try:
        new_qty = int(request.form.get('quantity', 1))
    except (ValueError, TypeError):
        new_qty = 1

    if dish_id in cart:
        if new_qty <= 0:
            del cart[dish_id]
        else:
            cart[dish_id]['quantity'] = new_qty

    session['cart'] = cart
    session.modified = True
    return redirect(url_for('view_cart'))

@app.route('/customer/cart')
@login_required
def view_cart():
    if current_user.role != 'customer':
        return redirect(url_for('index'))

    cart = session.get('cart', {})

    subtotal = sum(item['price'] * item['quantity'] for item in cart.values())
    delivery_fee = DELIVERY_FEE if cart else 0.0
    taxes = round(subtotal * GST_RATE, 2) if cart else 0.0
    total = subtotal + delivery_fee + taxes

    return render_template('cart.html', cart=cart, subtotal=subtotal,
                           delivery_fee=delivery_fee, taxes=taxes, total=total)

@app.route('/customer/clear_cart')
@login_required
def clear_cart():
    session.pop('cart', None)
    flash('Cart cleared.', 'info')
    return redirect(url_for('customer_dashboard'))

@app.route('/customer/checkout', methods=['POST'])
@login_required
def checkout():
    if current_user.role != 'customer':
        return redirect(url_for('index'))

    cart = session.get('cart')
    if not cart:
        flash('Your cart is empty!', 'error')
        return redirect(url_for('customer_dashboard'))

    payment_method = request.form.get('payment_method')
    delivery_address = request.form.get('delivery_address')

    if not delivery_address:
        flash('Please enter a delivery address.', 'error')
        return redirect(url_for('view_cart'))

    subtotal = sum(item['price'] * item['quantity'] for item in cart.values())
    delivery_fee = DELIVERY_FEE
    taxes = round(subtotal * GST_RATE, 2)
    total = subtotal + delivery_fee + taxes

    first_item = list(cart.values())[0]
    cook_id = first_item['cook_id']

    new_order = Order(
        customer_id=current_user.id,
        cook_id=cook_id,
        subtotal=subtotal,
        gst=taxes,
        delivery_charge=delivery_fee,
        total_amount=total,
        payment_method=payment_method,
        payment_status='Paid' if payment_method == 'upi' else 'Pending',
        delivery_address=delivery_address
    )
    db.session.add(new_order)
    db.session.flush()

    for dish_id_str, item in cart.items():
        order_item = OrderItem(
            order_id=new_order.id,
            dish_id=int(dish_id_str),
            quantity=item['quantity'],
            price=item['price']
        )
        db.session.add(order_item)

    db.session.commit()
    session.pop('cart', None)
    flash(f'Order #{new_order.id} placed successfully! Waiting for cook to accept.', 'success')
    return redirect(url_for('customer_history'))

@app.route('/customer/history')
@login_required
def customer_history():
    if current_user.role != 'customer':
        return redirect(url_for('index'))

    orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('customer_history.html', orders=orders)

@app.route('/customer/profile', methods=['GET', 'POST'])
@login_required
def customer_profile():
    if current_user.role != 'customer':
        return redirect(url_for('index'))

    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.phone = request.form.get('phone')
        current_user.address = request.form.get('address')

        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '':
                filename = secure_filename(f"user_{current_user.id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                current_user.profile_pic = filename

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('customer_profile'))

    return render_template('profile.html', role='customer')

# ============================================================
# COOK ROUTES
# ============================================================

@app.route('/cook/dashboard')
@login_required
def cook_dashboard():
    if current_user.role != 'cook':
        return redirect(url_for('index'))

    active_orders = Order.query.filter(
        Order.cook_id == current_user.id,
        Order.status.in_(['Pending', 'Accepted', 'Preparing', 'Ready for Delivery'])
    ).order_by(Order.created_at.desc()).all()

    # Today's earnings
    from datetime import date
    today = date.today()
    todays_orders = Order.query.filter(
        Order.cook_id == current_user.id,
        Order.status == 'Delivered',
        db.func.date(Order.created_at) == today.strftime('%Y-%m-%d')
    ).all()
    todays_earnings = sum(o.subtotal * 0.90 for o in todays_orders)

    return render_template('cook_dashboard.html', orders=active_orders,
                           todays_earnings=todays_earnings)

@app.route('/order_action/<int:order_id>/<action>', methods=['POST'])
@login_required
def order_action(order_id, action):
    if current_user.role != 'cook':
        return redirect(url_for('index'))

    order = Order.query.get_or_404(order_id)
    if order.cook_id != current_user.id:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('cook_dashboard'))

    if action == 'accept':
        order.status = 'Accepted'
        flash(f'Order #{order.id} accepted! Start preparing.', 'success')
    elif action == 'reject':
        order.status = 'Rejected'
        flash(f'Order #{order.id} rejected.', 'info')
    elif action == 'preparing':
        order.status = 'Preparing'
        flash(f'Order #{order.id} is now being prepared.', 'success')
    elif action == 'ready':
        order.status = 'Ready for Delivery'
        flash(f'Order #{order.id} is ready for delivery pickup!', 'success')

    db.session.commit()
    return redirect(url_for('cook_dashboard'))

@app.route('/cook/menu', methods=['GET', 'POST'])
@login_required
def cook_menu():
    if current_user.role != 'cook':
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price_str = request.form.get('price')
        category = request.form.get('category', 'Lunch')

        if not all([name, description, price_str]):
            flash('All fields are required.', 'error')
            return redirect(url_for('cook_menu'))

        try:
            price = float(price_str)
        except (ValueError, TypeError):
            flash('Invalid price format.', 'error')
            return redirect(url_for('cook_menu'))

        image_filename = 'default_dish.png'
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                image_filename = secure_filename(f"cook_{current_user.id}_dish_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        new_dish = Dish(
            cook_id=current_user.id,
            name=name,
            description=description,
            price=price,
            category=category,
            image_filename=image_filename
        )
        db.session.add(new_dish)
        db.session.commit()
        flash(f'"{name}" added to your menu!', 'success')
        return redirect(url_for('cook_menu'))

    dishes = Dish.query.filter_by(cook_id=current_user.id).order_by(Dish.created_at.desc()).all()
    return render_template('cook_menu.html', dishes=dishes)

@app.route('/toggle_dish/<int:dish_id>')
@login_required
def toggle_dish(dish_id):
    if current_user.role != 'cook':
        return redirect(url_for('index'))

    dish = Dish.query.get_or_404(dish_id)
    if dish.cook_id == current_user.id:
        dish.is_available = not dish.is_available
        db.session.commit()
        status = 'available' if dish.is_available else 'unavailable'
        flash(f'"{dish.name}" is now {status}.', 'info')

    return redirect(url_for('cook_menu'))

@app.route('/delete_dish/<int:dish_id>', methods=['POST'])
@login_required
def delete_dish(dish_id):
    if current_user.role != 'cook':
        return redirect(url_for('index'))

    dish = Dish.query.get_or_404(dish_id)
    if dish.cook_id == current_user.id:
        # Check if dish has been ordered
        if dish.order_items:
            flash(f'"{dish.name}" cannot be deleted because it is part of past orders. You can make it unavailable instead.', 'error')
        else:
            db.session.delete(dish)
            db.session.commit()
            flash(f'"{dish.name}" removed from your menu.', 'info')
    
    return redirect(url_for('cook_menu'))

@app.route('/cook/history')
@login_required
def cook_history():
    if current_user.role != 'cook':
        return redirect(url_for('index'))

    orders = Order.query.filter(
        Order.cook_id == current_user.id,
        Order.status.in_(['Delivered', 'Rejected'])
    ).order_by(Order.created_at.desc()).all()

    total_earnings = sum(o.subtotal * 0.90 for o in orders if o.status == 'Delivered')

    return render_template('cook_history.html', orders=orders, total_earnings=total_earnings)

@app.route('/cook/profile', methods=['GET', 'POST'])
@login_required
def cook_profile():
    if current_user.role != 'cook':
        return redirect(url_for('index'))

    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.phone = request.form.get('phone')
        current_user.address = request.form.get('address')

        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '':
                filename = secure_filename(f"user_{current_user.id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                current_user.profile_pic = filename

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('cook_profile'))

    return render_template('profile.html', role='cook')

@app.route('/cook/toggle_online')
@login_required
def cook_toggle_online():
    if current_user.role != 'cook':
        return redirect(url_for('index'))

    current_user.is_online = not current_user.is_online
    db.session.commit()
    status = 'Online' if current_user.is_online else 'Offline'
    flash(f'You are now {status}.', 'info')
    return redirect(url_for('cook_dashboard'))

# ============================================================
# DELIVERY PARTNER ROUTES
# ============================================================

@app.route('/delivery/dashboard')
@login_required
def delivery_dashboard():
    if current_user.role != 'delivery':
        return redirect(url_for('index'))

    available_orders = Order.query.filter_by(
        status='Ready for Delivery'
    ).order_by(Order.created_at.asc()).all()

    my_active_orders = Order.query.filter(
        Order.delivery_partner_id == current_user.id,
        Order.status == 'Picked Up'
    ).order_by(Order.created_at.asc()).all()

    return render_template('delivery_dashboard.html',
                           available_orders=available_orders,
                           my_active_orders=my_active_orders)

@app.route('/delivery_action/<int:order_id>/<action>', methods=['POST'])
@login_required
def delivery_action(order_id, action):
    if current_user.role != 'delivery':
        return redirect(url_for('index'))

    order = Order.query.get_or_404(order_id)

    if action == 'accept':
        if order.status == 'Ready for Delivery' and order.delivery_partner_id is None:
            order.delivery_partner_id = current_user.id
            order.status = 'Picked Up'
            flash(f'You accepted Order #{order.id} for delivery!', 'success')
        else:
            flash('This order is no longer available.', 'error')
    elif action == 'delivered':
        if order.delivery_partner_id == current_user.id and order.status == 'Picked Up':
            order.status = 'Delivered'
            if order.payment_method == 'cod':
                order.payment_status = 'Paid'
            flash(f'Order #{order.id} delivered successfully!', 'success')

    db.session.commit()
    return redirect(url_for('delivery_dashboard'))

@app.route('/delivery/history')
@login_required
def delivery_history():
    if current_user.role != 'delivery':
        return redirect(url_for('index'))

    orders = Order.query.filter_by(
        delivery_partner_id=current_user.id,
        status='Delivered'
    ).order_by(Order.created_at.desc()).all()

    total_earnings = sum(order.delivery_charge for order in orders)

    return render_template('delivery_history.html', orders=orders, total_earnings=total_earnings)

@app.route('/delivery/profile', methods=['GET', 'POST'])
@login_required
def delivery_profile():
    if current_user.role != 'delivery':
        return redirect(url_for('index'))

    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.phone = request.form.get('phone')
        current_user.address = request.form.get('address')

        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '':
                filename = secure_filename(f"user_{current_user.id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                current_user.profile_pic = filename

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('delivery_profile'))

    return render_template('profile.html', role='delivery')

# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == '__main__':
    with app.app_context():
        os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)
        db.create_all()
        print("Database initialized successfully!")
        print("Home Cook Delivery is running at http://127.0.0.1:5000")
    app.run(debug=True)

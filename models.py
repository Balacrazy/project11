from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)  # 'customer', 'cook', 'delivery'
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(256), nullable=False)
    address = db.Column(db.Text, nullable=True)
    profile_pic = db.Column(db.String(150), default='default.png')
    is_online = db.Column(db.Boolean, default=True)  # For cooks to toggle availability

    # Relationships
    dishes = db.relationship('Dish', backref='cook', lazy=True)
    customer_orders = db.relationship('Order', foreign_keys='Order.customer_id', backref='customer', lazy=True)
    delivery_orders = db.relationship('Order', foreign_keys='Order.delivery_partner_id', backref='driver', lazy=True)

class Dish(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cook_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), default='Lunch')  # Breakfast, Lunch, Snacks, Sweets, Dinner
    image_filename = db.Column(db.String(150), nullable=False, default='default_dish.png')
    is_available = db.Column(db.Boolean, default=True)
    rating = db.Column(db.Float, default=4.5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    cook_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    delivery_partner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Status flow: Pending -> Accepted -> Preparing -> Ready for Delivery -> Picked Up -> Delivered
    status = db.Column(db.String(50), default='Pending')

    subtotal = db.Column(db.Float, nullable=False)
    gst = db.Column(db.Float, nullable=False)
    delivery_charge = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)

    payment_method = db.Column(db.String(20), nullable=False)  # 'upi' or 'cod'
    payment_status = db.Column(db.String(20), default='Pending')  # 'Paid' or 'Pending'
    delivery_address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy=True)
    cook_rel = db.relationship('User', foreign_keys=[cook_id], overlaps="customer_orders,delivery_orders,customer,driver")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    dish_id = db.Column(db.Integer, db.ForeignKey('dish.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

    dish = db.relationship('Dish', backref='order_items', lazy=True)

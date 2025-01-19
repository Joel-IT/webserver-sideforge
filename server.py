import os
import stripe
from flask import (
    Flask, render_template, request, redirect, url_for, flash, 
    jsonify, session, abort, send_file
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import FlaskForm, CSRFProtect
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from wtforms import StringField, TextAreaField, SubmitField, SelectField, BooleanField, DateField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_debugtoolbar import DebugToolbarExtension
from datetime import datetime, timedelta
import secrets
from flask_wtf.csrf import generate_csrf
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import re
from enum import Enum
import traceback
from PIL import Image, ImageDraw, ImageFont
import io
import base64

# Stripe Configuration
STRIPE_PUBLISHABLE_KEY = os.environ.get(
    'STRIPE_PUBLISHABLE_KEY', 
    'pk_test_51OVcDbF2SxkZbNzbQpMcSBbwv6MppXWY7yQIIfVXE6QeuGYCTEMzMwxqnpFqyrUibmfpxoVfGP8BshYsxLLWAgGr00SLDPkUJZ'
)
stripe.api_key = os.environ.get(
    'STRIPE_SECRET_KEY', 
    'sk_test_51OVcDbF2SxkZbNzbpLIisM3x6SbVGCqHXdcEy3DEa4FZbWp6qf2Pq8oAxrtp85Qri1Gsm6hPZeq7fUJwMGnwBixB00aAalId0e'
)

# Validate Stripe keys
if not STRIPE_PUBLISHABLE_KEY or not stripe.api_key:
    raise ValueError("Stripe keys must be configured. Check environment variables.")

# Function to create or retrieve Stripe products and prices
def get_or_create_stripe_plan(name, monthly_price, features):
    try:
        # Hardcoded plans to avoid Stripe API calls during initialization
        return {
            'product_id': f'{name.lower()}_product',
            'price_id': f'{name.lower()}_price',
            'name': name,
            'monthly_price': monthly_price,
            'features': features
        }
    except Exception as e:
        # Use print for logging before app is initialized
        print(f"Error creating Stripe plan {name}: {str(e)}")
        return {
            'product_id': f'{name.lower()}_product',
            'price_id': f'{name.lower()}_price',
            'name': name,
            'monthly_price': monthly_price,
            'features': features
        }

# Enhanced Stripe Pricing Plans
STRIPE_PLANS = {
    'starter': get_or_create_stripe_plan(
        'Starter', 9.99, 
        ['1 CPU Core', '2GB RAM', '50GB SSD Storage', 'Basic Support', 'Shared Bandwidth']
    ),
    'pro': get_or_create_stripe_plan(
        'Pro', 29.99, 
        ['2 CPU Cores', '8GB RAM', '200GB SSD Storage', 'Priority Support', 'Dedicated Bandwidth', 'Free SSL Certificate']
    ),
    'enterprise': get_or_create_stripe_plan(
        'Enterprise', 99.99, 
        ['4 CPU Cores', '16GB RAM', '500GB SSD Storage', '24/7 Premium Support', 'Dedicated Server', 'Free Domain', 'Advanced Security']
    )
}

# Route to create actual Stripe products and prices after app initialization
def initialize_stripe_products():
    try:
        for plan_key, plan_details in STRIPE_PLANS.items():
            # Create or find existing product
            try:
                product = stripe.Product.create(
                    name=plan_details['name'],
                    description=' | '.join(plan_details['features']),
                    metadata={
                        'plan_type': plan_key,
                        'features': ','.join(plan_details['features'])
                    }
                )
                
                # Create price for the product
                price = stripe.Price.create(
                    product=product.id,
                    unit_amount=int(plan_details['monthly_price'] * 100),  # Convert to cents
                    currency='usd',
                    recurring={'interval': 'month'}
                )
                
                # Update the plan with actual Stripe IDs
                STRIPE_PLANS[plan_key]['product_id'] = product.id
                STRIPE_PLANS[plan_key]['price_id'] = price.id
                
            except stripe.error.StripeError as e:
                print(f"Error creating Stripe product for {plan_key}: {str(e)}")
    except Exception as e:
        print(f"Unexpected error initializing Stripe products: {str(e)}")

# Create Flask app
app = Flask(__name__)

# Configure app before Stripe initialization
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.root_path, 'sideforge.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure database directory and file have proper permissions
db_dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs(db_dir, exist_ok=True)
os.chmod(db_dir, 0o755)
db_path = os.path.join(db_dir, 'sideforge.db')
if os.path.exists(db_path):
    os.chmod(db_path, 0o666)
else:
    with open(db_path, 'w') as f:
        f.write('')  # Create an empty file
    os.chmod(db_path, 0o666)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def run_database_migration():
    """
    Run database migration to apply model changes
    """
    try:
        # Drop existing tables (be careful in production!)
        db.drop_all()
        
        # Recreate all tables
        db.create_all()
        
        print("Database migration completed successfully.")
    except Exception as e:
        print(f"Error during database migration: {str(e)}")
        db.session.rollback()

def initialize_database():
    """
    Initialize the database with all necessary setup
    """
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            
            # Additional initialization steps
            if not User.query.first():
                # Create a default admin user if no users exist
                default_admin = User(
                    username='admin', 
                    email='admin@sideforge.com', 
                    name='Admin User'
                )
                default_admin.set_password('adminpassword')
                db.session.add(default_admin)
                db.session.commit()
            
            print("Database initialized successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"Error initializing database: {str(e)}")

# Comprehensive data migration to preserve ALL critical application data 
# before database recreation.
def migrate_existing_subscriptions():
    """
    Comprehensive data migration to preserve ALL critical application data 
    before database recreation.
    
    This function ensures that every single record across all models 
    is backed up and can be restored during server reload or shutdown.
    """
    migrated_data = {}
    try:
        # Define ALL models to migrate in order of dependency
        models_to_migrate = [
            User,           # Users first (primary model)
            PaymentMethod,  # Payment methods depend on users
            Subscription,   # Subscriptions depend on users
            ServerInstance, # Server instances depend on users and subscriptions
            Payment,        # Payments depend on users and subscriptions
            UserCloudStorage # Cloud storage depends on users
        ]
        
        for model in models_to_migrate:
            model_name = model.__name__
            try:
                # Query ALL records for each model
                records = model.query.all()
                
                # Deep copy records to preserve all attributes
                migrated_records = []
                for record in records:
                    # Create a dictionary representation of the record
                    record_dict = {
                        column.name: getattr(record, column.name) 
                        for column in record.__table__.columns
                    }
                    migrated_records.append(record_dict)
                
                # Store migrated records
                migrated_data[model_name] = migrated_records
                
                # Log number of records for each model
                print(f"Preserving {len(records)} {model_name} records")
            except Exception as e:
                print(f"Error migrating {model_name}: {str(e)}")
        
        return migrated_data
    except Exception as e:
        print(f"Comprehensive data migration error: {str(e)}")
        return migrated_data

# Initialize database with comprehensive data preservation.
def initialize_database_with_preservation():
    """
    Initialize database with comprehensive data preservation.
    
    This function ensures ALL critical data is restored after database recreation.
    """
    with app.app_context():
        # Migrate existing data before dropping tables
        migrated_data = migrate_existing_subscriptions()
        
        # Drop existing tables (use with caution in production!)
        db.drop_all()
        # Create all tables
        db.create_all()
        
        # Restore migrated data
        try:
            # Restore models in the correct order
            models_restore_order = [
                ('User', User),
                ('PaymentMethod', PaymentMethod),
                ('Subscription', Subscription),
                ('ServerInstance', ServerInstance),
                ('Payment', Payment),
                ('UserCloudStorage', UserCloudStorage)
            ]
            
            for model_name, model_class in models_restore_order:
                if model_name in migrated_data:
                    for record_dict in migrated_data[model_name]:
                        try:
                            # Create a new instance of the model with preserved attributes
                            restored_record = model_class()
                            for key, value in record_dict.items():
                                setattr(restored_record, key, value)
                            
                            # Use merge to handle existing or new records
                            db.session.merge(restored_record)
                        except Exception as e:
                            print(f"Error restoring {model_name} record: {str(e)}")
            
            # Commit all changes
            db.session.commit()
            print("Successfully restored ALL migrated data!")
        except Exception as e:
            print(f"Error restoring migrated data: {str(e)}")
            db.session.rollback()
        
        # Ensure login manager is configured
        login_manager.login_view = 'login'
        
        @login_manager.user_loader
        def load_user(user_id):
            """
            Reload user from the database during each request.
            This ensures that the user object is always fresh.
            """
            try:
                return db.session.get(User, int(user_id))
            except Exception as e:
                print(f"Error loading user {user_id}: {str(e)}")
                return None

# Initialize Stripe products when the app context is pushed
@app.context_processor
def inject_stripe_initialization():
    # This will run when the first request context is created
    initialize_stripe_products()
    return {}

def generate_profile_picture(name, size=100, font_scale=0.5):
    """
    Generate a profile picture with user's initials on a colorful background
    
    Args:
        name (str): Full name of the user
        size (int): Size of the image in pixels
        font_scale (float): Scale of font size relative to image size
    
    Returns:
        str: Base64 encoded image
    """
    # Ensure we have a valid name
    if not name or not isinstance(name, str):
        name = 'Anonymous'
    
    # Enhanced color palette with more nuanced and professional colors
    colors = [
        ('#2196F3', '#1976D2'),  # Blue
        ('#4CAF50', '#388E3C'),  # Green
        ('#FF5722', '#E64A19'),  # Deep Orange
        ('#9C27B0', '#7B1FA2'),  # Purple
        ('#00BCD4', '#0097A7'),  # Cyan
        ('#FF9800', '#F57C00'),  # Orange
        ('#795548', '#5D4037'),  # Brown
        ('#607D8B', '#455A64'),  # Blue Grey
    ]
    
    # Sophisticated text color selection
    def get_text_color(bg_color):
        # Convert hex to RGB
        bg_color = bg_color.lstrip('#')
        rgb = tuple(int(bg_color[i:i+2], 16) for i in (0, 2, 4))
        
        # Calculate luminance
        luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
        
        # Choose text color based on background luminance
        return '#FFFFFF' if luminance < 0.5 else '#000000'
    
    # Sanitize and process name
    name = name.strip()
    name_parts = name.split()
    
    # Generate initials
    if len(name_parts) >= 2:
        initials = f"{name_parts[0][0].upper()}{name_parts[-1][0].upper()}"
    elif len(name_parts) == 1:
        initials = name_parts[0][0].upper()
    else:
        initials = '?'
    
    # Deterministic color selection based on name
    color_index = sum(ord(char) for char in name) % len(colors)
    background_color, gradient_color = colors[color_index]
    text_color = get_text_color(background_color)
    
    # Create image with gradient background
    image = Image.new('RGB', (size, size))
    draw = ImageDraw.Draw(image)
    
    # Create gradient background
    for y in range(size):
        # Linear gradient
        r1 = int(int(background_color[1:3], 16) * (size - y) / size + 
                 int(gradient_color[1:3], 16) * y / size)
        g1 = int(int(background_color[3:5], 16) * (size - y) / size + 
                 int(gradient_color[3:5], 16) * y / size)
        b1 = int(int(background_color[5:7], 16) * (size - y) / size + 
                 int(gradient_color[5:7], 16) * y / size)
        
        draw.line([(0, y), (size, y)], fill=(r1, g1, b1))
    
    # Load a font
    font = None
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
    ]
    
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, size=int(size * font_scale))
            break
        except IOError:
            continue
    
    # Fallback to default if no font found
    if font is None:
        font = ImageFont.load_default()
    
    # Calculate text position
    text_bbox = font.getbbox(initials)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    position = ((size - text_width) / 2, (size - text_height) / 2)
    
    # Draw text with slight shadow for better readability
    # Shadow
    shadow_offset = 1
    draw.text(
        (position[0] + shadow_offset, position[1] + shadow_offset), 
        initials, 
        font=font, 
        fill=(0, 0, 0, 64)  # Transparent black
    )
    
    # Main text
    draw.text(
        position, 
        initials, 
        font=font, 
        fill=text_color
    )
    
    # Save to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    # Encode to base64
    return f"data:image/png;base64,{base64.b64encode(img_byte_arr).decode('utf-8')}"

# Database Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    login_attempts = db.Column(db.Integer, default=0)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    theme = db.Column(db.String(20), default='light')
    email_notifications = db.Column(db.Boolean, default=True)
    marketing_emails = db.Column(db.Boolean, default=False)
    profile_picture = db.Column(db.String(500), nullable=True)
    
    # New fields for payment methods
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    default_payment_method_id = db.Column(db.String(255), nullable=True)
    
    server_instances = db.relationship('ServerInstance', backref='owner', lazy='dynamic')
    user_subscriptions = db.relationship('Subscription', back_populates='user', lazy='dynamic')
    payments = db.relationship('Payment', backref='user', lazy='dynamic')
    payment_methods = db.relationship('PaymentMethod', back_populates='user', lazy='dynamic')
    cloud_storage = db.relationship('UserCloudStorage', back_populates='user')
    planner_tasks_created = db.relationship('PlannerTask', foreign_keys='PlannerTask.creator_id', backref='task_creator')
    planner_tasks_assigned = db.relationship('PlannerTask', foreign_keys='PlannerTask.assigned_to_id', backref='task_assignee')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_stripe_customer(self, stripe_customer_id):
        """Set Stripe customer ID for the user"""
        self.stripe_customer_id = stripe_customer_id
        db.session.commit()

    def add_payment_method(self, payment_method_id, last4, card_type):
        """Add a new payment method for the user"""
        payment_method = PaymentMethod(
            user_id=self.id,
            stripe_payment_method_id=payment_method_id,
            last4=last4,
            card_type=card_type
        )
        db.session.add(payment_method)
        db.session.commit()
        return payment_method

    def reset_login_attempts(self):
        """Reset login attempts after successful login."""
        self.login_attempts = 0
        db.session.commit()

    def increment_login_attempts(self):
        """Increment login attempts."""
        self.login_attempts = (self.login_attempts or 0) + 1
        db.session.commit()

    def get_avatar_color(self):
        """Generate a consistent color for the user's avatar."""
        import hashlib
        
        # Use the user's name or email to generate a consistent color
        hash_input = self.name or self.email or str(self.id)
        hash_object = hashlib.md5(hash_input.encode())
        hash_hex = hash_object.hexdigest()
        
        # Color palettes similar to Google/Microsoft style
        color_palettes = [
            ('#4285F4', '#34A853', '#FBBC05', '#EA4335'),  # Google-inspired
            ('#0078D7', '#107C10', '#D83B01', '#FFB900'),  # Microsoft-inspired
            ('#5C2D91', '#008272', '#107C10', '#D83B01')   # Additional variations
        ]
        
        # Select a palette based on the hash
        palette_index = int(hash_hex[:2], 16) % len(color_palettes)
        color_index = int(hash_hex[2:4], 16) % len(color_palettes[palette_index])
        
        return color_palettes[palette_index][color_index]

    def get_profile_picture(self, size=100):
        """
        Always generate a profile picture based on user's name
        
        Args:
            size (int): Size of the profile picture in pixels
        
        Returns:
            str: Base64 encoded profile picture
        """
        # Always generate picture from name, ignoring stored profile_picture
        return generate_profile_picture(self.name, size=size)

    def __repr__(self):
        return f'<User {self.name}>'

class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    card_type = db.Column(db.String(50), nullable=False)  # visa, mastercard, etc.
    last4 = db.Column(db.String(4), nullable=False)  # Changed from last_four
    encrypted_card_number = db.Column(db.String(255), nullable=False)
    expiry_month = db.Column(db.Integer, nullable=False)
    expiry_year = db.Column(db.Integer, nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    
    # Relationship
    user = relationship("User", back_populates="payment_methods")

    @classmethod
    def create_payment_method(cls, user_id, card_number, expiry_month, expiry_year, card_type):
        # Validate card details
        if not cls.validate_card_number(card_number):
            raise ValueError("Ungültige Kartennummer")
        
        if not cls.validate_expiry_date(expiry_month, expiry_year):
            raise ValueError("Ungültiges Ablaufdatum")
        
        # Encrypt card number
        encrypted_card_number = generate_password_hash(card_number, method='pbkdf2:sha256')
        
        # Determine card type
        card_type = cls.detect_card_type(card_number)
        
        # Create payment method
        payment_method = cls(
            user_id=user_id,
            card_type=card_type,
            last4=card_number[-4:],
            encrypted_card_number=encrypted_card_number,
            expiry_month=int(expiry_month),
            expiry_year=int(expiry_year),
            is_default=False
        )
        
        return payment_method
    
    @staticmethod
    def validate_card_number(card_number):
        # Remove non-digit characters
        card_number = re.sub(r'\D', '', card_number)
        
        # Basic length check
        if len(card_number) < 12 or len(card_number) > 19:
            return False
        
        # Luhn algorithm
        def digits_of(n):
            return [int(d) for d in str(n)]
        
        digits = digits_of(card_number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return checksum % 10 == 0
    
    @staticmethod
    def validate_expiry_date(month, year):
        import datetime
        current_year = datetime.datetime.now().year % 100
        current_month = datetime.datetime.now().month
        
        try:
            month = int(month)
            year = int(year)
        except ValueError:
            return False
        
        return (year > current_year or 
                (year == current_year and month >= current_month))
    
    @staticmethod
    def detect_card_type(card_number):
        card_number = re.sub(r'\D', '', card_number)
        
        # Visa
        if re.match(r'^4', card_number):
            return 'Visa'
        
        # Mastercard
        if re.match(r'^5[1-5]', card_number):
            return 'Mastercard'
        
        # American Express
        if re.match(r'^3[47]', card_number):
            return 'American Express'
        
        return 'Unbekannt'

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_name = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='active')
    
    # New columns
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, overdue
    amount_paid = db.Column(db.Float, default=0.0)
    
    # Relationships
    user = db.relationship('User', back_populates='user_subscriptions')
    payments = db.relationship('Payment', backref='subscription', lazy='dynamic')

    def __repr__(self):
        return f'<Subscription {self.plan_name} for User {self.user_id}>'

class ServerInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=False)
    server_name = db.Column(db.String(100), nullable=False)
    server_type = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50), nullable=False)  # e.g., 'bank_transfer', 'credit_card', 'paypal'
    transaction_id = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='completed')  # completed, pending, failed

class UserCloudStorage(db.Model):
    __tablename__ = 'user_cloud_storage'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String(100), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship('User', back_populates='cloud_storage')

class SharedFile(db.Model):
    __tablename__ = 'shared_files'
    
    id = db.Column(db.Integer, primary_key=True)
    original_file_id = db.Column(db.Integer, db.ForeignKey('user_cloud_storage.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    shared_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    original_file = db.relationship('UserCloudStorage', backref='shared_instances')
    sender = db.relationship('User', foreign_keys=[sender_id])
    recipient = db.relationship('User', foreign_keys=[recipient_id])
    
    def to_dict(self):
        """
        Convert SharedFile instance to a dictionary representation.
        Safely handle cases where sender or original file might be None.
        """
        try:
            # Defensive checks for each attribute
            sender_username = getattr(self.sender, 'username', 'Unknown Sender')
            sender_name = getattr(self.sender, 'name', 'Unknown')
            
            file_name = getattr(self.original_file, 'file_name', 'Unnamed File')
            file_type = getattr(self.original_file, 'file_type', 'Unknown')
            file_size = getattr(self.original_file, 'file_size', 0)
            
            return {
                'id': self.id,
                'original_file_id': self.original_file_id,
                'sender_id': self.sender_id,
                'recipient_id': self.recipient_id,
                'sender_username': sender_username,
                'sender_name': sender_name,
                'file_name': file_name,
                'file_type': file_type,
                'file_size': file_size,
                'status': self.status,
                'shared_at': self.shared_at.isoformat() if self.shared_at else None
            }
        except Exception as e:
            app.logger.error(f"Error converting SharedFile to dict: {str(e)}")
            import traceback
            app.logger.error(traceback.format_exc())
            return {
                'id': self.id,
                'error': 'Failed to convert shared file details',
                'details': str(e)
            }

# Planner Models
class PlannerBoard(db.Model):
    __tablename__ = 'planner_boards'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=False)
    
    owner = db.relationship('User', backref='owned_boards')
    lists = db.relationship('PlannerList', back_populates='board', cascade='all, delete-orphan')
    board_members = db.relationship('BoardMember', back_populates='board', cascade='all, delete-orphan')

class BoardMember(db.Model):
    __tablename__ = 'board_members'
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('planner_boards.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), default='viewer')  # 'viewer', 'editor', 'admin'
    
    board = db.relationship('PlannerBoard', back_populates='board_members')
    user = db.relationship('User', backref='board_memberships')

class PlannerList(db.Model):
    __tablename__ = 'planner_lists'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    board_id = db.Column(db.Integer, db.ForeignKey('planner_boards.id'), nullable=False)
    order = db.Column(db.Integer, default=0)
    
    board = db.relationship('PlannerBoard', back_populates='lists')
    tasks = db.relationship('PlannerTask', back_populates='list', cascade='all, delete-orphan')

class PlannerTask(db.Model):
    __tablename__ = 'planner_tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    list_id = db.Column(db.Integer, db.ForeignKey('planner_lists.id'), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='todo')  # 'todo', 'in_progress', 'done'
    
    list = db.relationship('PlannerList', back_populates='tasks')
    creator = db.relationship('User', foreign_keys=[creator_id])
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id])

# User Loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Forms
class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    """
    Login form for user authentication.
    """
    email = StringField('Email', validators=[DataRequired(), Email()], 
        render_kw={"placeholder": "E-Mail", "class": "form-control"})
    password = PasswordField('Password', validators=[DataRequired()], 
        render_kw={"placeholder": "Passwort", "class": "form-control"})
    submit = SubmitField('Anmelden', 
        render_kw={"class": "btn btn-primary btn-block"})

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=50)])
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

# Planner Forms
class BoardForm(FlaskForm):
    title = StringField('Board Title', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    is_public = BooleanField('Make Board Public')
    submit = SubmitField('Create Board')

class ListForm(FlaskForm):
    title = StringField('List Title', validators=[DataRequired(), Length(min=2, max=100)])
    submit = SubmitField('Create List')

class TaskForm(FlaskForm):
    title = StringField('Task Title', validators=[DataRequired(), Length(min=2, max=200)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    list_id = SelectField('List', coerce=int, validators=[DataRequired()])
    assigned_to = SelectField('Assign To', coerce=int, validators=[])
    due_date = DateField('Due Date', format='%Y-%m-%d', validators=[])
    status = SelectField('Status', choices=[
        ('todo', 'To Do'), 
        ('in_progress', 'In Progress'), 
        ('done', 'Done')
    ], validators=[DataRequired()])
    submit = SubmitField('Create Task')

# Board Invitation Form
class BoardInviteForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Role', choices=[
        ('viewer', 'Viewer'), 
        ('editor', 'Editor'), 
        ('admin', 'Admin')
    ], validators=[DataRequired()])
    submit = SubmitField('Send Invitation')

# Routes
@app.route('/')
def index():
    """
    Main landing page
    """
    try:
        # Define comprehensive plans for homepage
        plans = {
            'starter': {
                'name': 'Starter',
                'monthly_price': 9.99,
                'price': 9.99,  # Duplicate for compatibility
                'description': 'Perfect for small projects and personal use',
                'features': [
                    '1 CPU Core',
                    '2GB RAM',
                    '50GB Storage',
                    'Basic Support'
                ],
                'recommended': False
            },
            'pro': {
                'name': 'Pro',
                'monthly_price': 29.99,
                'price': 29.99,  # Duplicate for compatibility
                'description': 'Ideal for growing businesses and more demanding applications',
                'features': [
                    '2 CPU Cores',
                    '4GB RAM',
                    '100GB Storage',
                    'Priority Support'
                ],
                'recommended': True
            },
            'enterprise': {
                'name': 'Enterprise',
                'monthly_price': 99.99,
                'price': 99.99,  # Duplicate for compatibility
                'description': 'Comprehensive solution for large-scale applications',
                'features': [
                    '4 CPU Cores',
                    '16GB RAM',
                    '500GB Storage',
                    '24/7 Premium Support'
                ],
                'recommended': False
            }
        }

        # Prepare context for the template
        context = {
            'plans': plans,
            'stripe_publishable_key': STRIPE_PUBLISHABLE_KEY
        }

        # If user is authenticated, add user info
        if current_user.is_authenticated:
            context['current_user'] = current_user

        return render_template('index.html', **context)
    except Exception as e:
        # Log the full error details
        app.logger.error(f"Error in index route: {str(e)}", exc_info=True)
        
        # Return a more informative error page
        return render_template('error.html', 
            error='Unable to load the homepage',
            details=str(e)
        ), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    User registration route
    Handles both GET (display form) and POST (process registration) requests
    """
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    # Create signup form
    form = RegisterForm()

    # Handle form submission
    if form.validate_on_submit():
        try:
            # Create new user
            new_user = User(
                username=form.email.data.split('@')[0],  # Use email prefix as username
                email=form.email.data,
                name=form.name.data
            )
            
            # Set password securely
            new_user.set_password(form.password.data)
            
            # Save user to database
            db.session.add(new_user)
            db.session.commit()

            # Create Stripe customer for the new user
            try:
                stripe_customer = stripe.Customer.create(
                    email=new_user.email,
                    name=new_user.name
                )
                new_user.stripe_customer_id = stripe_customer.id
                db.session.commit()
            except stripe.error.StripeError as stripe_error:
                app.logger.error(f"Stripe customer creation error: {str(stripe_error)}")
                # Optionally, you might want to handle this differently
                # For now, we'll continue without a Stripe customer

            # Log the user in
            login_user(new_user)

            # Flash success message
            flash('Account created successfully!', 'success')

            # Redirect to dashboard
            return redirect(url_for('dashboard'))

        except Exception as e:
            # Rollback database session in case of error
            db.session.rollback()
            
            # Log the error
            app.logger.error(f"Registration error: {str(e)}", exc_info=True)
            
            # Flash error message
            flash('An error occurred during registration. Please try again.', 'danger')

    # Render registration template for GET request or invalid POST
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user login.
    """
    # Create login form
    form = LoginForm()

    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    try:
        # Handle form submission
        if form.validate_on_submit():
            # Find user by email
            user = User.query.filter_by(email=form.email.data).first()

            # Check if user exists and password is correct
            if user and user.check_password(form.password.data):
                # Log the user in
                login_user(user)
                
                # Update last login and reset login attempts
                user.last_login = datetime.utcnow()
                user.login_attempts = 0  # Reset attempts on successful login
                db.session.commit()
                
                # Flash a welcome message
                flash('Erfolgreich eingeloggt!', 'success')
                
                return redirect(url_for('dashboard'))
            
            # Invalid credentials
            flash('Ungültige E-Mail oder Passwort', 'error')
            
            # Increment login attempts if user exists
            if user:
                user.login_attempts = (user.login_attempts or 0) + 1
                db.session.commit()
        
        # Render login template with form
        return render_template('login.html', form=form)
    
    except Exception as e:
        # Log any unexpected errors
        app.logger.error(f"Login error: {str(e)}")
        flash('Ein unerwarteter Fehler ist aufgetreten', 'error')
        return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """
    Render the user dashboard with comprehensive user information.
    
    Includes:
    - User profile details
    - Cloud storage information
    - Active files
    - Subscription details
    """
    try:
        # Cloud Storage Usage
        total_storage = 100  # GB
        used_storage = db.session.query(func.sum(UserCloudStorage.file_size)).filter_by(user_id=current_user.id).scalar() or 0
        storage_usage_percent = round((used_storage / (total_storage * 1024 * 1024 * 1024)) * 100, 2)
        
        # Monthly Spending
        monthly_spending = db.session.query(func.sum(Payment.amount)).filter_by(user_id=current_user.id).scalar() or 0
        
        # Active Files
        active_files = UserCloudStorage.query.filter_by(user_id=current_user.id).count()
        
        # Recent Cloud Files
        recent_cloud_files = UserCloudStorage.query.filter_by(user_id=current_user.id).order_by(UserCloudStorage.uploaded_at.desc()).limit(5).all()
        
        # Planner Boards
        boards = PlannerBoard.query.filter(
            (PlannerBoard.owner_id == current_user.id) | 
            (PlannerBoard.board_members.any(user_id=current_user.id))
        ).limit(5).all()
        
        return render_template('dashboard.html', 
                               storage_usage_percent=storage_usage_percent,
                               monthly_spending=monthly_spending,
                               active_files=active_files,
                               recent_cloud_files=recent_cloud_files,
                               boards=boards,
                               current_time=datetime.now())
    except Exception as e:
        app.logger.error(f"Dashboard error for user {current_user.id}: {e}")
        flash('An error occurred while loading your dashboard.', 'error')
        return redirect(url_for('index'))

@app.route('/checkout/<plan>')
@login_required
def checkout(plan):
    """Simplified checkout route"""
    try:
        # Validate plan
        plan_details = STRIPE_PLANS.get(plan)
        if not plan_details:
            flash('Invalid subscription plan', 'danger')
            return redirect(url_for('pricing'))

        # Create a PaymentIntent
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(plan_details['monthly_price'] * 100),  # amount in cents
                currency='usd',
                payment_method_types=['card'],
                metadata={
                    'user_id': current_user.id,
                    'plan': plan
                }
            )
        except stripe.error.StripeError as e:
            app.logger.error(f"Stripe PaymentIntent error: {str(e)}")
            flash('Unable to process payment. Please try again.', 'danger')
            return redirect(url_for('pricing'))

        return render_template(
            'checkout.html', 
            plan_details=plan_details,
            stripe_publishable_key=STRIPE_PUBLISHABLE_KEY,
            client_secret=intent.client_secret,
            user=current_user
        )
    except Exception as e:
        app.logger.error(f"Checkout page error: {str(e)}")
        flash('An unexpected error occurred', 'danger')
        return redirect(url_for('pricing'))

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        # Log the incoming request details
        app.logger.info(f"Checkout session request from user {current_user.id}")
        app.logger.info(f"Request form data: {request.form}")

        # Extract plan from form data
        plan = request.form.get('plan')
        if not plan:
            app.logger.error("No plan specified in checkout request")
            return jsonify({
                'error': 'No plan specified', 
                'details': 'Please select a valid subscription plan'
            }), 400

        # Validate plan exists
        plan_details = STRIPE_PLANS.get(plan)
        if not plan_details:
            app.logger.error(f"Invalid plan requested: {plan}")
            return jsonify({
                'error': 'Invalid plan', 
                'details': f'Plan {plan} does not exist'
            }), 400

        # Validate price ID
        price_id = plan_details.get('price_id')
        if not price_id:
            app.logger.error(f"No price ID found for plan: {plan}")
            return jsonify({
                'error': 'Plan configuration error', 
                'details': 'Unable to find pricing for selected plan'
            }), 500

        # Create Stripe customer if not exists
        try:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.name
            )
        except stripe.error.StripeError as customer_error:
            app.logger.error(f"Stripe customer creation error: {str(customer_error)}")
            return jsonify({
                'error': 'Customer creation failed', 
                'details': str(customer_error)
            }), 500

        # Create a Stripe checkout session with comprehensive options
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='subscription',
                client_reference_id=str(current_user.id),
                customer=customer.id,
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                subscription_data={
                    'metadata': {
                        'user_id': str(current_user.id),
                        'plan': plan,
                        'server_type': plan_details['name']
                    }
                },
                success_url=url_for('subscription_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=url_for('index', _external=True),
                payment_intent_data={
                    'setup_future_usage': 'on_session'
                },
                allow_promotion_codes=True,
                billing_address_collection='auto',
                phone_number_collection={
                    'enabled': True
                },
                custom_text={
                    'submit': {
                        'message': f'Secure your {plan_details["name"]} server hosting plan'
                    }
                }
            )

            # Log successful session creation
            app.logger.info(f"Checkout session created for user {current_user.id}, plan {plan}")

            return jsonify({
                'sessionId': checkout_session.id, 
                'publishableKey': STRIPE_PUBLISHABLE_KEY
            })

        except stripe.error.StripeError as checkout_error:
            app.logger.error(f"Stripe checkout session error: {str(checkout_error)}")
            return jsonify({
                'error': 'Checkout session creation failed', 
                'details': str(checkout_error)
            }), 500

    except Exception as e:
        # Catch-all for any unexpected errors
        app.logger.error(f"Unexpected error in checkout session: {str(e)}")
        return jsonify({
            'error': 'Unexpected error', 
            'details': 'An unexpected error occurred while processing your request'
        }), 500

@app.route('/pricing')
def pricing():
    """
    Pricing page route
    Displays available server hosting plans
    """
    try:
        # Define comprehensive pricing plans
        plans = {
            'starter': {
                'name': 'Starter',
                'price': 9.99,
                'description': 'Perfect for small projects and personal use',
                'features': [
                    '1 CPU Core',
                    '2GB RAM',
                    '50GB Storage',
                    'Basic Support',
                    'Daily Backups',
                    'Shared Resources'
                ],
                'recommended': False
            },
            'pro': {
                'name': 'Pro',
                'price': 29.99,
                'description': 'Ideal for growing businesses and more demanding applications',
                'features': [
                    '2 CPU Cores',
                    '4GB RAM',
                    '100GB Storage',
                    'Priority Support',
                    'Daily Automated Backups',
                    'Dedicated Resources',
                    'SSL Certificate',
                    'Free Domain'
                ],
                'recommended': True
            },
            'enterprise': {
                'name': 'Enterprise',
                'price': 99.99,
                'description': 'Comprehensive solution for large-scale applications',
                'features': [
                    '4 CPU Cores',
                    '16GB RAM',
                    '500GB Storage',
                    '24/7 Dedicated Support',
                    'Advanced Monitoring',
                    'Hourly Backups',
                    'Custom Security Configuration',
                    'Dedicated IP',
                    'Load Balancing',
                    'Free Consultation'
                ],
                'recommended': False
            }
        }

        # Prepare context for the template
        context = {
            'plans': plans,
            'stripe_publishable_key': STRIPE_PUBLISHABLE_KEY
        }

        # If user is authenticated, add user info
        if current_user.is_authenticated:
            context['current_user'] = current_user

        return render_template('pricing.html', **context)
    except Exception as e:
        # Log the full error details
        app.logger.error(f"Error in pricing route: {str(e)}", exc_info=True)
        
        # Return a more informative error page
        return render_template('error.html', 
            error='Unable to load pricing page',
            details=str(e)
        ), 500

@app.route('/payment-methods/set-default', methods=['POST'])
@login_required
def set_payment_method_default():
    """Set a payment method as the default for the user"""
    try:
        data = request.get_json()
        method_id = data.get('method_id')
        
        if not method_id:
            return jsonify({'success': False, 'message': 'Invalid payment method'}), 400
        
        # Find the payment method
        payment_method = PaymentMethod.query.filter_by(
            id=method_id, 
            user_id=current_user.id
        ).first()
        
        if not payment_method:
            return jsonify({'success': False, 'message': 'Payment method not found'}), 404
        
        # Update Stripe customer's default payment method
        stripe.Customer.modify(
            current_user.stripe_customer_id,
            invoice_settings={'default_payment_method': payment_method.stripe_payment_method_id}
        )
        
        # Reset all other payment methods to non-default
        PaymentMethod.query.filter_by(user_id=current_user.id).update({'is_default': False})
        
        # Set this method as default
        payment_method.is_default = True
        current_user.default_payment_method_id = payment_method.stripe_payment_method_id
        db.session.commit()
        
        return jsonify({'success': True})
    
    except stripe.error.StripeError as e:
        db.session.rollback()
        app.logger.error(f"Stripe error setting default payment method: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error setting default payment method: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred'}), 500

@app.route('/payment-methods/delete', methods=['POST'])
@login_required
def remove_payment_method():
    """Delete a payment method for the user"""
    try:
        data = request.get_json()
        method_id = data.get('method_id')
        
        if not method_id:
            return jsonify({'success': False, 'message': 'Invalid payment method'}), 400
        
        # Find the payment method
        payment_method = PaymentMethod.query.filter_by(
            id=method_id, 
            user_id=current_user.id
        ).first()
        
        if not payment_method:
            return jsonify({'success': False, 'message': 'Payment method not found'}), 404
        
        # Prevent deleting the last payment method
        user_payment_methods = PaymentMethod.query.filter_by(user_id=current_user.id).count()
        if user_payment_methods <= 1:
            return jsonify({
                'success': False, 
                'message': 'You must have at least one payment method'
            }), 400
        
        # Remove from Stripe
        stripe.PaymentMethod.detach(payment_method.stripe_payment_method_id)
        
        # If this was the default method, set another method as default
        if payment_method.is_default:
            alternative_method = PaymentMethod.query.filter(
                PaymentMethod.user_id == current_user.id, 
                PaymentMethod.id != method_id
            ).first()
            
            if alternative_method:
                alternative_method.is_default = True
                stripe.Customer.modify(
                    current_user.stripe_customer_id,
                    invoice_settings={'default_payment_method': alternative_method.stripe_payment_method_id}
                )
        
        # Delete the payment method
        db.session.delete(payment_method)
        db.session.commit()
        
        return jsonify({'success': True})
    
    except stripe.error.StripeError as e:
        db.session.rollback()
        app.logger.error(f"Stripe error deleting payment method: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting payment method: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred'}), 500

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """
    Contact page route
    Allows users to send messages or inquiries
    """
    try:
        # If using a form, you would create a ContactForm here
        # For now, this is a placeholder route
        return render_template('contact.html', 
            current_user=current_user if current_user.is_authenticated else None
        )
    except Exception as e:
        # Log the full error details
        app.logger.error(f"Error in contact route: {str(e)}", exc_info=True)
        
        # Return a more informative error page
        return render_template('error.html', 
            error='Unable to load contact page',
            details=str(e)
        ), 500

@app.route('/subscription/success')
@login_required
def subscription_success():
    """
    Subscription success page after successful payment
    """
    try:
        # Get session ID from Stripe
        session_id = request.args.get('session_id')
        if not session_id:
            flash('Invalid checkout session', 'danger')
            return redirect(url_for('dashboard'))

        # Retrieve the Checkout Session
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError as e:
            app.logger.error(f"Stripe session retrieval error: {str(e)}")
            flash('Unable to verify payment', 'danger')
            return redirect(url_for('dashboard'))

        # Validate the session belongs to the current user
        if str(current_user.id) != checkout_session.client_reference_id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('dashboard'))

        # Extract plan details from session metadata
        plan_key = checkout_session.metadata.get('plan', 'starter')
        
        # Define plan details
        plans = {
            'starter': {
                'name': 'Starter',
                'price': 9.99,
                'features': [
                    '1 CPU Core',
                    '2GB RAM',
                    '50GB Storage',
                    'Basic Support'
                ]
            }
            # Add more plans as needed
        }

        # Validate plan
        plan = plans.get(plan_key, plans['starter'])

        # Retrieve the subscription from Stripe
        try:
            stripe_subscription = stripe.Subscription.retrieve(
                checkout_session.subscription
            )
        except stripe.error.StripeError as e:
            app.logger.error(f"Stripe subscription retrieval error: {str(e)}")
            flash('Unable to retrieve subscription details', 'danger')
            return redirect(url_for('dashboard'))

        # Create or update local subscription
        subscription = Subscription(
            user_id=current_user.id,
            plan_name=plan_key,
            start_date=datetime.utcfromtimestamp(stripe_subscription.start_date),
            status='active',
            payment_status='paid',
            amount_paid=plan['price']
        )
        db.session.add(subscription)
        db.session.flush()  # Get the ID before committing

        # Create server instance
        server_instance = ServerInstance(
            user_id=current_user.id,
            subscription_id=subscription.id,
            server_name=f"{current_user.name}'s {plan['name']} Server",
            server_type=plan_key.lower(),
            status='active'
        )
        db.session.add(server_instance)

        # Save payment method if available
        if checkout_session.payment_method:
            try:
                payment_method = stripe.PaymentMethod.retrieve(
                    checkout_session.payment_method
                )
                
                # Check if payment method already exists
                existing_method = PaymentMethod.query.filter_by(
                    stripe_payment_method_id=payment_method.id
                ).first()

                if not existing_method:
                    new_payment_method = PaymentMethod(
                        user_id=current_user.id,
                        stripe_payment_method_id=payment_method.id,
                        last4=payment_method.card.last4,
                        brand=payment_method.card.brand,
                        exp_month=payment_method.card.exp_month,
                        exp_year=payment_method.card.exp_year,
                        is_default=True
                    )
                    db.session.add(new_payment_method)

                    # Update user's default payment method
                    current_user.default_payment_method_id = new_payment_method.stripe_payment_method_id
            except stripe.error.StripeError as e:
                app.logger.error(f"Error retrieving payment method: {str(e)}")

        # Commit all changes
        db.session.commit()

        return render_template(
            'subscription_success.html', 
            plan=plan,
            subscription=subscription,
            server_instance=server_instance
        )
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Subscription success page error: {str(e)}")
        flash('An unexpected error occurred', 'danger')
        return redirect(url_for('dashboard'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        'error': 'Datei zu groß. Maximale Dateigröße: 5 GB'
    }), 413

@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error(f"Internal Server Error: {str(error)}")
    return jsonify({
        'error': 'Ein interner Serverfehler ist aufgetreten. Bitte versuchen Sie es später erneut.'
    }), 500

# Ensure user storage directory exists with proper permissions
USER_STORAGE_BASE_DIR = os.path.join(app.root_path, 'user_storage')
os.makedirs(USER_STORAGE_BASE_DIR, exist_ok=True)
os.chmod(USER_STORAGE_BASE_DIR, 0o755)  # rwxr-x

def get_user_storage_path(user_id):
    """
    Generate a unique storage path for a user's files with proper permissions.
    
    Args:
        user_id (int): The ID of the user.
    
    Returns:
        str: Absolute path to the user's storage directory.
    
    Raises:
        OSError: If directory creation or permission setting fails.
    """
    try:
        # Convert user_id to string to prevent any path traversal
        user_id_str = str(int(user_id))
        
        # Create user-specific directory
        user_storage_dir = os.path.join(USER_STORAGE_BASE_DIR, user_id_str)
        
        # Create directory with proper permissions
        try:
            os.makedirs(user_storage_dir, mode=0o700, exist_ok=True)
            app.logger.info(f"Created user storage directory: {user_storage_dir}")
        except OSError as dir_error:
            app.logger.error(f"Failed to create user storage directory: {dir_error}")
            raise
        
        # Ensure correct ownership and permissions
        try:
            os.chmod(user_storage_dir, 0o700)  # rwx------
            
            app.logger.info(f"Set permissions for {user_storage_dir}")
        except Exception as ownership_error:
            app.logger.warning(f"Could not set directory ownership: {ownership_error}")
            # Fallback: ensure at least the base directory has correct permissions
            os.chmod(user_storage_dir, 0o700)
        
        return user_storage_dir
    except Exception as e:
        app.logger.error(f"Comprehensive error creating user storage directory: {e}")
        raise

@app.route('/cloud/upload', methods=['POST'])
@login_required
def upload_file():
    # Log request details for debugging
    app.logger.info(f"Upload request headers: {request.headers}")
    app.logger.info(f"Request content type: {request.content_type}")
    app.logger.info(f"Request method: {request.method}")
    app.logger.info(f"Request data: {request.data}")
    app.logger.info(f"Request form: {request.form}")
    app.logger.info(f"Request files: {request.files}")
    
    # Logging for debugging
    app.logger.info(f"Upload attempt by user {current_user.id}")
    app.logger.info(f"Request method: {request.method}")
    app.logger.info(f"Request content type: {request.content_type}")
    
    # Log all incoming files and their details
    app.logger.info(f"Incoming files: {request.files}")
    app.logger.info(f"Incoming form data: {request.form}")

    # Check if file is present
    if 'file' not in request.files:
        app.logger.warning(f"No file in request by user {current_user.id}")
        return jsonify({'error': 'Keine Datei ausgewählt'}), 400
    
    file = request.files['file']
    
    # Log file details
    app.logger.info(f"File details: name={file.filename}, content_type={file.content_type}")
    
    # Check if filename is empty
    if file.filename == '':
        app.logger.warning(f"Empty filename for upload by user {current_user.id}")
        return jsonify({'error': 'Keine Datei ausgewählt'}), 400

    # Validate file size
    MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB
    
    # Get file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    app.logger.info(f"File size: {file_size} bytes")
    
    # Check file size
    if file_size > MAX_FILE_SIZE:
        app.logger.warning(f"File too large: {file_size} bytes by user {current_user.id}")
        return jsonify({
            'error': f'Datei zu groß. Maximale Dateigröße: 5 GB (Ihre Datei: {file_size / (1024 * 1024):.2f} MB)'
        }), 400

    # Check user's total storage
    total_storage = db.session.query(func.sum(UserCloudStorage.file_size)).filter_by(user_id=current_user.id).scalar() or 0
    
    app.logger.info(f"Current user storage: {total_storage} bytes")
    
    if total_storage + file_size > MAX_FILE_SIZE:
        app.logger.warning(f"Storage limit exceeded for user {current_user.id}")
        return jsonify({
            'error': 'Speicherlimit überschritten. Bitte löschen Sie einige Dateien.'
        }), 400
    
    # Generate unique filename
    unique_filename = f"{secure_filename(file.filename)}"
    user_storage_path = get_user_storage_path(current_user.id)
    file_path = os.path.join(user_storage_path, unique_filename)
    
    try:
        # Save file
        file.save(file_path)
        
        app.logger.info(f"File saved: {file_path}")
        
        # Create database record
        cloud_file = UserCloudStorage(
            user_id=current_user.id,
            file_name=file.filename,
            file_path=file_path,
            file_size=file_size,
            file_type=file.content_type or 'application/octet-stream'
        )
        
        db.session.add(cloud_file)
        db.session.commit()
        
        app.logger.info(f"File record created for user {current_user.id}")
        
        return jsonify({
            'id': cloud_file.id,
            'filename': unique_filename,
            'message': 'Datei erfolgreich hochgeladen'
        }), 200
    
    except Exception as e:
        # Rollback database transaction
        db.session.rollback()
        
        # Remove partially uploaded file if it exists
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Log the error
        app.logger.error(f"File upload error for user {current_user.id}: {str(e)}")
        
        return jsonify({
            'error': 'Fehler beim Datei-Upload. Bitte versuchen Sie es erneut.'
        }), 500

@app.route('/cloud/files', methods=['GET'])
@login_required
def list_cloud_files():
    """
    List cloud files for the current user.
    
    Returns:
        JSON list of cloud files with their details
    """
    try:
        # Retrieve cloud storage files
        cloud_files = UserCloudStorage.query.filter_by(user_id=current_user.id).all()
        
        # Convert to list of dictionaries for JSON serialization
        file_list = [
            {
                'id': file.id,  # Add this line to provide the file ID
                'filename': file.file_name, 
                'size': file.file_size, 
                'type': file.file_type,
                'uploaded_at': file.uploaded_at.isoformat() if file.uploaded_at else None,
                'path': file.file_path
            } for file in cloud_files
        ]
        
        return jsonify(file_list)
    except Exception as e:
        app.logger.error(f"Error listing cloud files: {e}")
        return jsonify({'error': 'Failed to retrieve cloud files'}), 500

@app.route('/cloud')
@login_required
def cloud_storage():
    return render_template('cloud_storage.html')

@app.route('/dashboard/add_payment_method', methods=['POST'])
@login_required
def add_payment_method():
    """Add a new payment method for the user"""
    try:
        # Get JSON data
        data = request.get_json()
        
        # Validate input
        card_number = data.get('card_number', '').replace(' ', '')
        expiry_month = data.get('expiry_month')
        expiry_year = data.get('expiry_year')
        
        # Basic validation
        if not all([card_number, expiry_month, expiry_year]):
            return jsonify({'success': False, 'message': 'Incomplete card details'}), 400
        
        # Validate card number length and type
        card_type = 'unknown'
        if re.match(r'^4\d{15}$', card_number):
            card_type = 'visa'
        elif re.match(r'^5[1-5]\d{14}$', card_number):
            card_type = 'mastercard'
        elif re.match(r'^3[47]\d{13}$', card_number):
            card_type = 'amex'
        
        # Create new payment method
        new_method = PaymentMethod(
            user_id=current_user.id,
            card_type=card_type,
            last4=card_number[-4:],
            expiry_month=int(expiry_month),
            expiry_year=int(expiry_year),
            is_default=data.get('set_as_default', False)
        )
        
        # Reset other default methods if this is set as default
        if new_method.is_default:
            PaymentMethod.query.filter_by(user_id=current_user.id).update({'is_default': False})
        
        # Save to database
        db.session.add(new_method)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Payment method added successfully',
            'method': {
                'id': new_method.id,
                'card_type': new_method.card_type,
                'last4': new_method.last4,
                'is_default': new_method.is_default
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error adding payment method: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/dashboard/set_default_payment_method/<int:method_id>', methods=['POST'])
@login_required
def set_default_payment_method(method_id):
    """Set a payment method as the default for the user"""
    try:
        # Find the payment method
        method = PaymentMethod.query.filter_by(id=method_id, user_id=current_user.id).first()
        
        if not method:
            return jsonify({'success': False, 'message': 'Payment method not found'}), 404
        
        # Reset other default methods
        PaymentMethod.query.filter_by(user_id=current_user.id).update({'is_default': False})
        
        # Set this method as default
        method.is_default = True
        
        # Update Stripe customer's default payment method
        try:
            stripe.Customer.modify(
                current_user.stripe_customer_id,
                invoice_settings={
                    'default_payment_method': method.stripe_payment_method_id
                }
            )
        except Exception as e:
            app.logger.error(f"Stripe default payment method error: {str(e)}")
            return jsonify({'success': False, 'message': 'Failed to update default payment method'}), 500
        
        # Commit changes
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Default payment method updated'}), 200
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error setting default payment method: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred'}), 500

@app.route('/dashboard/delete_payment_method/<int:method_id>', methods=['DELETE'])
@login_required
def delete_payment_method(method_id):
    """Delete a payment method for the user"""
    try:
        # Find the payment method
        method = PaymentMethod.query.filter_by(id=method_id, user_id=current_user.id).first()
        
        if not method:
            return jsonify({'success': False, 'message': 'Payment method not found'}), 404
        
        # Prevent deleting the last payment method
        remaining_methods = PaymentMethod.query.filter_by(user_id=current_user.id).count()
        if remaining_methods <= 1:
            return jsonify({
                'success': False, 
                'message': 'You must have at least one payment method'
            }), 400
        
        # Detach from Stripe
        try:
            stripe.PaymentMethod.detach(method.stripe_payment_method_id)
        except Exception as e:
            app.logger.error(f"Stripe payment method detach error: {str(e)}")
            # Continue even if Stripe detach fails
        
        # Delete the payment method
        db.session.delete(method)
        
        # If this was the default method, set another method as default
        if method.is_default:
            new_default_method = PaymentMethod.query.filter_by(user_id=current_user.id).first()
            if new_default_method:
                new_default_method.is_default = True
                
                # Update Stripe customer's default payment method
                try:
                    stripe.Customer.modify(
                        current_user.stripe_customer_id,
                        invoice_settings={
                            'default_payment_method': new_default_method.stripe_payment_method_id
                        }
                    )
                except Exception as e:
                    app.logger.error(f"Stripe default payment method error: {str(e)}")
        
        # Commit changes
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Payment method deleted successfully'}), 200
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting payment method: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred'}), 500

@app.route('/log-client-error', methods=['POST'])
def log_client_error():
    try:
        error_data = request.json
        app.logger.error(f"Client-Side Error: {error_data}")
        return jsonify({"status": "logged"}), 200
    except Exception as e:
        app.logger.error(f"Error logging client-side error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/payment-methods/new', methods=['GET', 'POST'])
@login_required
@csrf.exempt  # Optional: remove if you want CSRF protection
def create_payment_method():
    if request.method == 'POST':
        try:
            data = request.form
            card_number = data.get('card_number', '').replace(' ', '')
            expiry_month = data.get('expiry_month')
            expiry_year = data.get('expiry_year')
            
            # Validate input
            if not all([card_number, expiry_month, expiry_year]):
                flash('Bitte alle Felder ausfüllen', 'error')
                return redirect(url_for('create_payment_method'))
            
            # Validate card number length and type
            card_type = 'unknown'
            if re.match(r'^4\d{15}$', card_number):
                card_type = 'visa'
            elif re.match(r'^5[1-5]\d{14}$', card_number):
                card_type = 'mastercard'
            elif re.match(r'^3[47]\d{13}$', card_number):
                card_type = 'amex'
            
            # Create new payment method
            new_method = PaymentMethod(
                user_id=current_user.id,
                card_type=card_type,
                last4=card_number[-4:],
                expiry_month=int(expiry_month),
                expiry_year=int(expiry_year),
                is_default=data.get('set_as_default', False)
            )
            
            # Reset other default methods if this is set as default
            if new_method.is_default:
                PaymentMethod.query.filter_by(user_id=current_user.id).update({'is_default': False})
            
            # Save to database
            db.session.add(new_method)
            db.session.commit()
            
            flash('Zahlungsmethode erfolgreich hinzugefügt', 'success')
            return redirect(url_for('dashboard'))
        
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('create_payment_method'))
        except Exception as e:
            app.logger.error(f"Fehler beim Hinzufügen der Zahlungsmethode: {e}")
            flash('Ein unerwarteter Fehler ist aufgetreten', 'error')
            return redirect(url_for('create_payment_method'))
    
    return render_template('add_payment_method.html', current_year=datetime.now().year)

# Add cloud storage routes for code editor
@app.route('/cloud/code/list', methods=['GET'])
@login_required
def list_cloud_code_files():
    """List code files in user's cloud storage."""
    user_cloud_dir = get_user_code_storage_path(current_user.id)
    
    # Ensure the directory exists
    os.makedirs(user_cloud_dir, exist_ok=True)
    
    # Get list of code files
    try:
        code_files = [f for f in os.listdir(user_cloud_dir) if os.path.isfile(os.path.join(user_cloud_dir, f))]
        return jsonify(code_files)
    except Exception as e:
        app.logger.error(f"Error listing code files: {str(e)}")
        return jsonify([])  # Return empty list if error occurs

@app.route('/cloud/code/save', methods=['POST'])
@login_required
def save_cloud_code_file():
    """Save a code file to user's cloud storage."""
    data = request.json
    filename = data.get('filename')
    content = data.get('content')
    language = data.get('language', 'text')
    
    if not filename or not content:
        return jsonify({'error': 'Filename and content are required'}), 400
    
    # Sanitize filename and ensure it has an extension
    if '.' not in filename:
        filename = f"{filename}.{language}"
    
    # Ensure unique filename
    user_cloud_dir = get_user_code_storage_path(current_user.id)
    filepath = os.path.join(user_cloud_dir, filename)
    
    try:
        # Save file
        with open(filepath, 'w') as f:
            f.write(content)
        
        # Optional: Create a database record for the file
        try:
            new_file = UserCloudStorage(
                user_id=current_user.id,
                file_name=filename,
                file_path=filepath,
                file_size=len(content),
                file_type=language
            )
            db.session.add(new_file)
            db.session.commit()
        except Exception as db_error:
            app.logger.warning(f"Could not create database record: {str(db_error)}")
        
        return jsonify({
            'success': True, 
            'message': f'File {filename} saved successfully',
            'filepath': filepath
        }), 200
    except Exception as e:
        app.logger.error(f"Error saving code file: {str(e)}")
        return jsonify({
            'error': f'Failed to save file: {str(e)}'
        }), 500

@app.route('/cloud/code/load/<filename>', methods=['GET'])
@login_required
def load_cloud_code_file(filename):
    """Load a specific code file from user's cloud storage."""
    # Sanitize filename
    filename = secure_filename(filename)
    
    user_cloud_dir = get_user_code_storage_path(current_user.id)
    filepath = os.path.join(user_cloud_dir, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Determine language from file extension
        language = filename.split('.')[-1] if '.' in filename else 'text'
        
        return jsonify({
            'filename': filename,
            'content': content,
            'language': language
        }), 200
    except Exception as e:
        app.logger.error(f"Error loading code file: {str(e)}")
        return jsonify({
            'error': f'Failed to read file: {str(e)}'
        }), 500

@app.route('/cloud/code/delete/<filename>', methods=['DELETE'])
@login_required
def delete_cloud_code_file(filename):
    """Delete a specific code file from user's cloud storage."""
    # Sanitize filename
    filename = secure_filename(filename)
    
    user_cloud_dir = get_user_code_storage_path(current_user.id)
    filepath = os.path.join(user_cloud_dir, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        # Delete physical file
        os.remove(filepath)
        
        # Optional: Remove database record
        try:
            file_to_delete = UserCloudStorage.query.filter_by(
                user_id=current_user.id, 
                file_name=filename
            ).first()
            if file_to_delete:
                db.session.delete(file_to_delete)
                db.session.commit()
        except Exception as db_error:
            app.logger.warning(f"Could not delete database record: {str(db_error)}")
        
        return jsonify({
            'success': True, 
            'message': f'File {filename} deleted successfully'
        }), 200
    except Exception as e:
        app.logger.error(f"Error deleting code file: {str(e)}")
        return jsonify({
            'error': f'Failed to delete file: {str(e)}'
        }), 500

@app.route('/code-editor')
@login_required
def code_editor():
    """
    Render the code editor page for the logged-in user.
    
    Ensures that only authenticated users can access the code editor.
    Provides context for the user's existing files and cloud files.
    
    Returns:
        Rendered code editor template with user context
    """
    try:
        # Retrieve cloud files
        cloud_files = UserCloudStorage.query.filter_by(user_id=current_user.id).all()
        
        # Ensure user's code storage directory exists
        user_code_dir = get_user_code_storage_path(current_user.id)
        
        # Get local code files
        try:
            local_code_files = [
                {
                    'name': f, 
                    'path': os.path.join(user_code_dir, f),
                    'size': os.path.getsize(os.path.join(user_code_dir, f))
                } 
                for f in os.listdir(user_code_dir) 
                if os.path.isfile(os.path.join(user_code_dir, f))
            ]
        except Exception as list_error:
            app.logger.warning(f"Could not list local code files for user {current_user.id}: {list_error}")
            local_code_files = []
        
        return render_template(
            'code_editor.html', 
            user=current_user, 
            cloud_files=cloud_files,
            local_code_files=local_code_files
        )
    except Exception as e:
        app.logger.error(f"Error rendering code editor for user {current_user.id}: {e}")
        flash('An error occurred while loading the code editor. Please try again.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/cloud/storage-info', methods=['GET'])
@login_required
def get_storage_info():
    """
    Get comprehensive storage information for the current user.
    """
    try:
        # Total storage limit (5 GB)
        TOTAL_STORAGE_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB
        
        # Get all cloud storage files for the user
        cloud_files = UserCloudStorage.query.filter_by(user_id=current_user.id).all()
        
        # Calculate total storage used
        total_size = sum(file.file_size for file in cloud_files)
        
        # Ensure total_size is a valid number
        total_size = max(0, total_size)
        
        # Convert to human-readable format
        def convert_size(size_in_bytes):
            if size_in_bytes < 1024:
                return f"{size_in_bytes} B"
            elif size_in_bytes < 1024 * 1024:
                return f"{size_in_bytes/1024:.2f} KB"
            elif size_in_bytes < 1024 * 1024 * 1024:
                return f"{size_in_bytes/(1024*1024):.2f} MB"
            else:
                return f"{size_in_bytes/(1024*1024*1024):.2f} GB"
        
        # Calculate percentage used
        percent_used = (total_size / TOTAL_STORAGE_BYTES) * 100 if TOTAL_STORAGE_BYTES > 0 else 0
        
        # Improve file type detection
        def get_file_type(filename):
            if not filename:
                return "Unknown File"
            ext = os.path.splitext(filename)[1].lower()
            type_map = {
                '.txt': 'Text File',
                '.pdf': 'PDF Document',
                '.docx': 'Word Document',
                '.xlsx': 'Excel Spreadsheet',
                '.jpg': 'Image',
                '.jpeg': 'Image',
                '.png': 'Image',
                '.gif': 'Image',
                '.py': 'Python Script',
                '.js': 'JavaScript File',
                '.html': 'HTML File',
                '.css': 'CSS File'
            }
            return type_map.get(ext, f"{ext.upper().replace('.', '')} File")
        
        storage_info = {
            'total_storage': TOTAL_STORAGE_BYTES,
            'used_storage': total_size,
            'used_storage_human': convert_size(total_size),
            'percent_used': round(percent_used, 2),
            'total_files': len(cloud_files),
            'files': [
                {
                    'name': file.file_name,
                    'size': convert_size(file.file_size),
                    'size_bytes': file.file_size,
                    'type': get_file_type(file.file_name),
                    'uploaded_at': file.uploaded_at.isoformat() if file.uploaded_at else None
                } for file in cloud_files
            ]
        }
        
        return jsonify(storage_info)
    except Exception as e:
        app.logger.error(f"Error retrieving storage information: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({
            'total_storage': 5 * 1024 * 1024 * 1024,  # 5 GB
            'used_storage': 0,
            'used_storage_human': '0 GB',
            'percent_used': 0,
            'total_files': 0,
            'files': [],
            'error': 'Failed to retrieve storage information'
        }), 500

@app.route('/server-instances')
@login_required
def server_instances():
    """
    Render a page showing the user's server instances.
    
    Returns:
        Rendered template with server instances details
    """
    try:
        # Fetch server instances for the current user
        instances = ServerInstance.query.filter_by(user_id=current_user.id).all()
        
        return render_template('server_instances.html', 
                               server_instances=instances, 
                               title='Server Instances')
    except Exception as e:
        app.logger.error(f"Error fetching server instances for user {current_user.id}: {e}")
        flash('Unable to retrieve server instances. Please try again later.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/billing')
@login_required
def billing():
    """
    Redirect to pricing page for billing management.
    
    This route serves as a fallback for billing-related actions,
    guiding users to the pricing and subscription management page.
    """
    flash('Manage your subscription and billing details on the pricing page.', 'info')
    return redirect(url_for('pricing'))

@app.route('/cloud/files/search-users', methods=['GET'])
@login_required
def search_users_for_sharing():
    """
    Search for users to share files with.
    Excludes the current user and returns usernames matching the query.
    """
    query = request.args.get('query', '').strip()
    
    if not query:
        return jsonify([])
    
    # Search for users with matching username or email, excluding current user
    matching_users = User.query.filter(
        db.or_(
            User.username.ilike(f'%{query}%'), 
            User.email.ilike(f'%{query}%')
        ), 
        User.id != current_user.id
    ).limit(10).all()
    
    return jsonify([
        {
            'id': user.id, 
            'username': user.username, 
            'email': user.email
        } for user in matching_users
    ])

@app.route('/cloud/files/<int:file_id>/share', methods=['POST'])
@login_required
def share_cloud_file(file_id):
    """
    Share a cloud file with selected users.
    """
    # Ensure request is JSON
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    
    data = request.get_json()
    recipient_ids = data.get('recipient_ids', [])
    
    # Validate input
    if not recipient_ids or not isinstance(recipient_ids, list):
        return jsonify({'error': 'Invalid recipient list'}), 400
    
    # Validate file ownership
    file = UserCloudStorage.query.filter_by(id=file_id, user_id=current_user.id).first()
    if not file:
        return jsonify({'error': 'File not found or not owned by you'}), 404
    
    # Validate recipients
    recipients = User.query.filter(
        User.id.in_(recipient_ids),
        User.id != current_user.id
    ).all()
    
    # Check if any recipients are invalid
    if len(recipients) != len(recipient_ids):
        return jsonify({'error': 'One or more recipients are invalid'}), 400
    
    shared_files = []
    for recipient in recipients:
        # Check if file is already shared with this user
        existing_share = SharedFile.query.filter_by(
            original_file_id=file_id, 
            sender_id=current_user.id, 
            recipient_id=recipient.id,
            status='pending'
        ).first()
        
        if existing_share:
            continue  # Skip if already shared
        
        # Create a shared file entry
        shared_file = SharedFile(
            original_file_id=file_id,
            sender_id=current_user.id,
            recipient_id=recipient.id,
            status='pending'
        )
        db.session.add(shared_file)
        shared_files.append(shared_file.to_dict())
    
    try:
        db.session.commit()
        
        # Optional: Send notification email
        for recipient in recipients:
            try:
                send_share_notification_email(
                    recipient_email=recipient.email, 
                    sender_name=current_user.username, 
                    file_name=file.file_name
                )
            except Exception as email_error:
                app.logger.error(f"Failed to send share notification email: {email_error}")
        
        return jsonify({
            'message': f'File shared with {len(recipients)} user(s)',
            'shared_files': shared_files
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error sharing file: {str(e)}")
        return jsonify({'error': 'Failed to share file', 'details': str(e)}), 500

def send_share_notification_email(recipient_email, sender_name, file_name):
    """
    Send an email notification about a shared file.
    """
    subject = f"{sender_name} shared a file with you"
    body = f"""
    Hello,

    {sender_name} has shared a file named '{file_name}' with you on SideForge.
    
    Please log in to your account to view and accept the shared file.

    Best regards,
    SideForge Team
    """
    
    # Use your existing email sending mechanism
    send_email(
        to_email=recipient_email, 
        subject=subject, 
        body=body
    )

@app.route('/cloud/files/shared', methods=['GET'])
@login_required
def get_shared_files():
    """
    Retrieve shared files for the current user.
    """
    try:
        # Get pending and accepted shared files for the current user
        from sqlalchemy import or_
        
        shared_files = SharedFile.query.filter(
            SharedFile.recipient_id == current_user.id,
            or_(
                SharedFile.status == 'pending', 
                SharedFile.status == 'accepted'
            )
        ).all()
        
        # Debug logging
        app.logger.info(f"Found {len(shared_files)} shared files for user {current_user.id}")
        
        # Detailed logging for each shared file
        for sf in shared_files:
            app.logger.info(f"Shared File Details: ID={sf.id}, Sender={sf.sender_id}, "
                            f"Original File={sf.original_file_id}, Status={sf.status}")
        
        # Convert shared files to dictionary
        shared_files_dict = [sf.to_dict() for sf in shared_files]
        
        return jsonify(shared_files_dict)
    except Exception as e:
        app.logger.error(f"Error retrieving shared files: {str(e)}")
        # Include the full traceback for more detailed error information
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({'error': 'Failed to retrieve shared files', 'details': str(e)}), 500

@app.route('/cloud/files/shared/<int:shared_file_id>/accept', methods=['POST'])
@login_required
def accept_shared_file(shared_file_id):
    """
    Accept a shared file, which copies it to the recipient's cloud storage.
    """
    shared_file = SharedFile.query.filter_by(
        id=shared_file_id, 
        recipient_id=current_user.id, 
        status='pending'
    ).first()
    
    if not shared_file:
        return jsonify({'error': 'Shared file not found or already processed'}), 404
    
    # Copy the original file to recipient's cloud storage
    original_file = shared_file.original_file
    new_file = UserCloudStorage(
        user_id=current_user.id,
        file_name=f"Shared_{original_file.file_name}",
        file_path=original_file.file_path,
        file_type=original_file.file_type,
        file_size=original_file.file_size
    )
    
    db.session.add(new_file)
    
    # Update shared file status
    shared_file.status = 'accepted'
    
    try:
        db.session.commit()
        
        # Optional: Send notification email
        for recipient in recipients:
            try:
                send_share_notification_email(
                    recipient_email=recipient.email, 
                    sender_name=current_user.username, 
                    file_name=file.file_name
                )
            except Exception as email_error:
                app.logger.error(f"Failed to send share notification email: {email_error}")
        
        return jsonify({
            'message': 'File successfully accepted and added to your cloud storage',
            'file': new_file.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error accepting shared file: {str(e)}")
        return jsonify({'error': 'Failed to accept file', 'details': str(e)}), 500

@app.route('/cloud/files/shared/<int:shared_file_id>/reject', methods=['POST'])
@login_required
def reject_shared_file(shared_file_id):
    """
    Reject a shared file.
    """
    shared_file = SharedFile.query.filter_by(
        id=shared_file_id, 
        recipient_id=current_user.id, 
        status='pending'
    ).first()
    
    if not shared_file:
        return jsonify({'error': 'Shared file not found or already processed'}), 404
    
    # Update shared file status
    shared_file.status = 'rejected'
    
    try:
        db.session.commit()
        return jsonify({'message': 'File share request rejected'}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error rejecting shared file: {str(e)}")
        return jsonify({'error': 'Failed to reject file', 'details': str(e)}), 500

@app.route('/account', methods=['GET'])
@login_required
def account():
    """
    Render the account settings page for the current user.
    """
    try:
        # Fetch additional user details if needed
        user_details = {
            'name': current_user.name,
            'email': current_user.email,
            'username': current_user.username,
            'theme': getattr(current_user, 'theme', 'light'),
            'two_factor_enabled': getattr(current_user, 'two_factor_enabled', False),
            'email_notifications': getattr(current_user, 'email_notifications', True),
            'marketing_emails': getattr(current_user, 'marketing_emails', False),
            'subscription': {
                'plan_name': 'Basic Plan',  # Replace with actual subscription logic
                'next_billing_date': datetime.now() + timedelta(days=30)
            },
            'payment_methods': []  # Replace with actual payment method retrieval
        }

        return render_template('account.html', user=user_details)
    except Exception as e:
        app.logger.error(f"Account page error for user {current_user.id}: {str(e)}")
        flash('An error occurred while loading your account page.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/account/update-profile', methods=['POST'])
@login_required
def update_profile():
    """
    Update user profile information.
    """
    try:
        # Get form data
        name = request.form.get('full_name')
        email = request.form.get('email')
        username = request.form.get('username')

        # Validate input
        if not name or not email or not username:
            return jsonify({'error': 'All fields are required'}), 400

        # Check if email or username already exists
        existing_email = User.query.filter(
            User.email == email, 
            User.id != current_user.id
        ).first()
        
        existing_username = User.query.filter(
            User.username == username, 
            User.id != current_user.id
        ).first()

        if existing_email:
            return jsonify({'error': 'Email already in use'}), 400
        
        if existing_username:
            return jsonify({'error': 'Username already taken'}), 400

        # Update user details
        current_user.name = name
        current_user.email = email
        current_user.username = username

        # Commit changes
        db.session.commit()

        return jsonify({
            'message': 'Profile updated successfully',
            'user': {
                'name': current_user.name,
                'email': current_user.email,
                'username': current_user.username
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Profile update error for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Could not update profile'}), 500

@app.route('/account/change-password', methods=['POST'])
@login_required
def change_password():
    """
    Change user account password.
    """
    try:
        # Get form data
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Validate input
        if not current_password or not new_password or not confirm_password:
            return jsonify({'success': False, 'message': 'All password fields are required'}), 400
        
        # Check if new passwords match
        if new_password != confirm_password:
            return jsonify({'success': False, 'message': 'New passwords do not match'}), 400

        # Verify current password
        if not current_user.check_password(current_password):
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400

        # Set new password
        current_user.set_password(new_password)
        db.session.commit()

        return jsonify({
            'message': 'Password changed successfully',
        }), 200

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Password change error for user {current_user.id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Could not change password'}), 500

@app.route('/account/update-preferences', methods=['POST'])
@login_required
def update_preferences():
    """
    Update user account preferences.
    """
    try:
        # Get form data
        theme = request.form.get('theme', 'light')
        email_notifications = 'email_notifications' in request.form
        marketing_emails = 'marketing_emails' in request.form

        # Update preferences
        current_user.theme = theme
        current_user.email_notifications = email_notifications
        current_user.marketing_emails = marketing_emails

        # Commit changes
        db.session.commit()

        return jsonify({
            'message': 'Preferences updated successfully',
            'preferences': {
                'theme': current_user.theme,
                'email_notifications': current_user.email_notifications,
                'marketing_emails': current_user.marketing_emails
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Preferences update error for user {current_user.id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Could not update preferences'}), 500

@app.route('/account/toggle-2fa', methods=['POST'])
@login_required
def toggle_two_factor():
    """
    Toggle two-factor authentication for the user.
    """
    try:
        # Toggle 2FA status
        current_user.two_factor_enabled = not current_user.two_factor_enabled
        db.session.commit()

        status = 'enabled' if current_user.two_factor_enabled else 'disabled'
        return jsonify({
            'message': f'Two-factor authentication {status}',
            'status': status
        }), 200

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"2FA toggle error for user {current_user.id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Could not toggle two-factor authentication'}), 500

@app.route('/account/delete', methods=['POST'])
@login_required
def delete_account():
    """
    Permanently delete user account.
    """
    try:
        # Get user ID before deletion
        user_id = current_user.id

        # Logout user
        logout_user()

        # Delete user account
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()

        return jsonify({
            'message': 'Your account has been permanently deleted',
        }), 200

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Account deletion error for user {user_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Could not delete account'}), 500

@app.route('/security-settings', methods=['GET'])
@login_required
def security_settings():
    """
    Render the security settings page for the current user.
    """
    try:
        # Fetch security-related user details with safe attribute retrieval
        security_details = {
            'two_factor_enabled': getattr(current_user, 'two_factor_enabled', False),
            'last_login': getattr(current_user, 'last_login', None),
            'login_attempts': getattr(current_user, 'login_attempts', 0),
            'active_sessions': get_active_user_sessions(current_user.id),
            'recent_activities': get_recent_user_activities(current_user.id)
        }

        return render_template('security_settings.html', user=security_details)
    except Exception as e:
        app.logger.error(f"Security settings page error for user {current_user.id}: {str(e)}")
        flash('An error occurred while loading security settings.', 'error')
        return redirect(url_for('dashboard'))

def get_active_user_sessions(user_id):
    """
    Retrieve active sessions for a user.
    """
    try:
        # This is a placeholder. Implement actual session tracking logic
        # You might want to use a session management library or custom tracking
        return [
            {
                'ip_address': '127.0.0.1',
                'device': 'Desktop Chrome',
                'last_activity': datetime.now() - timedelta(minutes=15),
                'is_current': True
            },
            {
                'ip_address': '192.168.1.100',
                'device': 'Mobile Safari',
                'last_activity': datetime.now() - timedelta(hours=2),
                'is_current': False
            }
        ]
    except Exception as e:
        app.logger.error(f"Error retrieving active sessions for user {user_id}: {str(e)}")
        return []

def get_recent_user_activities(user_id):
    """
    Retrieve recent user activities.
    """
    try:
        # This is a placeholder. Implement actual activity logging
        return [
            {
                'action': 'Login',
                'timestamp': datetime.now() - timedelta(hours=1),
                'ip_address': '127.0.0.1'
            },
            {
                'action': 'Password Changed',
                'timestamp': datetime.now() - timedelta(days=3),
                'ip_address': '192.168.1.100'
            },
            {
                'action': 'File Uploaded',
                'timestamp': datetime.now() - timedelta(hours=6),
                'ip_address': '127.0.0.1'
            }
        ]
    except Exception as e:
        app.logger.error(f"Error retrieving recent activities for user {user_id}: {str(e)}")
        return []

@app.route('/security-settings/revoke-session', methods=['POST'])
@login_required
def revoke_session():
    """
    Revoke a specific user session.
    """
    try:
        session_id = request.form.get('session_id')
        
        # Implement session revocation logic
        # This is a placeholder and should be replaced with actual session management
        return jsonify({
            'message': f'Session {session_id} revoked successfully'
        }), 200
    except Exception as e:
        app.logger.error(f"Session revocation error for user {current_user.id}: {str(e)}")
        return jsonify({'error': 'Could not revoke session'}), 500

@app.route('/cloud/files/debug', methods=['GET'])
@login_required
def debug_user_files():
    """
    Debug endpoint to retrieve detailed information about user's files.
    
    Returns:
        JSON with detailed file information for debugging.
    """
    try:
        # Retrieve all files for the current user
        user_files = UserCloudStorage.query.filter_by(user_id=current_user.id).all()
        
        # Prepare detailed file information
        file_details = []
        for file in user_files:
            # Check for active shares
            active_shares = SharedFile.query.filter_by(
                original_file_id=file.id, 
                status__in=['pending', 'accepted']
            ).count()
            
            file_details.append({
                'id': file.id,
                'name': file.file_name,
                'path': file.file_path,
                'size': file.file_size,
                'type': file.file_type,
                'active_shares': active_shares,
                'physical_file_exists': os.path.exists(file.file_path) if file.file_path else False
            })
        
        return jsonify({
            'total_files': len(file_details),
            'files': file_details
        }), 200
    
    except Exception as e:
        app.logger.error(f"Debug files error: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve file information',
            'details': str(e)
        }), 500

# Planner Routes
@app.route('/planner')
@login_required
def planner_home():
    # Get boards where user is owner or member
    owned_boards = PlannerBoard.query.filter_by(owner_id=current_user.id).all()
    member_boards = [bm.board for bm in current_user.board_memberships]
    
    return render_template('planner/home.html', 
                           owned_boards=owned_boards, 
                           member_boards=member_boards)

@app.route('/planner/board/create', methods=['GET', 'POST'])
@login_required
def create_board():
    form = BoardForm()
    if form.validate_on_submit():
        new_board = PlannerBoard(
            title=form.title.data,
            description=form.description.data,
            owner_id=current_user.id,
            is_public=form.is_public.data
        )
        db.session.add(new_board)
        
        # Add board creator as admin member
        board_member = BoardMember(
            board=new_board, 
            user=current_user, 
            role='admin'
        )
        db.session.add(board_member)
        
        db.session.commit()
        flash('Board created successfully!', 'success')
        return redirect(url_for('planner_board', board_id=new_board.id))
    
    return render_template('planner/create_board.html', form=form)

@app.route('/planner/board/<int:board_id>')
@login_required
def planner_board(board_id):
    board = PlannerBoard.query.get_or_404(board_id)
    
    # Check if user is a board member or owner
    is_member = BoardMember.query.filter_by(
        board_id=board_id, 
        user_id=current_user.id
    ).first()
    
    if not is_member and not board.is_public and board.owner_id != current_user.id:
        flash('You do not have access to this board.', 'danger')
        return redirect(url_for('planner_home'))
    
    list_form = ListForm()
    task_form = TaskForm()
    
    # Populate list of users for task assignment
    board_members = [bm.user for bm in board.board_members]
    task_form.assigned_to.choices = [(0, 'Unassigned')] + [(user.id, user.name) for user in board_members]
    task_form.list_id.choices = [(lst.id, lst.title) for lst in board.lists]
    
    return render_template('planner/board.html', 
                           board=board, 
                           list_form=list_form, 
                           task_form=task_form)

@app.route('/planner/board/<int:board_id>/list/create', methods=['POST'])
@login_required
def create_list(board_id):
    form = ListForm()
    board = PlannerBoard.query.get_or_404(board_id)
    
    # Check permissions
    is_member = BoardMember.query.filter_by(
        board_id=board_id, 
        user_id=current_user.id, 
        role__in=['editor', 'admin']
    ).first()
    
    if not is_member and board.owner_id != current_user.id:
        flash('You do not have permission to create lists.', 'danger')
        return redirect(url_for('planner_board', board_id=board_id))
    
    if form.validate_on_submit():
        new_list = PlannerList(
            title=form.title.data,
            board_id=board_id,
            order=len(board.lists)
        )
        db.session.add(new_list)
        db.session.commit()
        flash('List created successfully!', 'success')
    
    return redirect(url_for('planner_board', board_id=board_id))

@app.route('/planner/board/<int:board_id>/task/create', methods=['POST'])
@login_required
def create_task(board_id):
    form = TaskForm()
    board = PlannerBoard.query.get_or_404(board_id)
    
    # Check permissions
    is_member = BoardMember.query.filter_by(
        board_id=board_id, 
        user_id=current_user.id, 
        role__in=['editor', 'admin']
    ).first()
    
    if not is_member and board.owner_id != current_user.id:
        flash('You do not have permission to create tasks.', 'danger')
        return redirect(url_for('planner_board', board_id=board_id))
    
    form.list_id.choices = [(lst.id, lst.title) for lst in board.lists]
    board_members = [bm.user for bm in board.board_members]
    form.assigned_to.choices = [(0, 'Unassigned')] + [(user.id, user.name) for user in board_members]
    
    if form.validate_on_submit():
        assigned_to_id = form.assigned_to.data if form.assigned_to.data != 0 else None
        
        new_task = PlannerTask(
            title=form.title.data,
            description=form.description.data,
            list_id=form.list_id.data,
            creator_id=current_user.id,
            assigned_to_id=assigned_to_id,
            due_date=form.due_date.data,
            status=form.status.data
        )
        db.session.add(new_task)
        db.session.commit()
        flash('Task created successfully!', 'success')
    
    return redirect(url_for('planner_board', board_id=board_id))

@app.route('/planner/board/<int:board_id>/invite', methods=['GET', 'POST'])
@login_required
def invite_to_board(board_id):
    board = PlannerBoard.query.get_or_404(board_id)
    form = BoardInviteForm()
    
    # Check if current user is owner or admin
    is_admin = (board.owner_id == current_user.id or 
                BoardMember.query.filter_by(
                    board_id=board_id, 
                    user_id=current_user.id, 
                    role='admin'
                ).first() is not None)
    
    if not is_admin:
        flash('You do not have permission to invite members.', 'danger')
        return redirect(url_for('planner_board', board_id=board_id))
    
    # Get current board members for display
    board_members = BoardMember.query.filter_by(board_id=board_id).all()
    
    if form.validate_on_submit():
        email = form.email.data.strip()
        role = form.role.data
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Check if user is already a member
            existing_member = BoardMember.query.filter_by(
                board_id=board_id, 
                user_id=user.id
            ).first()
            
            if existing_member:
                flash(f'{user.name} is already a member of this board.', 'warning')
            else:
                # Add user as board member
                board_member = BoardMember(
                    board_id=board_id, 
                    user_id=user.id, 
                    role=role
                )
                db.session.add(board_member)
                
                try:
                    db.session.commit()
                    
                    # Send invitation notification (implement email sending logic)
                    send_board_invitation_email(user.email, board.title, current_user.name)
                    
                    flash(f'{user.name} has been invited to the board with {role} access.', 'success')
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"Error inviting user to board: {str(e)}")
                    flash('An error occurred while inviting the user.', 'danger')
        else:
            flash('No user found with that email address.', 'danger')
    
    return render_template('planner/invite.html', board=board, board_members=board_members, form=form)

def send_board_invitation_email(recipient_email, board_title, inviter_name):
    # Implement email sending logic
    pass

# Add these to your database initialization or migration script
if __name__ == '__main__':
    port = int(os.getenv('PORT', 80))
    from flask_migrate import Migrate
    migrate = Migrate(app, db)
    initialize_database()
    app.run(debug=True, host='0.0.0.0', port=port)

# Add logging configuration
import logging
from logging.handlers import RotatingFileHandler

# Configure logging
def configure_logging(app):
    # Ensure log directory exists
    log_dir = '/var/log/flask'
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure file handler
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'), 
        maxBytes=10240, 
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    # Set overall logging level
    app.logger.setLevel(logging.INFO)
    app.logger.info('Application startup')

# Call logging configuration
configure_logging(app)

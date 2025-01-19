import sys
import os

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Conditionally import to avoid Stripe initialization errors
try:
    import stripe
except ImportError:
    stripe = None

from server import app, db, User

def reset_database():
    """
    Completely reset the database - USE WITH CAUTION
    """
    with app.app_context():
        try:
            # Drop all tables
            db.drop_all()
            
            # Recreate all tables
            db.create_all()
            
            # Create default admin user
            default_admin = User(
                username='admin', 
                email='admin@sideforge.com', 
                name='Admin User',
                profile_picture=None  # Explicitly set profile_picture
            )
            default_admin.set_password('adminpassword')
            db.session.add(default_admin)
            
            # Optional: Add any other default data or initial setup
            
            db.session.commit()
            
            print("Database completely reset and initialized successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"Error resetting database: {str(e)}")
            raise

if __name__ == '__main__':
    reset_database()

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_caching import Cache
import os
import uuid

# Initialize extensions first (but don't configure them yet)
db = SQLAlchemy()
login_manager = LoginManager()
cache = Cache()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', str(uuid.uuid4()))
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///instance/users.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['CACHE_TYPE'] = 'simple'
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    cache.init_app(app)
    
    login_manager.login_view = 'login_page'
    
    with app.app_context():
        # Import routes after app is created to avoid circular imports
        from . import routes  # Create this file for your routes
        from . import models  # Create this file for your models
        
        # Create database tables
        db.create_all()
        
        # Add this after creating the login_manager
        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))
        
        return app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port) 
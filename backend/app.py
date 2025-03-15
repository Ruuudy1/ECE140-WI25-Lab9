import base64
from flask import Flask, request, jsonify, session, render_template, redirect, url_for, flash
import logging
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
import uuid
import requests
import atexit
import random

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = str(uuid.uuid4())

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'ssl': {
        'ssl_mode': 'REQUIRED'
    }
}

# Make sure the instance folder exists
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

# Cache configuration
app.config['CACHE_TYPE'] = 'simple'
cache = Cache(app)

# Register cleanup function
@atexit.register
def cleanup():
    try:
        db.session.remove()
        db.engine.dispose()
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# Models
class ESP32Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(100))
    location = db.Column(db.String(100))
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    location = db.Column(db.String(100))
    api_key = db.Column(db.String(32), unique=True)
    devices = db.relationship('ESP32Device', backref='owner', lazy=True)

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if not self.api_key:
            self.api_key = os.urandom(16).hex()

class ClothingItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(50))
    seasons = db.Column(db.String(200))  # Store seasons as comma-separated string
    image_url = db.Column(db.String(500))
    notes = db.Column(db.Text)
    is_favorite = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TemperatureReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Float)
    unit = db.Column(db.String(10))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    device_id = db.Column(db.Integer, db.ForeignKey('esp32_device.id'), nullable=False)

# Your other models here...

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables
def init_db():
    with app.app_context():
        try:
            # Try to create tables first
            db.create_all()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            try:
                # If there's an error, try to cleanup and recreate
                db.session.remove()
                db.engine.dispose()
                
                if os.path.exists(db_path):
                    try:
                        os.remove(db_path)
                        logger.info("Removed existing database file")
                    except OSError as ose:
                        logger.error(f"Could not remove database file: {ose}")
                        return
                
                # Try creating tables again
                db.create_all()
                logger.info("Database recreated successfully")
            except Exception as inner_e:
                logger.error(f"Failed to recreate database: {inner_e}")
                raise

# Frontend routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))
    return render_template('index.html')

@app.route('/login')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))
    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/wardrobe')
@login_required
def wardrobe():
    return render_template('wardrobe.html')

@app.route('/profile')
def profile():
    try:
        if not current_user.is_authenticated:
            return redirect(url_for('login_page'))
            
        return render_template(
            'profile.html',
            email=current_user.email,
            name=current_user.name,
            location=current_user.location,
            pid=current_user.api_key
        )
    except Exception as e:
        app.logger.error(f"Error in profile route: {str(e)}")
        return redirect(url_for('login_page'))


# API routes
@app.route('/api/signup', methods=['POST'])
def api_signup():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'password', 'location']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'message': f'{field} is required'}), 400
        
        # Check if user already exists
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'message': 'Email address already exists'}), 409
        
        # Create new user
        hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
        new_user = User(
            name=data['name'],
            email=data['email'],
            password=hashed_password,
            location=data['location']
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            
            # Log in the new user
            login_user(new_user)
            
            return jsonify({
                'message': 'User created successfully',
                'user': {
                    'id': new_user.id,
                    'name': new_user.name,
                    'email': new_user.email,
                    'location': new_user.location
                }
            }), 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error during signup: {e}")
            return jsonify({'message': 'Error creating user account'}), 500
            
    except Exception as e:
        logger.error(f"Error in signup route: {e}")
        return jsonify({'message': 'An unexpected error occurred'}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Invalid email or password'}), 401
    
    login_user(user, remember=data.get('remember', False))
    
    devices = ESP32Device.query.filter_by(user_id=user.id).all()
    connected_devices = [d for d in devices if d.is_online]
    
    return jsonify({
        'message': 'Logged in successfully',
        'user': {   
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'location': user.location
        },
        'devices': {
            'total': len(devices),
            'connected': len(connected_devices)
        }
    }), 200

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200

# Wardrobe routes
@app.route('/api/wardrobe', methods=['GET'])
@login_required
@cache.memoize(timeout=60)
def get_wardrobe_items():
    items = ClothingItem.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': item.id,
        'name': item.name,
        'category': item.category,
        'color': item.color,
        'seasons': item.seasons.split(',') if item.seasons else [],
        'image_url': item.image_url,
        'notes': item.notes
    } for item in items])

@app.route('/api/wardrobe', methods=['POST'])
@login_required
def add_clothing_item():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No data provided'}), 400

        required_fields = ['name', 'category']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'message': f'{field} is required'}), 400

        # Convert seasons array to comma-separated string
        seasons = ','.join(data.get('seasons', [])) if isinstance(data.get('seasons'), list) else data.get('season', '')

        new_item = ClothingItem(
            name=data['name'],
            category=data['category'],
            color=data.get('color', '#000000'),
            seasons=seasons,
            image_url=data.get('image_url', 'https://via.placeholder.com/150'),
            notes=data.get('notes', ''),
            user_id=current_user.id
        )
        
        try:
            db.session.add(new_item)
            db.session.commit()
            cache.delete_memoized(get_wardrobe_items)  # Invalidate cache
            
            return jsonify({
                'id': new_item.id,
                'name': new_item.name,
                'category': new_item.category,
                'color': new_item.color,
                'seasons': seasons.split(',') if seasons else [],
                'image_url': new_item.image_url,
                'notes': new_item.notes
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': f'Database error: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'message': f'Error processing request: {str(e)}'}), 400

@app.route('/api/wardrobe/items/<int:item_id>', methods=['DELETE'])
@login_required
def delete_clothing_item(item_id):
    try:
        item = ClothingItem.query.filter_by(id=item_id, user_id=current_user.id).first()
        
        if not item:
            return jsonify({'message': 'Item not found'}), 404
            
        db.session.delete(item)
        db.session.commit()
        
        # Clear the cache for get_wardrobe_items
        cache.delete_memoized(get_wardrobe_items)
        
        return '', 204
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error deleting item: {str(e)}'}), 500

@app.route('/api/wardrobe/items/<int:item_id>', methods=['PUT'])
@login_required
def update_clothing_item(item_id):
    try:
        item = ClothingItem.query.filter_by(id=item_id, user_id=current_user.id).first()
        
        if not item:
            return jsonify({'message': 'Item not found'}), 404
            
        data = request.get_json()
        item.name = data.get('name', item.name)
        item.category = data.get('category', item.category)
        item.color = data.get('color', item.color)
        item.seasons = data.get('seasons', item.seasons)
        item.image_url = data.get('image_url', item.image_url)
        item.notes = data.get('notes', item.notes)
        
        db.session.commit()
        
        return jsonify({
            'id': item.id,
            'name': item.name,
            'category': item.category,
            'color': item.color,
            'seasons': item.seasons.split(',') if item.seasons else [],
            'image_url': item.image_url,
            'notes': item.notes
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error updating item: {str(e)}'}), 500

@app.route('/api/wardrobe/suggestions', methods=['GET'])
@login_required
def get_clothing_suggestions():
    try:
        # Hardcoded San Diego weather data
        weather_data = {
            'temperature': 72,  # Typical San Diego temperature
            'conditions': 'sunny',  # Usually sunny in San Diego
            'humidity': 70  # Average humidity
        }
        
        # Get user's wardrobe items
        items = ClothingItem.query.filter_by(user_id=current_user.id).all()
        
        if not items:
            return jsonify({
                'weather': weather_data,
                'suggestions': [],
                'message': 'Please add items to your wardrobe first'
            })

        # Convert items to dictionary format
        suggestions = []
        for item in items:
            # Basic weather appropriateness check
            if weather_data['temperature'] > 80 and item.category.lower() == 'outerwear':
                continue
            if weather_data['temperature'] < 60 and 'tank' in item.name.lower():
                continue
                
            suggestions.append({
                'id': item.id,
                'name': item.name,
                'category': item.category,
                'color': item.color,
                'seasons': item.seasons.split(',') if item.seasons else [],
                'image_url': item.image_url
            })
        
        # Select a balanced outfit (one item from each main category)
        outfit = []
        categories = ['tops', 'bottoms', 'shoes', 'outerwear']
        
        for category in categories:
            matching_items = [item for item in suggestions if item['category'].lower() == category]
            if matching_items:
                # For outerwear, only include if it's cool enough
                if category == 'outerwear' and weather_data['temperature'] >= 75:
                    continue
                outfit.append(matching_items[0])  # Add first matching item

        return jsonify({
            'weather': weather_data,
            'suggestions': outfit
        })

    except Exception as e:
        return jsonify({
            'weather': weather_data,
            'suggestions': [],
            'error': str(e)
        }), 500

# Device routes
@app.route('/api/devices', methods=['GET'])
@login_required
def get_devices():
    devices = ESP32Device.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': device.id,
        'device_id': device.device_id,
        'name': device.name,
        'location': device.location,
        'is_online': device.is_online,
        'last_seen': device.last_seen
    } for device in devices])



##################### AI API #######################
####################################################################################
@app.route('/api/devices', methods=['POST'])
@login_required
def register_device():
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('device_id') or not data.get('name'):
            return jsonify({'message': 'Device ID and name are required'}), 400
            
        # Check if device already exists
        existing_device = ESP32Device.query.filter_by(device_id=data['device_id']).first()
        if existing_device:
            # If device exists but belongs to this user, update it
            if existing_device.user_id == current_user.id:
                existing_device.name = data['name']
                existing_device.location = data.get('location', '')
                db.session.commit()
                return jsonify({
                    'id': existing_device.id,
                    'device_id': existing_device.device_id,
                    'name': existing_device.name,
                    'location': existing_device.location,
                    'is_online': existing_device.is_online,
                    'last_seen': existing_device.last_seen
                }), 200
            return jsonify({'message': 'Device already registered to another user'}), 409
        
        # Create new device
        new_device = ESP32Device(
            device_id=data['device_id'],
            name=data['name'],
            location=data.get('location', ''),
            user_id=current_user.id,
            is_online=False
        )
        
        db.session.add(new_device)
        db.session.commit()
        
        return jsonify({
            'id': new_device.id,
            'device_id': new_device.device_id,
            'name': new_device.name,
            'location': new_device.location,
            'is_online': new_device.is_online,
            'last_seen': new_device.last_seen
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error registering device: {e}")
        return jsonify({'message': 'Error registering device'}), 500

@app.route('/api/devices/<int:device_id>', methods=['DELETE'])
@login_required
def delete_device(device_id):
    device = ESP32Device.query.filter_by(id=device_id, user_id=current_user.id).first_or_404()
    db.session.delete(device)
    db.session.commit()
    return '', 204

@app.route('/api/devices/ping/<device_id>', methods=['POST'])
def device_ping(device_id):
    try:
        device = ESP32Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({'message': 'Device not found'}), 404
        
        device.is_online = True
        device.last_seen = datetime.utcnow()
        db.session.commit()
        
        # Return current temperature if available
        latest_temp = TemperatureReading.query.filter_by(device_id=device.id).order_by(TemperatureReading.timestamp.desc()).first()
        
        return jsonify({
            'message': 'Ping received',
            'device': {
                'id': device.id,
                'name': device.name,
                'location': device.location,
                'is_online': device.is_online,
                'last_seen': device.last_seen.isoformat(),
                'current_temp': latest_temp.value if latest_temp else None
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing device ping: {e}")
        return jsonify({'message': 'Error processing ping'}), 500

@app.route('/api/devices/<int:device_id>/status', methods=['PUT'])
@login_required
def update_device_status(device_id):
    device = ESP32Device.query.filter_by(id=device_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    
    device.name = data.get('name', device.name)
    device.location = data.get('location', device.location)
    device.is_online = data.get('is_online', device.is_online)
    
    if data.get('is_online'):
        device.last_seen = datetime.utcnow()
        
    db.session.commit()
    
    return jsonify({
        'id': device.id,
        'device_id': device.device_id,
        'name': device.name,
        'location': device.location,
        'is_online': device.is_online,
        'last_seen': device.last_seen
    })

@app.route('/api/ai/text', methods=['POST'])
@login_required
def generate_text():
    data = request.get_json()
    prompt = data.get("prompt", "")
    
    if not prompt:
        return jsonify({"error": "No prompt provided."}), 400

    payload = {
        "prompt": prompt
    }
    
    api_url = "https://ece140-wi25-api.frosty-sky-f43d.workers.dev/api/v1/ai/complete"
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'email': 'ruosuna@ucsd.edu',
        'pid': 'A17434783'
    }
    
    try:
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get('success'):
            return jsonify({"text": data["result"]["response"]}), 200
        return jsonify({"error": "API request failed"}), 500
    except Exception as e:
        app.logger.error(str(e))
        return jsonify({"error": "Text generation failed."}), 500


@app.route('/api/ai/image', methods=['POST'])
@login_required
def generate_image():
    data = request.get_json()
    prompt = data.get("prompt", "")
    width = data.get("width", 512)
    height = data.get("height", 512)
    
    if not prompt:
        return jsonify({"success": False, "error": "No prompt provided."}), 400

    payload = {
        "prompt": prompt,
        "width": width,
        "height": height
    }
    
    api_url = "https://ece140-wi25-api.frosty-sky-f43d.workers.dev/api/v1/ai/image"
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'email': 'ruosuna@ucsd.edu',
        'pid': 'A17434783'
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        
        # Convert the image data to base64
        image_data = response.content
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        return jsonify({
            "success": True,
            "result": {
                "imageData": f"data:image/jpeg;base64,{image_base64}"
            }
        }), 200
            
    except requests.exceptions.RequestException as e:
        app.logger.error(str(e))
        if hasattr(e.response, 'status_code') and e.response.status_code == 429:
            return jsonify({
                "success": False,
                "error": "Rate limit exceeded"
            }), 429
        return jsonify({
            "success": False,
            "error": "Image generation failed."
        }), 500

@app.route('/api/check-auth')
def check_auth():
    if current_user.is_authenticated:
        return jsonify({'authenticated': True}), 200
    return jsonify({'authenticated': False}), 401

@app.route('/api/temperature', methods=['GET'])
@login_required
def get_temperature():
    try:
        # Get the latest temperature reading from your database
        latest_reading = TemperatureReading.query.order_by(TemperatureReading.timestamp.desc()).first()
        
        if latest_reading:
            return jsonify({
                'value': latest_reading.value,
                'unit': latest_reading.unit,
                'timestamp': latest_reading.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            return jsonify({'error': 'No temperature readings available'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/temperature', methods=['POST'])
def record_temperature():
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        temperature = data.get('temperature')
        unit = data.get('unit', 'C')  # Default to Celsius

        # Find the device
        device = ESP32Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({'error': 'Device not found'}), 404

        # Create new temperature reading
        reading = TemperatureReading(
            value=temperature,
            unit=unit,
            device_id=device.id
        )
        db.session.add(reading)
        db.session.commit()

        return jsonify({
            'message': 'Temperature recorded successfully',
            'reading_id': reading.id
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/temperature/history', methods=['GET'])
@login_required
def get_temperature_history():
    try:
        location = current_user.location or 'San Diego'
        response = requests.get(
            f"{WEATHER_API_BASE_URL}/forecast.json",
            params={
                'key': WEATHER_API_KEY,
                'q': location,
                'days': 1  # We only need current weather
            }
        )
        response.raise_for_status()
        weather_data = response.json()
        
        current_temp = weather_data['current']['temp_c']
        

        readings = []
        now = datetime.utcnow()
        
        for i in range(10):

            temp = current_temp + random.uniform(-0.5, 0.5)
            timestamp = (now - timedelta(minutes=i*5)).strftime('%Y-%m-%d %H:%M:%S')
            
            readings.append({
                'value': round(temp, 1),
                'timestamp': timestamp
            })
        
        return jsonify(readings)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(401)
def unauthorized(error):
    return jsonify({'message': 'Unauthorized access'}), 401

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found. Please check the URL."}), 404

WEATHER_API_KEY = "a649c0353f22415594923930251503"  
WEATHER_API_BASE_URL = 'https://api.weatherapi.com/v1'

@app.route('/api/weather/forecast', methods=['GET'])
@login_required
def get_weather_forecast():
    try:
        # Get user's location from their profile
        location = current_user.location or 'San Diego'  # Default to San Diego if no location set
        
        # Call weather API
        response = requests.get(
            f"{WEATHER_API_BASE_URL}/forecast.json",
            params={
                'key': WEATHER_API_KEY,
                'q': location,
                'days': 3  # Get 3-day forecast
            }
        )
        response.raise_for_status()
        weather_data = response.json()
        
        # Get user's wardrobe items
        items = ClothingItem.query.filter_by(user_id=current_user.id).all()
        
        # Simulate indoor temperature as outdoor + 2°C
        outdoor_temp = weather_data['current']['temp_c']
        indoor_temp = outdoor_temp + 2
        
        # Process weather data and generate recommendations
        current = weather_data['current']
        forecast = weather_data['forecast']['forecastday']
        
        return jsonify({
            'current_weather': {
                'temperature': current['temp_c'],
                'condition': current['condition']['text'],
                'humidity': current['humidity'],
                'indoor_temperature': indoor_temp  # Add simulated indoor temperature
            },
            'forecast': [{
                'date': day['date'],
                'max_temp': day['day']['maxtemp_c'],
                'min_temp': day['day']['mintemp_c'],
                'condition': day['day']['condition']['text']
            } for day in forecast],
            'recommendations': [{
                'id': item.id,
                'name': item.name,
                'category': item.category,
                'color': item.color,
                'seasons': item.seasons.split(',') if item.seasons else [],
                'image_url': item.image_url
            } for item in items[:5]]  # Limit to top 5 items
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Weather API error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/prewritten-queries', methods=['GET'])
@login_required
def get_prewritten_queries():
    # List of available pre-written queries
    queries = [
        {
            'id': 'what-to-wear',
            'text': 'What should I wear today?',
            'description': 'Get personalized clothing recommendations based on weather and your wardrobe'
        },
        {
            'id': 'temperature-analysis',
            'text': 'How is my indoor temperature?',
            'description': 'Analyze indoor temperature trends and comfort levels'
        },
        {
            'id': 'weather-forecast',
            'text': 'How\'s the weather looking?',
            'description': 'Get detailed weather forecast and recommendations'
        }
    ]
    return jsonify(queries)

@app.route('/api/ai/query/<query_id>', methods=['GET'])
@login_required
def handle_prewritten_query(query_id):
    try:
        if query_id == 'what-to-wear':
            # Get weather forecast and recommendations
            weather_response = get_weather_forecast()
            weather_data = weather_response.get_json()
            
            # Format the prompt for the AI
            current_weather = weather_data['current_weather']
            recommendations = weather_data['recommendations']
            
            prompt = f"""Given the current weather conditions:
            - Temperature: {current_weather['temperature']}°C
            - Conditions: {current_weather['condition']}
            - Indoor Temperature: {current_weather.get('indoor_temperature', 'N/A')}°C
            
            And these recommended clothing items:
            {', '.join(item['name'] for item in recommendations)}
            
            Please provide a friendly and detailed recommendation for what to wear today, including specific items from the list above."""
            
        elif query_id == 'temperature-analysis':
            # Get temperature history
            history_response = get_temperature_history()
            temp_data = history_response.get_json()
            
            if not temp_data:
                return jsonify({'text': 'No temperature data available'}), 404
                
            # Calculate some basic statistics
            temps = [reading['value'] for reading in temp_data]
            avg_temp = sum(temps) / len(temps)
            max_temp = max(temps)
            min_temp = min(temps)
            
            prompt = f"""Based on the temperature readings:
            - Average temperature: {avg_temp:.1f}°C
            - Maximum temperature: {max_temp:.1f}°C
            - Minimum temperature: {min_temp:.1f}°C
            
            Please analyze these temperatures and provide insights about indoor comfort levels and any recommendations for improvement."""
            
        elif query_id == 'weather-forecast':
            # Get weather forecast
            weather_response = get_weather_forecast()
            weather_data = weather_response.get_json()
            
            current = weather_data['current_weather']
            forecast = weather_data['forecast']
            
            prompt = f"""Current weather conditions:
            Temperature: {current['temperature']}°C
            Conditions: {current['condition']}
            
            3-day forecast:
            {', '.join(f"{day['date']}: {day['condition']} ({day['min_temp']}-{day['max_temp']}°C)" for day in forecast)}
            
            Please provide a detailed analysis of the weather conditions and what to expect in the coming days."""
            
        else:
            return jsonify({'text': 'Invalid query ID'}), 400
            
        # Call the AI API for text generation
        payload = {
            "prompt": prompt
        }
        
        api_url = "https://ece140-wi25-api.frosty-sky-f43d.workers.dev/api/v1/ai/complete"
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
            'email': 'ruosuna@ucsd.edu',
            'pid': 'A17434783'
        }
        
        try:
            ai_response = requests.post(api_url, json=payload, headers=headers)
            ai_response.raise_for_status()
            data = ai_response.json()
            if data.get('success'):
                return jsonify({"text": data["result"]["response"]}), 200
            return jsonify({"text": "Failed to generate AI response"}), 500
        except Exception as e:
            return jsonify({"text": f"Error generating response: {str(e)}"}), 500
            
    except Exception as e:
        return jsonify({"text": f"Error processing query: {str(e)}"}), 500

# Add a background task to mark devices as offline if not seen for a while
def mark_inactive_devices():
    with app.app_context():
        try:
            # Mark devices as offline if not seen in the last 2 minutes
            timeout = datetime.utcnow() - timedelta(minutes=2)
            devices = ESP32Device.query.filter(
                ESP32Device.is_online == True,
                ESP32Device.last_seen < timeout
            ).all()
            
            for device in devices:
                device.is_online = False
            
            db.session.commit()
        except Exception as e:
            logger.error(f"Error marking inactive devices: {e}")
            db.session.rollback()

# Run the cleanup task every minute
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    from threading import Thread
    import time
    
    def run_cleanup():
        while True:
            mark_inactive_devices()
            time.sleep(60)
    
    cleanup_thread = Thread(target=run_cleanup, daemon=True)
    cleanup_thread.start()

@app.route('/api/wardrobe/items/<int:item_id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(item_id):
    try:
        item = ClothingItem.query.filter_by(id=item_id, user_id=current_user.id).first()
        
        if not item:
            return jsonify({'message': 'Item not found'}), 404
            
        # Toggle the favorite status
        item.is_favorite = not item.is_favorite
        db.session.commit()
        
        # Clear the cache for get_wardrobe_items
        cache.delete_memoized(get_wardrobe_items)
        
        return jsonify({
            'id': item.id,
            'is_favorite': item.is_favorite
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error updating favorite status: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    init_db()
    app.run(host='0.0.0.0', port=port)


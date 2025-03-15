from flask import render_template, redirect, url_for, request, jsonify, session, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import base64
from datetime import datetime, timedelta
import random
import os
from . import app, db, cache
from .models import User, ESP32Device, ClothingItem, TemperatureReading

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
            app.logger.error(f"Database error during signup: {e}")
            return jsonify({'message': 'Error creating user account'}), 500
    except Exception as e:
        app.logger.error(f"Error in signup route: {e}")
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
        
        db.session.add(new_item)
        db.session.commit()
        cache.delete_memoized(get_wardrobe_items)
        
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

@app.route('/api/devices', methods=['POST'])
@login_required
def register_device():
    try:
        data = request.get_json()
        if not data.get('device_id') or not data.get('name'):
            return jsonify({'message': 'Device ID and name are required'}), 400
        
        existing_device = ESP32Device.query.filter_by(device_id=data['device_id']).first()
        if existing_device:
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
        app.logger.error(f"Error registering device: {e}")
        return jsonify({'message': 'Error registering device'}), 500

@app.route('/api/devices/<int:device_id>', methods=['DELETE'])
@login_required
def delete_device(device_id):
    device = ESP32Device.query.filter_by(id=device_id, user_id=current_user.id).first_or_404()
    db.session.delete(device)
    db.session.commit()
    return '', 204

# AI API routes
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

@app.route('/api/ai/prewritten-queries', methods=['GET'])
@login_required
def get_prewritten_queries():
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
            weather_response = get_weather_forecast()
            weather_data = weather_response.get_json()
            
            current_weather = weather_data['current_weather']
            
            prompt = f"""Given the current weather conditions:
            Temperature: {current_weather['temperature']}°C
            Conditions: {current_weather['condition']}
            Indoor Temperature: {current_weather.get('indoor_temperature', 'N/A')}°C
            
            Please provide a friendly and detailed recommendation for what to wear today."""
            
        elif query_id == 'temperature-analysis':
            weather_response = get_weather_forecast()
            weather_data = weather_response.get_json()
            
            current = weather_data['current_weather']
            
            prompt = f"""Based on the current conditions:
            - Outdoor temperature: {current['temperature']}°C
            - Indoor temperature: {current.get('indoor_temperature', 'N/A')}°C
            
            Please analyze these temperatures and provide insights about comfort levels."""
            
        elif query_id == 'weather-forecast':
            weather_response = get_weather_forecast()
            weather_data = weather_response.get_json()
            
            current = weather_data['current_weather']
            forecast = weather_data['forecast']
            
            prompt = f"""Current weather conditions:
            Temperature: {current['temperature']}°C
            Conditions: {current['condition']}
            
            3-day forecast:
            {', '.join(f"{day['date']}: {day['condition']} ({day['min_temp']}-{day['max_temp']}°C)" for day in forecast)}
            
            Please provide a detailed analysis of the weather conditions and what to expect."""
            
        else:
            return jsonify({'text': 'Invalid query ID'}), 400
            
        # Call the AI API
        return generate_text()
        
    except Exception as e:
        return jsonify({"text": f"Error processing query: {str(e)}"}), 500

@app.route('/api/check-auth')
def check_auth():
    if current_user.is_authenticated:
        return jsonify({'authenticated': True}), 200
    return jsonify({'authenticated': False}), 401

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/api/wardrobe/items/<int:item_id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(item_id):
    try:
        item = ClothingItem.query.filter_by(id=item_id, user_id=current_user.id).first()
        if not item:
            return jsonify({'message': 'Item not found'}), 404
        item.is_favorite = not item.is_favorite
        db.session.commit()
        cache.delete_memoized(get_wardrobe_items)
        return jsonify({
            'id': item.id,
            'is_favorite': item.is_favorite
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error updating favorite status: {str(e)}'}), 500

# Weather API configuration
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY', "a649c0353f22415594923930251503")
WEATHER_API_BASE_URL = 'https://api.weatherapi.com/v1'

@app.route('/api/weather/forecast', methods=['GET'])
@login_required
def get_weather_forecast():
    try:
        location = current_user.location or 'San Diego'
        
        response = requests.get(
            f"{WEATHER_API_BASE_URL}/forecast.json",
            params={
                'key': WEATHER_API_KEY,
                'q': location,
                'days': 3
            }
        )
        response.raise_for_status()
        weather_data = response.json()
        
        # Simulate indoor temperature as outdoor + 2°C
        current_temp = weather_data['current']['temp_c']
        indoor_temp = current_temp + 2
        
        current = weather_data['current']
        forecast = weather_data['forecast']['forecastday']
        
        return jsonify({
            'current_weather': {
                'temperature': current['temp_c'],
                'condition': current['condition']['text'],
                'humidity': current['humidity'],
                'indoor_temperature': indoor_temp
            },
            'forecast': [{
                'date': day['date'],
                'max_temp': day['day']['maxtemp_c'],
                'min_temp': day['day']['mintemp_c'],
                'condition': day['day']['condition']['text']
            } for day in forecast]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(401)
def unauthorized(error):
    return jsonify({'message': 'Unauthorized access'}), 401

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found. Please check the URL."}), 404 
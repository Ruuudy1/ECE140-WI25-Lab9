import unittest
import requests
import sqlite3
from app import app, db, User

class TestMVP(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
    
    def test_user_management(self):
        # Test signup
        signup_data = {
            'name': 'Test User',
            'email': 'test@test.com',
            'password': 'test123'
        }
        response = self.client.post('/api/signup', json=signup_data)
        self.assertEqual(response.status_code, 201)
        
        # Test login
        login_data = {
            'email': 'test@test.com',
            'password': 'test123'
        }
        response = self.client.post('/api/login', json=login_data)
        self.assertEqual(response.status_code, 200)
        
        # Test database storage
        with app.app_context():
            user = User.query.filter_by(email='test@test.com').first()
            self.assertIsNotNone(user)
        
        # Test logout
        response = self.client.post('/api/logout')
        self.assertEqual(response.status_code, 200)
    
    def test_wardrobe_management(self):
        # First login to get access
        login_data = {
            'email': 'test@test.com',
            'password': 'test123'
        }
        self.client.post('/api/login', json=login_data)
        
        # Test adding a clothing item
        item_data = {
            'name': 'Blue T-Shirt',
            'category': 'tops',
            'color': 'blue',
            'season': 'Summer',
            'image_url': 'https://example.com/shirt.jpg'
        }
        response = self.client.post('/api/wardrobe', json=item_data)
        self.assertEqual(response.status_code, 201)
        
        # Test getting wardrobe items
        response = self.client.get('/api/wardrobe')
        self.assertEqual(response.status_code, 200)
        items = response.get_json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['name'], 'Blue T-Shirt')
        
        # Test updating an item
        item_id = items[0]['id']
        update_data = {
            'name': 'Red T-Shirt',
            'color': 'red'
        }
        response = self.client.put(f'/api/wardrobe/{item_id}', json=update_data)
        self.assertEqual(response.status_code, 200)
        
        # Test deleting an item
        response = self.client.delete(f'/api/wardrobe/{item_id}')
        self.assertEqual(response.status_code, 204)
    
    def tearDown(self):
        with app.app_context():
            db.drop_all()

if __name__ == '__main__':
    unittest.main()
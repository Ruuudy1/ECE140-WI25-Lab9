import paho.mqtt.client as mqtt
import json
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# MQTT Settings
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "avocadobanana/ece140/sensors/readings"

# Database connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="admin",
        database="ece140a"
    )

# Ensure sensor_data table exists
def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id VARCHAR(50) NOT NULL,
            temperature FLOAT,
            pressure FLOAT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        # Parse the JSON message
        data = json.loads(msg.payload.decode())
        
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert the data
        cursor.execute("""
            INSERT INTO sensor_data (device_id, temperature, pressure)
            VALUES (%s, %s, %s)
        """, (data['device_id'], data['temperature'], data['pressure']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"Stored sensor data: {data}")
    except Exception as e:
        print(f"Error processing message: {e}")

def main():
    # Initialize database
    init_database()
    
    # Set up MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Connect to broker
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    
    # Start the loop
    print("MQTT Relay started. Waiting for messages...")
    client.loop_forever()

if __name__ == "__main__":
    main() 
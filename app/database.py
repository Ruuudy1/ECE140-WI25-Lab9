import mysql.connector
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

def seed_database():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD")
        )
        cursor = conn.cursor()
        
        # if no db, create one
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {os.getenv('MYSQL_DATABASE')}")
        cursor.execute(f"USE {os.getenv('MYSQL_DATABASE')}")
        
        # fill with sensor type
        tables = ['temperature', 'humidity', 'light']
        for table in tables:
            # table creation 
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    value FLOAT NOT NULL,
                    unit VARCHAR(10) NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # open CSV and insert data
            try:
                csv_path = f"./sample/{table}.csv"
                if os.path.exists(csv_path):
                    df = pd.read_csv(csv_path)
                    for _, row in df.iterrows():
                        cursor.execute(
                            f"INSERT INTO {table} (value, unit, timestamp) VALUES (%s, %s, %s)",
                            (float(row['value']), row['unit'], row['timestamp'])
                        )
                else:
                    # insert sample data 
                    sample_data = {
                        'temperature': [(25.5, '°C'), (26.1, '°C'), (24.8, '°C')],
                        'humidity': [(45.2, '%'), (46.5, '%'), (44.8, '%')],
                        'light': [(500, 'lux'), (550, 'lux'), (480, 'lux')]
                    }
                    for value, unit in sample_data[table]:
                        cursor.execute(
                            f"INSERT INTO {table} (value, unit) VALUES (%s, %s)",
                            (value, unit)
                        )
            except Exception as e:
                print(f"Error loading data for {table}: {e}")
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized successfully")
    except mysql.connector.Error as err:
        print(f"Error initializing database: {err}")

if __name__ == "__main__":
    seed_database()

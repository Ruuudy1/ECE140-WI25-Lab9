from fastapi import FastAPI, Query, HTTPException, Path, Body
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import mysql.connector
import os
from datetime import datetime

from app.database import seed_database

from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

from dotenv import load_dotenv
load_dotenv()

# Allowed sensor types
ALLOWED_SENSORS = {"temperature", "humidity", "light"}




# Initialize database and tables
def init_database():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="admin"
        )
        cursor = conn.cursor()
        
        # Create database if it doesn't exist
        cursor.execute("CREATE DATABASE IF NOT EXISTS ece140a")
        cursor.execute("USE ece140a")
        
        # Create sensor_data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_id VARCHAR(50) NOT NULL,
                temperature FLOAT,
                pressure FLOAT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create other sensor tables
        for sensor in ALLOWED_SENSORS:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {sensor} (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    value FLOAT NOT NULL,
                    unit VARCHAR(10) NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized successfully!")
    except mysql.connector.Error as err:
        print(f"Error initializing database: {err}")

# replacing on_event()
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()  # Initialize database when app starts
    seed_database()
    yield

app = FastAPI(lifespan=lifespan)

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="ece140a"
    )


static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def test_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="ece140a"
        )
        print("Database connection successful!")
        conn.close()
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")

if __name__ == "__main__":
    test_connection()

# Pydantic models for incoming data validation.
class SensorData(BaseModel):
    value: float
    unit: str
    timestamp: Optional[str] = None

class SensorDataUpdate(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    timestamp: Optional[str] = None




#################################################
##############Challenge 2!!!#####################
#################################################

# GET "/" - Main homepage

@app.get("/", response_class=HTMLResponse)
def read_index():
    try:
        file_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
        with open(file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading index.html: {str(e)}")
    
# GET "/dashboard" - Dashboard page
@app.get("/dashboard", response_class=HTMLResponse)
def read_dashboard():
    try:
        file_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
        with open(file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading dashboard.html: {str(e)}")




#################################################
##############Challenge 1!!!#####################
#################################################

# ############## must put the count endpoint above the detail route ###########
@app.get("/api/{sensor_type}/count")
def get_sensor_count(sensor_type: str):
    if sensor_type not in ALLOWED_SENSORS:
        raise HTTPException(status_code=404, detail="Invalid sensor type")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = f"SELECT COUNT(*) FROM {sensor_type}"
        cursor.execute(query)
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))

# GET all sensor records with optional query parameters.
@app.get("/api/{sensor_type}")
def read_sensor_data(
    sensor_type: str,
    order_by: Optional[str] = Query(None, alias="order-by"),
    start_date: Optional[str] = Query(None, alias="start-date"),
    end_date: Optional[str] = Query(None, alias="end-date")
):
    if sensor_type not in ALLOWED_SENSORS:
        raise HTTPException(status_code=404, detail="Invalid sensor type")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT * FROM {sensor_type} WHERE 1=1"
        params = []

        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        if order_by:
            if order_by not in ["value", "timestamp"]:
                raise HTTPException(status_code=400, detail="Invalid order-by field")
            query += f" ORDER BY {order_by}"

        cursor.execute(query, params)
        results = cursor.fetchall()

        for record in results:
            if record.get("timestamp") and isinstance(record["timestamp"], datetime):
                record["timestamp"] = record["timestamp"].strftime("%Y-%m-%d %H:%M:%S") #expected foormat on the instructions
        cursor.close()
        conn.close()
        return results
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))


# GET specific sensor record by id
@app.get("/api/{sensor_type}/{id}")
def get_sensor_data_by_id(sensor_type: str, id: int = Path(...)):
    if sensor_type not in ALLOWED_SENSORS:
        raise HTTPException(status_code=404, detail="Invalid sensor type")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT * FROM {sensor_type} WHERE id = %s"
        cursor.execute(query, (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if not result:
            raise HTTPException(status_code=404, detail="Data not found")
        return result
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))

# POST insert a new sensor record.
@app.post("/api/{sensor_type}")
def create_sensor_data(sensor_type: str, sensor: SensorData):
    if sensor_type not in ALLOWED_SENSORS:
        raise HTTPException(status_code=404, detail="Invalid sensor type")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # use database timestamp or IF NO TIMESTAMP: else reformat to match format
        data_timestamp = sensor.timestamp if sensor.timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        insert_query = f"INSERT INTO {sensor_type} (value, unit, timestamp) VALUES (%s, %s, %s)"
        cursor.execute(insert_query, (sensor.value, sensor.unit, data_timestamp))
        conn.commit()
        new_id = cursor.lastrowid

        # most recently inserted record so that the response is subscriptable
        cursor.execute(f"SELECT * FROM {sensor_type} WHERE id = %s", (new_id,))
        new_record = cursor.fetchone()

        # correct the instance formatting
        if new_record.get("timestamp") and isinstance(new_record["timestamp"], datetime):
            new_record["timestamp"] = new_record["timestamp"].strftime("%Y-%m-%d %H:%M:%S")

        cursor.close()
        conn.close()
        return new_record
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))

# PUT: update an existing sensor record
@app.put("/api/{sensor_type}/{id}")
def update_sensor_data(sensor_type: str, id: int = Path(...), sensor: SensorDataUpdate = Body(...)):
    if sensor_type not in ALLOWED_SENSORS:
        raise HTTPException(status_code=404, detail="Invalid sensor type")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        fields = []
        params = []
        if sensor.value is not None:
            fields.append("value = %s")
            params.append(sensor.value)
        if sensor.unit is not None:
            fields.append("unit = %s")
            params.append(sensor.unit)
        if sensor.timestamp is not None:
            fields.append("timestamp = %s")
            params.append(sensor.timestamp)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        query = f"UPDATE {sensor_type} SET " + ", ".join(fields) + " WHERE id = %s"
        params.append(id)
        cursor.execute(query, params)
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Data not found")
        cursor.close()
        conn.close()
        return "Update successful"
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))

# DELETE del. a sensor record
@app.delete("/api/{sensor_type}/{id}")
def delete_sensor_data(sensor_type: str, id: int = Path(...)):
    if sensor_type not in ALLOWED_SENSORS:
        raise HTTPException(status_code=404, detail="Invalid sensor type")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = f"DELETE FROM {sensor_type} WHERE id = %s"
        cursor.execute(query, (id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Data not found")
        cursor.close()
        conn.close()
        return "Deletion successful"
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))

# GET ESP32 sensor data
@app.get("/api/esp32-data")
def get_esp32_data(
    limit: Optional[int] = Query(100, description="Number of data points to return")
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT device_id, temperature, pressure, timestamp 
            FROM sensor_data 
            ORDER BY timestamp DESC 
            LIMIT %s
        """
        
        cursor.execute(query, (limit,))
        results = cursor.fetchall()
        
        # Format timestamps
        for record in results:
            if isinstance(record["timestamp"], datetime):
                record["timestamp"] = record["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.close()
        conn.close()
        
        # Reverse to show oldest to newest
        return list(reversed(results))
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))






if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

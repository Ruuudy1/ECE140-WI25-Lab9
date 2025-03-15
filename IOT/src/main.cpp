
// how to use platformIO: just resave the platformio.init file 
//

// ##########################################################################
// # TA GIRISH HELPED ME REWRITE THIS TO PASS GRADESCOPE TEST CASES
// ##########################################################################


// Replace with your MQTT broker address
const char* mqtt_server = "YOUR_MQTT_BROKER_IP";

// These variables should be set via your .env file and used in place of hardcoding.
#ifndef CLIENT_ID
  #define CLIENT_ID "esp32-sensors"
#endif

#ifndef TOPIC_PREFIX
  #define TOPIC_PREFIX "avocadobanana/ece140/sensors"
#endif


#include "ECE140_WIFI.h"
#include "ECE140_MQTT.h"
#include <Adafruit_BMP085.h>

ECE140_MQTT mqtt(String(CLIENT_ID), String(TOPIC_PREFIX));
ECE140_WIFI wifi;



// Replace these with your WiFi credentials (ALL UCSD WIFI ACCOUNT)
const char* username = UCSD_USERNAME;
const char* password = "132Ru7&39dY461"; // have to hardcode password since it has special characters '&'
const char* ssid = WIFI_SSID;
//const char* non_enterprise_pass = NON_ENTERPRISE_WIFI_PASSWORD; //NOT NEEDED ON SCHOOL WIFI



Adafruit_BMP085 bmp;

// unsigned long lastPublishTime = 0;

// float readTemperature() {
//     return (temprature_sens_read() - 32) / 1.8;
// }

void setup() {
    Serial.begin(115200);
    wifi.connectToWPAEnterprise(ssid, username, password);
    mqtt.connectToBroker();
    if(!bmp.begin()){
      Serial.println("check wiring");
    }

    // Serial.println("Starting ESP32 MQTT Sensor Node"); // IDK WHERE TO PUT
    // wifi.connect(wifiSsid, nonEnterpriseWifiPassword); // using school wifi 
    
    // mqtt.begin();
}

// GIRISH TA IS MY SAVIOUR 
// HE HELPED ME DEBUG 
// WHAT A GOAT
void loop() {
    Serial.println("temperature: " + String(bmp.readTemperature()) + " celsius");
    Serial.println("pressure: " + String(bmp.readPressure()) + " .pa");
    Serial.println("altitude: " + String(bmp.readAltitude()) + " meter(s)");
    Serial.println("sea_level pressure: " + String(bmp.readSealevelPressure()) + " pascal(s)");
    Serial.println("precise altitude: " + String(bmp.readAltitude(101500)) + " meters(s)");
    
    String payload = "{\"temperature\": " + String(bmp.readTemperature()) + ", \"pressure\": " + String(bmp.readPressure()) + "}";
    mqtt.publishMessage("readings", payload);
    delay(5000); 
}

// WiFiClient espClient;
// PubSubClient client(espClient);
// Adafruit_BMP085 bmp;

// void setup_wifi() {
//   delay(10);
//   Serial.println();
//   Serial.print("Connecting to ");
//   Serial.println(ssid);
  
//   WiFi.begin(ssid, password);
//   while (WiFi.status() != WL_CONNECTED) {
//     delay(500);
//     Serial.print(".");
//   }
  
//   Serial.println("");
//   Serial.println("WiFi connected");
// }

// void reconnect() {
//   // Loop until we reconnect to MQTT
//   while (!client.connected()) {
//     Serial.print("Attempting MQTT connection...");
//     if (client.connect(CLIENT_ID)) {
//       Serial.println("connected");
//     } else {
//       Serial.print("failed, rc=");
//       Serial.print(client.state());
//       Serial.println(" - trying again in 5 seconds");
//       delay(5000);
//     }
//   }
// }

// void setup() {
//   Serial.begin(115200);
//   setup_wifi();
  
//   client.setServer(mqtt_server, 1883);
  
//   if (!bmp.begin()) {
//     Serial.println("Could not find a valid BMP sensor, check wiring!");
//     while (1) {}
//   }
// }

// void loop() {
//   if (!client.connected()) {
//     reconnect();
//   }
//   client.loop();
  
//   // Read sensor data
//   float temperature = bmp.readTemperature();
//   float pressure = bmp.readPressure();
  
//   // Format the payload as JSON string
//   String payload = "{\"temperature\": " + String(temperature, 2) + ", \"pressure\": " + String(pressure, 2) + "}";
  
//   // Construct the full MQTT topic by appending the subtopic 'readings'
//   String topic = String(TOPIC_PREFIX) + "/readings";
  
//   Serial.print("Publishing message: ");
//   Serial.println(payload);
  
//   client.publish(topic.c_str(), payload.c_str());
  
//   // Wait 5 seconds between sensor readings
//   delay(5000);
// Include mqtt.js in your HTML (either via CDN or locally)
// Example with CDN:
// <script src="https://unpkg.com/mqtt/dist/mqtt.min.js"></script>

const mqttClient = mqtt.connect('ws://YOUR_MQTT_BROKER_URL');

mqttClient.on('connect', () => {
  console.log('Connected to MQTT broker');
  // Subscribe to topics; adjust the topic based on your ESP32 implementation
  mqttClient.subscribe('devices/+/temperature', (err) => {
    if (!err) console.log('Subscribed to temperature topics');
  });
});

mqttClient.on('message', (topic, message) => {
  // message is a Buffer, convert to string
  const payload = message.toString();
  // Update your UI with the new sensor data,
  // for example, update a real-time chart or the device status section.
  console.log(`Topic: ${topic}, Data: ${payload}`);
});
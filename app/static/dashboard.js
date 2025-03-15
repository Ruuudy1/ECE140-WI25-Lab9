// Fetch ESP32 sensor data
async function fetchESP32Data() {
    try {
        const response = await fetch('/api/esp32-data');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching ESP32 data:', error);
        return [];
    }
}

// Fetch other sensor data
async function fetchSensorData(sensorType) {
    try {
        const response = await fetch(`/api/${sensorType}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Error fetching ${sensorType} data:`, error);
        return [];
    }
}

// Create a chart
function createChart(canvasId, label, data, unit = '') {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    // Clear existing chart if it exists
    if (window.charts && window.charts[canvasId]) {
        window.charts[canvasId].destroy();
    }

    // Initialize charts object if it doesn't exist
    if (!window.charts) {
        window.charts = {};
    }

    // Create new chart
    window.charts[canvasId] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => moment(d.timestamp).format('HH:mm:ss')),
            datasets: [{
                label: `${label} ${unit}`,
                data: data.map(d => {
                    // Handle both formats (value property and direct property)
                    if (label.toLowerCase() === 'temperature') return d.temperature || d.value;
                    if (label.toLowerCase() === 'pressure') return d.pressure || d.value;
                    return d.value;
                }),
                borderColor: getColorForSensor(label),
                tension: 0.1,
                fill: false
            }]
        },
        options: {
            responsive: true,
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Time'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: label
                    }
                }
            },
            animation: {
                duration: 0 // Disable animation for better performance
            }
        }
    });
}

// Get color for different sensor types
function getColorForSensor(sensorType) {
    const colors = {
        'Temperature': 'rgb(255, 99, 132)',
        'Humidity': 'rgb(54, 162, 235)',
        'Light': 'rgb(255, 206, 86)',
        'Pressure': 'rgb(75, 192, 192)'
    };
    return colors[sensorType] || 'rgb(75, 192, 192)';
}

// Update ESP32 charts
async function updateESP32Charts() {
    const esp32Data = await fetchESP32Data();
    if (esp32Data.length > 0) {
        createChart('esp32TempChart', 'Temperature', esp32Data, '°C');
        createChart('esp32PressureChart', 'Pressure', esp32Data, 'Pa');
    }
}

// Initialize dashboard
async function initializeDashboard() {
    // Initial ESP32 data load
    await updateESP32Charts();

    // Load other sensor data
    const temperatureData = await fetchSensorData('temperature');
    const humidityData = await fetchSensorData('humidity');
    const lightData = await fetchSensorData('light');

    if (temperatureData.length > 0) {
        createChart('temperatureChart', 'Temperature', temperatureData);
    }
    if (humidityData.length > 0) {
        createChart('humidityChart', 'Humidity', humidityData);
    }
    if (lightData.length > 0) {
        createChart('lightChart', 'Light', lightData);
    }

    // Update ESP32 charts every 5 seconds
    setInterval(updateESP32Charts, 5000);
}

// Initialize the dashboard when the page loads
document.addEventListener('DOMContentLoaded', initializeDashboard);

document.addEventListener('DOMContentLoaded', function() {
    // Register device form handler
    const registerForm = document.getElementById('registerDeviceForm') || document.querySelector('form');
    
    registerForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      
      const deviceId = document.querySelector('input[name="Device ID"]').value;
      const deviceName = document.querySelector('input[name="Device Name"]').value;
      const location = document.querySelector('input[name="Location (optional)"]').value || '';
      
      try {
        const response = await fetch('/api/devices', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            device_id: deviceId,
            name: deviceName,
            location: location
          })
        });
        
        const data = await response.json();
        
        if (response.ok) {
          alert('Device registered successfully!');
          registerForm.reset();
          loadDevices();
        } else {
          alert(`Error: ${data.message}`);
        }
      } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while registering the device.');
      }
    });
    
    // Function to load and display existing devices
    async function loadDevices() {
      try {
        const response = await fetch('/api/devices');
        const devices = await response.json();
        
        const devicesList = document.getElementById('devicesList');
        if (devicesList) {
          devicesList.innerHTML = devices.map(device => `
            <div class="device-item">
              <p><strong>ID:</strong> ${device.device_id}</p>
              <p><strong>Name:</strong> ${device.name}</p>
              <p><strong>Location:</strong> ${device.location || 'Not specified'}</p>
              <p><strong>Status:</strong> ${device.is_online ? 'Online': 'Online'}</p>
              <button onclick="removeDevice(${device.id})">Remove</button>
            </div>
          `).join('');
        }
      } catch (error) {
        console.error('Error loading devices:', error);
      }
    }
    
    // Load devices when page loads
    loadDevices();
  });
  
  // Make removeDevice function available globally
  function removeDevice(deviceId) {
    if (confirm('Are you sure you want to remove this device?')) {
      fetch(`/api/devices/${deviceId}`, {
        method: 'DELETE'
      })
      .then(response => {
        if (response.ok) {
          alert('Device removed successfully!');
          location.reload();
        } else {
          return response.json().then(data => {
            throw new Error(data.message);
          });
        }
      })
      .catch(error => {
        console.error('Error:', error);
        alert(`Error: ${error.message}`);
      });
    }
  }
  
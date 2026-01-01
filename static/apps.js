// Initialize the Map (Centering on Philippines/Manila as default)
var map = L.map('map').setView([14.5995, 120.9842], 13);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

var marker;

// Handle Map Clicks
map.on('click', function(e) {
    var lat = e.latlng.lat;
    var lng = e.latlng.lng;

    // Update Input Boxes
    document.getElementById('lat').value = lat.toFixed(6);
    document.getElementById('lng').value = lng.toFixed(6);

    // Update Marker
    if (marker) {
        marker.setLatLng(e.latlng);
    } else {
        marker = L.marker(e.latlng).addTo(map);
    }
});

// Handle Form Submission
document.getElementById('incidentForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);

    // Show loading state
    const submitBtn = this.querySelector('button');
    submitBtn.innerText = "Sending...";
    submitBtn.disabled = true;

    fetch('/api/report', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        submitBtn.innerText = "Submit Report";
        submitBtn.disabled = false;

        if (data.status === 'success') {
            alert("Success: Incident has been recorded!");
            // Optional: Clear form or reload
            document.getElementById('incidentForm').reset();
            if(marker) map.removeLayer(marker);
        } else {
            alert("Error: " + data.message);
        }
    })
    .catch(error => {
        submitBtn.innerText = "Submit Report";
        submitBtn.disabled = false;
        console.error('Fetch Error:', error);
        alert("Server connection failed. Please try again.");
    });
});

// Initialize the Map
var map = L.map('map').setView([14.5995, 120.9842], 13);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

var marker;

// 1. Handle Map Clicks (To add new reports)
map.on('click', function(e) {
    var lat = e.latlng.lat;
    var lng = e.latlng.lng;

    // Update Input Boxes
    document.getElementById('lat').value = lat.toFixed(6);
    document.getElementById('lng').value = lng.toFixed(6);

    // Update the "Selection" Marker
    if (marker) {
        marker.setLatLng(e.latlng);
    } else {
        marker = L.marker(e.latlng).addTo(map);
    }
});

// 2. Handle Form Submission
document.getElementById('incidentForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);
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
            document.getElementById('incidentForm').reset();
            if(marker) map.removeLayer(marker);
            
            // Reload markers to show the new one immediately
            loadIncidents();
        } else {
            alert("Error: " + data.message);
        }
    })
    .catch(error => {
        submitBtn.innerText = "Submit Report";
        submitBtn.disabled = false;
        console.error('Fetch Error:', error);
        alert("Server connection failed.");
    });
});

// 3. Load Existing Incidents from Database (NEW!)
function loadIncidents() {
    fetch('/api/incidents')
    .then(response => response.json())
    .then(data => {
        console.log("Incidents loaded:", data);
        data.forEach(incident => {
            // Add a marker for each incident
            L.marker([incident.lat, incident.lng])
                .addTo(map)
                .bindPopup(`
                    <b>${incident.type}</b><br>
                    ${incident.description}<br>
                    <small>${incident.date}</small>
                `);
        });
    })
    .catch(error => console.error("Error loading incidents:", error));
}

// Call this function when the app starts
loadIncidents();

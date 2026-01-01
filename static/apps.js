// Map Initialization: Centered on San Jose del Monte, Bulacan
var map = L.map('map').setView([14.8091, 121.0459], 13);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
}).addTo(map);

var currentMarker;

// Click to place a new pin
map.on('click', (e) => {
    document.getElementById('lat').value = e.latlng.lat.toFixed(6);
    document.getElementById('lng').value = e.latlng.lng.toFixed(6);
    if (currentMarker) currentMarker.setLatLng(e.latlng);
    else currentMarker = L.marker(e.latlng).addTo(map);
});

// Load existing pins
function loadIncidents() {
    fetch('/api/incidents')
    .then(res => res.json())
    .then(data => {
        data.forEach(inc => {
            const markerColor = inc.status === 'Pending' ? 'red' : 'green';
            L.marker([inc.lat, inc.lng])
                .addTo(map)
                .bindPopup(`
                    <strong>${inc.type}</strong><br>
                    ${inc.description}<br>
                    <span class="badge bg-secondary">${inc.status}</span><br>
                    <small>${inc.date}</small>
                `);
        });
    });
}

// Submit logic
document.getElementById('incidentForm').onsubmit = function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    
    fetch('/api/report', { method: 'POST', body: formData })
    .then(res => res.json())
    .then(data => {
        if(data.status === 'success') {
            alert("Incident Report Submitted!");
            location.reload();
        }
    });
};

loadIncidents();

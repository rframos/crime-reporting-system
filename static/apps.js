var map = L.map('map').setView([14.5995, 120.9842], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

var marker;
var heatmapLayer;

// Function to load incidents and Heatmap
function loadIncidents() {
    fetch('/api/incidents')
    .then(res => res.json())
    .then(data => {
        // 1. Clear existing layers if needed
        
        // 2. Add Markers
        data.forEach(inc => {
            L.marker([inc.lat, inc.lng])
                .addTo(map)
                .bindPopup(`<b>${inc.type}</b><br>${inc.description}<br>Status: ${inc.status}`);
        });

        // 3. Phase 3: Heatmap Logic
        let heatPoints = data.map(inc => [inc.lat, inc.lng, 0.5]); // intensity 0.5
        if (heatmapLayer) map.removeLayer(heatmapLayer);
        // Note: Needs leaflet-heat.js library in HTML to work
        // heatmapLayer = L.heatLayer(heatPoints, {radius: 25}).addTo(map);
    });
}

map.on('click', function(e) {
    document.getElementById('lat').value = e.latlng.lat.toFixed(6);
    document.getElementById('lng').value = e.latlng.lng.toFixed(6);
    if (marker) marker.setLatLng(e.latlng);
    else marker = L.marker(e.latlng).addTo(map);
});

document.getElementById('incidentForm').onsubmit = function(e) {
    e.preventDefault();
    fetch('/api/report', { method: 'POST', body: new FormData(this) })
    .then(res => res.json())
    .then(data => {
        if(data.status === 'success') {
            alert("Reported!");
            loadIncidents();
        }
    });
};

loadIncidents();

var map = L.map('map').setView([14.8091, 121.0459], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

var marker;

map.on('click', function(e) {
    document.getElementById('lat').value = e.latlng.lat.toFixed(6);
    document.getElementById('lng').value = e.latlng.lng.toFixed(6);
    if (marker) marker.setLatLng(e.latlng);
    else marker = L.marker(e.latlng).addTo(map);
});

function loadIncidents() {
    fetch('/api/incidents')
    .then(res => res.json())
    .then(data => {
        data.forEach(inc => {
            L.marker([inc.lat, inc.lng]).addTo(map)
                .bindPopup(`<b>${inc.type}</b><br>${inc.description}<br><small>${inc.status}</small>`);
        });
    });
}

document.getElementById('incidentForm').onsubmit = function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    fetch('/api/report', { method: 'POST', body: formData })
    .then(res => res.json())
    .then(data => {
        if(data.status === 'success') {
            alert("Record Saved!");
            location.reload();
        } else {
            alert("Error: " + data.message);
        }
    });
};

loadIncidents();

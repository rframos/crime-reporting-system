const map = L.map('map').setView([14.5995, 120.9842], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

let marker;
map.on('click', function(e) {
    document.getElementById('lat').value = e.latlng.lat;
    document.getElementById('lng').value = e.latlng.lng;
    if (marker) marker.setLatLng(e.latlng);
    else marker = L.marker(e.latlng).addTo(map);
});

document.getElementById('incidentForm').onsubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const res = await fetch('/api/report', { method: 'POST', body: formData });
    const result = await res.json();
    alert(result.status === 'success' ? "Reported!" : "Error");
};

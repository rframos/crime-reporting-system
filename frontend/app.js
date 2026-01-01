// 1. INITIALIZE THE MAP
// Centered on a general coordinate (you can adjust this to your specific Barangay/City)
const map = L.map('map').setView([14.5995, 120.9842], 13); 

// Add OpenStreetMap tiles
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

// 2. HEATMAP CONFIGURATION
const cfg = {
    "radius": 40,
    "maxOpacity": .6,
    "scaleRadius": false,
    "useLocalExtrema": true,
    latField: 'lat',
    lngField: 'lng',
    valueField: 'count'
};

const heatmapLayer = new HeatmapOverlay(cfg);
map.addLayer(heatmapLayer);

// 3. CLICK TO SET LOCATION
let marker;
map.on('click', function(e) {
    const lat = e.latlng.lat.toFixed(6);
    const lng = e.latlng.lng.toFixed(6);

    // Update the hidden/readonly form fields
    document.getElementById('lat').value = lat;
    document.getElementById('lng').value = lng;

    // Move or create a marker to show the selected spot
    if (marker) {
        marker.setLatLng(e.latlng);
    } else {
        marker = L.marker(e.latlng).addTo(map);
    }
});

// 4. FETCH DATA FOR THE HEATMAP
function loadHeatmapData() {
    fetch('/api/incidents')
        .then(response => response.json())
        .then(data => {
            // Heatmap.js expects a "count" for intensity
            const heatmapData = {
                max: 8,
                data: data.map(i => ({
                    lat: i.lat,
                    lng: i.lng,
                    count: 1
                }))
            };
            heatmapLayer.setData(heatmapData);
        })
        .catch(err => console.error("Error loading heatmap:", err));
}

// Initial load
loadHeatmapData();

// 5. FORM SUBMISSION (With AI Feedback)
const incidentForm = document.getElementById('incidentForm');

incidentForm.addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(incidentForm);
    const submitBtn = document.getElementById('submitBtn');
    
    submitBtn.disabled = true;
    submitBtn.innerText = "Analyzing & Submitting...";

    fetch('/api/report', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === "success") {
            alert(`Report Successful! AI Classification: ${result.detected_type}`);
            incidentForm.reset();
            if (marker) map.removeLayer(marker);
            loadHeatmapData(); // Refresh the heatmap
        } else {
            alert("Error: " + result.message);
        }
    })
    .catch(err => {
        console.error("Submission error:", err);
        alert("An error occurred while submitting the report.");
    })
    .finally(() => {
        submitBtn.disabled = false;
        submitBtn.innerText = "Submit Report";
    });
});

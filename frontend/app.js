function showPage(page) {
  document.querySelectorAll('.container > div').forEach(div => div.classList.add('hidden'));
  document.getElementById(page).classList.remove('hidden');
}

function showDashboard() {
  let role = document.getElementById('role').value;
  document.querySelectorAll('[id^="dashboard"]').forEach(div => div.classList.add('hidden'));
  if (role) {
    let dashboard = document.getElementById('dashboard-' + role);
    dashboard.classList.remove('hidden');

    // Show heatmap only for Admin, Barangay, Police
    if (role === "admin" || role === "barangay" || role === "police") {
      initHeatmap();
    }
  }
}

function initHeatmap() {
  // Initialize map
  let map = L.map('map').setView([14.8136, 121.0453], 13); // Example: San Jose del Monte coords

  // Add OpenStreetMap tiles
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
  }).addTo(map);

  // Example incident data (lat, lng, intensity)
  let incidents = [
    [14.8136, 121.0453, 0.8], // Example point
    [14.8150, 121.0500, 0.6],
    [14.8200, 121.0400, 0.9]
  ];

  // Add heatmap layer
  L.heatLayer(incidents, { radius: 25 }).addTo(map);
}

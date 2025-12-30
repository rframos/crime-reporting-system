// Show selected page (Login, News, About, Contacts)
function showPage(page) {
  document.querySelectorAll('.container > div').forEach(div => div.classList.add('hidden'));
  document.getElementById(page).classList.remove('hidden');
}

// Show role-based dashboard after login
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

// Initialize heatmap visualization
function initHeatmap() {
  // Clear previous map instance if exists
  if (window.map) {
    window.map.remove();
  }

  // Initialize map (default center: San Jose del Monte)
  window.map = L.map('map').setView([14.8136, 121.0453], 13);

  // Add OpenStreetMap tiles
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
  }).addTo(window.map);

  // Fetch incident data from backend API
  fetch("https://your-backend.onrender.com/heatmap")  // Replace with your Render backend URL
    .then(response => response.json())
    .then(data => {
      // Example data format: [[lat, lng, intensity], ...]
      L.heatLayer(data, { radius: 25 }).addTo(window.map);
    })
    .catch(error => console.error("Error loading heatmap data:", error));
}

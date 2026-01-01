var map = L.map('map').setView([14.5995, 120.9842], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

var marker;

// --- Auth Toggle ---
const toggleBtn = document.getElementById('toggleAuth');
const roleSelect = document.getElementById('roleSelect');
const authTitle = document.getElementById('authTitle');
const authBtn = document.getElementById('authBtn');
let isLogin = true;

toggleBtn.onclick = (e) => {
    e.preventDefault();
    isLogin = !isLogin;
    authTitle.innerText = isLogin ? "Login" : "Register";
    authBtn.innerText = isLogin ? "Login" : "Register";
    toggleBtn.innerText = isLogin ? "Need an account? Register" : "Have an account? Login";
    roleSelect.classList.toggle('hidden', isLogin);
};

// --- Auth Submit ---
document.getElementById('authForm').onsubmit = function(e) {
    e.preventDefault();
    const url = isLogin ? '/api/login' : '/api/register';
    fetch(url, { method: 'POST', body: new FormData(this) })
    .then(res => res.json())
    .then(data => {
        if(data.status === 'success') {
            if(isLogin) window.location.reload();
            else { alert(data.message); toggleBtn.click(); }
        } else { alert(data.message); }
    });
};

// --- Map Click ---
map.on('click', (e) => {
    document.getElementById('lat').value = e.latlng.lat.toFixed(6);
    document.getElementById('lng').value = e.latlng.lng.toFixed(6);
    if (marker) marker.setLatLng(e.latlng);
    else marker = L.marker(e.latlng).addTo(map);
});

// --- Incident Logic ---
function loadIncidents() {
    fetch('/api/incidents')
    .then(res => res.json())
    .then(data => {
        data.forEach(inc => {
            L.marker([inc.lat, inc.lng])
                .addTo(map)
                .bindPopup(`<b>${inc.type}</b><br>${inc.description}<br>Status: ${inc.status}`);
        });
    });
}

document.getElementById('incidentForm').onsubmit = function(e) {
    e.preventDefault();
    fetch('/api/report', { method: 'POST', body: new FormData(this) })
    .then(res => res.json())
    .then(data => {
        if(data.status === 'success') {
            alert("Reported!");
            location.reload();
        } else { alert("Please login to submit a report."); }
    });
};

loadIncidents();

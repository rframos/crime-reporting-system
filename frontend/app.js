function showPage(page) {
  document.querySelectorAll('.container > div').forEach(div => div.classList.add('hidden'));
  document.getElementById(page).classList.remove('hidden');
}

function showDashboard() {
  let role = document.getElementById('role').value;
  document.querySelectorAll('[id^="dashboard"]').forEach(div => div.classList.add('hidden'));
  if (role) {
    document.getElementById('dashboard-' + role).classList.remove('hidden');
  }
}

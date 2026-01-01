document.getElementById('incidentForm').addEventListener('submit', function(e) {
    e.preventDefault();

    // Use FormData to grab all input values (lat, lng, type, description)
    const formData = new FormData(this);

    fetch('/api/report', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert("Reported Successfully!");
            window.location.reload(); // Refresh to show the new data (if applicable)
        } else {
            alert("Submission Error: " + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert("Server connection failed.");
    });
});

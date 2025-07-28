document.addEventListener('DOMContentLoaded', () => {
    const video = document.querySelector('img');
    const infoDiv = document.getElementById('info');

    // Function to capture a frame from the video feed and send it for analysis
    const analyzeFrame = () => {
        // Create a canvas to draw the video frame
        const canvas = document.createElement('canvas');
        canvas.width = video.width;
        canvas.height = video.height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Convert the canvas to a blob
        canvas.toBlob((blob) => {
            // Create a form data object to send the image
            const formData = new FormData();
            formData.append('image', blob, 'frame.jpg');

            // Send the image to the backend for analysis
            fetch('/analyze_vehicle', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    infoDiv.innerHTML = `<p>Error: ${data.error}</p>`;
                    return;
                }
                // Update the information div with the analysis results
                infoDiv.innerHTML = `
                    <p><strong>Number Plate:</strong> ${data.number_plate}</p>
                    <p><strong>Registration State:</strong> ${data.registration_state}</p>
                    <p><strong>Registration Year:</strong> ${data.registration_year}</p>
                    <p><strong>Vehicle Type:</strong> ${data.vehicle_type}</p>
                    <p><strong>Fuel Type:</strong> ${data.fuel_type}</p>
                    <p><strong>Vehicle Category:</strong> ${data.vehicle_category}</p>
                    <p><strong>Tariff:</strong> ₹${data.tariff}</p>
                `;
            })
            .catch(error => {
                console.error('Error analyzing vehicle:', error);
                infoDiv.innerHTML = '<p>Error analyzing vehicle.</p>';
            });
        }, 'image/jpeg');
    };

    // Analyze a frame every 5 seconds
    setInterval(analyzeFrame, 5000);
});

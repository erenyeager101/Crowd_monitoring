document.addEventListener('DOMContentLoaded', () => {
    const map = L.map('map').setView([18.5204, 73.8567], 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    const markers = {};
    let circles = {};
    let peakCrowd = 0;
    let totalCrowd = 0;
    let numberOfShops = 0;

    function createIcon(color) {
        return L.divIcon({
            className: 'custom-icon',
            html: `<div style="background-color: ${color}; width: 20px; height: 20px; border-radius: 50%;"></div>`,
            iconSize: [20, 20]
        });
    }

    function updateMap() {
        totalCrowd = 0;
        numberOfShops = 0;

        fetch('/data')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                const fetchedData = data.data;
                let maxCrowd = 0;
                let minCrowd = Infinity;
                let minCrowdLocation = '';

                fetchedData.forEach(item => {
                    const key = `${item.coordinates.latitude},${item.coordinates.longitude}`;

                    // Keep markers intact
                    const color = item.count > 3 ? 'red' : 'yellow';
                    if (!markers[key]) {
                        const marker = L.marker([item.coordinates.latitude, item.coordinates.longitude], { icon: createIcon(color) }).addTo(map)
                            .bindPopup(`Shop Count: ${item.count}`);
                        markers[key] = marker;
                    } else {
                        markers[key].setPopupContent(`Shop Count: ${item.count}`);
                        markers[key].setIcon(createIcon(color));
                    }

                    // Draw heatmap circles (Green, Yellow, Red layers)
                    if (circles[key]) {
                        circles[key].forEach(circle => map.removeLayer(circle));
                    }
                    circles[key] = [];

                    // Base circle (Green) is always shown
                    const greenCircle = L.circle([item.coordinates.latitude, item.coordinates.longitude], {
                        color: 'green',
                        fillColor: 'green',
                        fillOpacity: 0.3,
                        radius: 50 // Adjust base green circle size
                    }).addTo(map);
                    circles[key].push(greenCircle);

                    // Middle circle (Yellow) is shown if crowd >= 2
                    if (item.count >= 2) {
                        const yellowCircle = L.circle([item.coordinates.latitude, item.coordinates.longitude], {
                            color: 'yellow',
                            fillColor: 'yellow',
                            fillOpacity: 0.5,
                            radius: 30 // Middle yellow circle radius
                        }).addTo(map);
                        circles[key].push(yellowCircle);
                    }

                    // Inner circle (Red) is shown if crowd >= 5
                    if (item.count >= 5) {
                        const redCircle = L.circle([item.coordinates.latitude, item.coordinates.longitude], {
                            color: 'red',
                            fillColor: 'red',
                            fillOpacity: 0.6,
                            radius: 45 // Smallest red circle radius
                        }).addTo(map);
                        circles[key].push(redCircle);
                    }

                    // Update statistics
                    if (item.count > maxCrowd) {
                        maxCrowd = item.count;
                    }
                    if (item.count < minCrowd) {
                        minCrowd = item.count;
                        minCrowdLocation = `${item.coordinates.latitude},${item.coordinates.longitude}`;
                    }

                    totalCrowd += item.count;
                    numberOfShops++;
                });

                const averageCrowd = numberOfShops > 0 ? (totalCrowd / numberOfShops).toFixed(2) : 0;
                peakCrowd = maxCrowd;

                document.getElementById('peak-crowd').textContent = peakCrowd;
                document.getElementById('average-crowd').textContent = averageCrowd;
                document.getElementById('preferred-shop').textContent = minCrowdLocation ? `Shop Location: ${minCrowdLocation} with crowd: ${minCrowd}` : 'No data available';
            })
            .catch(error => {
                console.error('Error fetching data:', error);
            });
    }

    updateMap();
    setInterval(updateMap, 5000);
});

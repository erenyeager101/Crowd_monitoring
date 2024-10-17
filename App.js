document.addEventListener('DOMContentLoaded', () => {
    const map = L.map('map').setView([18.5204, 73.8567], 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    const markers = {};
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

    // Fetch and update the map with current data
    function updateMap() {
        fetch('/data')
            .then(response => response.json())
            .then(data => {
                let maxCrowd = 0;
                let minCrowd = Infinity;
                let minCrowdLocation = '';

                totalCrowd = 0;
                numberOfShops = 0;

                data.forEach(item => {
                    const key = `${item.coordinates.latitude},${item.coordinates.longitude}`;
                    const color = item.count > 10 ? 'red' : 'yellow';

                    if (!markers[key]) {
                        const marker = L.marker([item.coordinates.latitude, item.coordinates.longitude], { icon: createIcon(color) }).addTo(map)
                            .bindPopup(`Shop Count: ${item.count}`);
                        markers[key] = marker;
                    } else {
                        markers[key].setPopupContent(`Shop Count: ${item.count}`);
                        markers[key].setIcon(createIcon(color));
                    }

                    // Calculate statistics
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

                // Update statistics
                const averageCrowd = numberOfShops > 0 ? (totalCrowd / numberOfShops).toFixed(2) : 0;
                peakCrowd = maxCrowd;

                document.getElementById('peak-crowd').textContent = peakCrowd;
                document.getElementById('average-crowd').textContent = averageCrowd;
                document.getElementById('preferred-shop').textContent = minCrowdLocation ? 
                    `Shop Location: ${minCrowdLocation} with crowd: ${minCrowd}` : 'No data available';
            })
            .catch(error => {
                console.error('Error fetching data:', error);
            });
    }

    // Function to fetch and display historical data for a selected location
    function fetchHistoricalData(lat, lng, minutes) {
        fetch(`/history?lat=${lat}&lng=${lng}&minutes=${minutes}`)
            .then(response => response.json())
            .then(data => {
                const historyContainer = document.getElementById('history');
                historyContainer.innerHTML = '';

                data.forEach(item => {
                    const historyItem = document.createElement('div');
                    historyItem.textContent = `Time: ${item.timestamp}, Count: ${item.count}`;
                    historyContainer.appendChild(historyItem);
                });
            })
            .catch(error => {
                console.error('Error fetching historical data:', error);
            });
    }

    updateMap();
    setInterval(updateMap, 5000);

    // Event listener for viewing historical data
    document.getElementById('view-history').addEventListener('click', () => {
        const lat = document.getElementById('lat').value;
        const lng = document.getElementById('lng').value;
        const minutes = document.getElementById('time-range').value;

        if (lat && lng && minutes) {
            fetchHistoricalData(lat, lng, minutes);
        }
    });
    document.addEventListener('DOMContentLoaded', () => {
        const map = L.map('map').setView([18.5204, 73.8567], 13);
    
        // Adding OpenStreetMap tiles (background)
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);
    
        // Step 1: Initialize heatmap layer (but leave it empty for now)
        let heat = L.heatLayer([], { radius: 25 }).addTo(map);
    
        // Step 2: Fetch data from server and update heatmap
        function updateHeatmap() {
            fetch('/data')  // Assuming your crowd data is at /data
                .then(response => response.json())  // Convert the response to JSON
                .then(data => {
                    // Step 3: Prepare the heatmap data in the format [lat, lng, intensity]
                    const heatmapData = data.map(item => [
                        item.coordinates.latitude, 
                        item.coordinates.longitude, 
                        item.count // Use crowd count as intensity
                    ]);
    
                    // Step 4: Update the heatmap layer with new data
                    heat.setLatLngs(heatmapData);
                })
                .catch(error => {
                    console.error('Error fetching heatmap data:', error);
                });
        }
    
        // Step 5: Update the heatmap every 5 seconds to reflect changes in crowd data
        updateHeatmap();  // Run it once to load data initially
        setInterval(updateHeatmap, 5000);  // Run it every 5 seconds
    });
    
});

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

    function updateMap() {
        fetch('/data')
            .then(response => response.json())
            .then(data => {
                let maxCrowd = 0;
                let minCrowd = Infinity;
                let minCrowdLocation = '';
                let preferredShop = '';

                data.forEach(item => {
                    const key = `${item.lat},${item.lng}`;
                    const color = item.count > 10 ? 'red' : 'yellow';

                    if (!markers[key]) {
                        const marker = L.marker([item.lat, item.lng], { icon: createIcon(color) }).addTo(map)
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
                        minCrowdLocation = `${item.lat},${item.lng}`;
                    }

                    totalCrowd += item.count;
                    numberOfShops++;
                });

                // Update statistics
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

console.log("app is running")
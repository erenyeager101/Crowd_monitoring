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
    const shopNames = {
        '18.5204,73.8567': 'Zudio',
        '18.5250,73.8567': 'Pheonix Mall',
        '18.5369,73.8567': 'Kaka Halwai',
        '18.5650,73.8567': 'Shaniwar Peth',
        '18.5850,73.8567': 'Starbucks',
    };

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
                let maxShopName = '';
                let minShopName = '';
                
                fetchedData.forEach(item => {
                    const latitude = item.coordinates.latitude.toFixed(4);  
                    const longitude = item.coordinates.longitude.toFixed(4); 
                    const key = `${latitude},${longitude}`;

                    const shopName = shopNames[key] || 'Unknown Shop';  
                    const color = item.count > 3 ? 'red' : 'yellow';
                    if (!markers[key]) {
                        const marker = L.marker([item.coordinates.latitude, item.coordinates.longitude], { icon: createIcon(color) }).addTo(map)
                            .bindPopup(`Shop Name: ${shopName}<br>Shop Count: ${item.count}`);
                        markers[key] = marker;
                    } else {
                        markers[key].setPopupContent(`Shop Name: ${shopName}<br>Shop Count: ${item.count}`);
                        markers[key].setIcon(createIcon(color));
                    }

                    if (circles[key]) {
                        circles[key].forEach(circle => map.removeLayer(circle));
                    }
                    circles[key] = [];

                    const greenCircle = L.circle([item.coordinates.latitude, item.coordinates.longitude], {
                        color: 'green',
                        fillColor: 'green',
                        fillOpacity: 0.3,
                        radius: 50 
                    }).addTo(map);
                    circles[key].push(greenCircle);

                    if (item.count >= 2) {
                        const yellowCircle = L.circle([item.coordinates.latitude, item.coordinates.longitude], {
                            color: 'yellow',
                            fillColor: 'yellow',
                            fillOpacity: 0.5,
                            radius: 30 
                        }).addTo(map);
                        circles[key].push(yellowCircle);
                    }

                    if (item.count >= 5) {
                        const redCircle = L.circle([item.coordinates.latitude, item.coordinates.longitude], {
                            color: 'red',
                            fillColor: 'red',
                            fillOpacity: 0.6,
                            radius: 45 
                        }).addTo(map);
                        circles[key].push(redCircle);
                    }

                    if (item.count > maxCrowd) {
                        maxCrowd = item.count;
                        maxCrowdLocation = key;
                        maxShopName = shopNames[maxCrowdLocation] || 'Unknown Shop';
                    }
                    if (item.count < minCrowd) {
                        minCrowd = item.count;
                        minCrowdLocation = key;
                        minShopName = shopNames[minCrowdLocation] || 'Unknown Shop';
                    }

                    totalCrowd += item.count;
                    numberOfShops++;
                });

                const averageCrowd = numberOfShops > 0 ? (totalCrowd / numberOfShops).toFixed(2) : 0;
                peakCrowd = maxCrowd;

                document.getElementById('peak-crowd').textContent = peakCrowd;
                document.getElementById('average-crowd').textContent = averageCrowd;
                document.getElementById('preferred-shop').textContent = minCrowdLocation ? `Shop Name: ${minShopName} with crowd: ${minCrowd}` : 'No data available';
                document.getElementById('avoid-shop').textContent = maxCrowdLocation ? `Shop Name: ${maxShopName} with crowd: ${maxCrowd}` : 'No data available';
            })
            .catch(error => {
                console.error('Error fetching data:', error);
            });
    }

    document.getElementById('search-button').addEventListener('click', () => {
        const searchInput = document.getElementById('search-shop').value.trim().toLowerCase();
        let found = false;

        for (const [coordinates, name] of Object.entries(shopNames)) {
            if (name.toLowerCase() === searchInput) {
                const [latitude, longitude] = coordinates.split(',').map(Number);
                const count = markers[coordinates] ? markers[coordinates].getPopup().getContent().match(/Shop Count: (\d+)/)[1] : 'N/A';

                document.getElementById('search-result').textContent = `Shop Name: ${name}, Coordinates: ${latitude}, ${longitude}, Crowd Count: ${count}`;
                map.setView([latitude, longitude], 16); // Zoom in on the found shop
                found = true;
                break;
            }
        }

        if (!found) {
            document.getElementById('search-result').textContent = 'Shop not found.';
        }
    });

    updateMap();
    setInterval(updateMap, 5000);
});

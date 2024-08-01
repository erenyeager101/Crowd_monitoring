const express = require('express');
const path = require('path');
const app = express();
const port = 3000;

app.use(express.static('public'));
app.use(express.json());

let crowdData = [];

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/data', (req, res) => {
    res.json(crowdData);
});

app.post('/update_data', (req, res) => {
    const { coordinates, count } = req.body;
    const index = crowdData.findIndex(item => item.lat === coordinates.latitude && item.lng === coordinates.longitude);

    if (index !== -1) {
        crowdData[index].count = count;
    } else {
        crowdData.push({ lat: coordinates.latitude, lng: coordinates.longitude, count });
    }
    const maxCrowd = Math.max(...crowdData.map(item => item.count), 0);
    const averageCrowd = crowdData.reduce((acc, item) => acc + item.count, 0) / crowdData.length || 0;
    const preferredShop = crowdData.reduce((min, item) => (item.count < min.count ? item : min), { count: Infinity });
    res.json({ status: "success",
        maxCrowd,
        averageCrowd,
        preferredShop });
});


   
app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});

const express = require('express');
const path = require('path');
const { MongoClient } = require('mongodb'); 
const app = express();
const port = 3000;

const uri = "mongodb+srv://kunalsonne:kunalsonne1847724@cluster0.95mdg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0";

const client = new MongoClient(uri);
let collection;

async function connectToDatabase() {
    try {
        await client.connect();
        console.log('MongoDB connected successfully');
        const db = client.db('home');
        collection = db.collection('blogs');
    } catch (err) {
        console.error('Failed to connect to MongoDB:', err);
        process.exit(1); 
    }
}

app.use(express.static('public'));
app.use(express.json());

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/data', async (req, res) => {
    console.log('Received request to fetch data');
    try {
        console.log('Fetching data from MongoDB...');
        const data = await collection.find({}).sort({ timestamp: -1 }).limit(50).toArray();
        console.log('Data fetched successfully. Number of documents:', data.length);

        let maxCrowd = 0;
        let totalCrowd = 0;
        let preferredShop = { lat: '', lng: '', count: Infinity };
        
        data.forEach(item => {
            if (item.count > maxCrowd) {
                maxCrowd = item.count;
            }
            totalCrowd += item.count;
            if (item.count < preferredShop.count) {
                preferredShop = { lat: item.coordinates.latitude, lng: item.coordinates.longitude, count: item.count };
            }
        });
        
        const averageCrowd = totalCrowd / data.length || 0;

        res.json({
            data,
            maxCrowd,
            averageCrowd: averageCrowd.toFixed(2),
            preferredShop
        });
    } catch (err) {
        console.error('Error fetching data from MongoDB:', err);
        res.status(500).json({ error: 'Error fetching data from MongoDB' });
    }
});

app.get('/history', async (req, res) => {
    const { lat, lng, minutes } = req.query;
    const timeRange = new Date(Date.now() - minutes * 60 * 1000); 

    try {
        console.log(`Fetching historical data for lat: ${lat}, lng: ${lng}, minutes: ${minutes}`);
        const data = await collection.find({
            "coordinates.latitude": parseFloat(lat),
            "coordinates.longitude": parseFloat(lng),
            timestamp: { $gte: timeRange }
        }).sort({ timestamp: -1 }).toArray();
        console.log('Historical data fetched successfully. Number of documents:', data.length);
        res.json(data);
    } catch (err) {
        console.error('Error fetching historical data from MongoDB:', err);
        res.status(500).json({ error: 'Error fetching historical data from MongoDB' });
    }
});
 
app.post('/update_data', async (req, res) => {
    const { coordinates, count } = req.body;

    try {
        console.log('Inserting new data into MongoDB:', { coordinates, count });
        const result = await collection.insertOne({
            coordinates,
            count,
            timestamp: new Date()
        });
        console.log("Data inserted into MongoDB:", result);

        const data = await collection.find({}).sort({ timestamp: -1 }).limit(50).toArray();
        let maxCrowd = 0;
        let totalCrowd = 0;
        let preferredShop = { lat: '', lng: '', count: Infinity };

        data.forEach(item => {
            if (item.count > maxCrowd) {
                maxCrowd = item.count;
            }
            totalCrowd += item.count;
            if (item.count < preferredShop.count) {
                preferredShop = { lat: item.coordinates.latitude, lng: item.coordinates.longitude, count: item.count };
            }
        });

        const averageCrowd = totalCrowd / data.length || 0;

        res.json({
            status: "success",
            maxCrowd,
            averageCrowd: averageCrowd.toFixed(2),
            preferredShop
        });
    } catch (err) {
        console.error("Error updating MongoDB:", err);
        res.status(500).json({ error: "Error updating MongoDB" });
    }
});

connectToDatabase().then(() => {
    app.listen(port, () => {
        console.log(`Server is running on http://localhost:${port}`);
    });
});

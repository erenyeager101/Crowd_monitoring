const express = require('express');
const path = require('path');
const { MongoClient } = require('mongodb'); 
const app = express();
const port = 3000;
const mongoose = require('mongoose');

const cors = require('cors');


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
app.use(express.static('admin'));
app.use(express.json());
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'admin', 'admin.html'));
});
app.use(express.static('public'));
app.use(express.json());


app.get('/crowd', (req, res) => {
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
const HistorySchema = new mongoose.Schema({
    count: Number,
    coordinates: {
        latitude: Number,
        longitude: Number
    },
    timestamp: { type: Date }
});

const History = mongoose.model('History', HistorySchema);

app.get('/history', async (req, res) => {
    const { shop, time } = req.query;

    if (!shop || !time) {
        return res.status(400).json({ error: 'Shop and time parameters are required.' });
    }

    const currentTime = new Date();
    const pastTime = new Date(currentTime - time * 60 * 1000);  

    const shopCoordinates = {
        'Zudio': { latitude: 18.5204, longitude: 73.8567 },
        'Pheonix Mall': { latitude: 18.5250, longitude: 73.8567 },
        'Kaka Halwai': { latitude: 18.5369, longitude: 73.8567 },
        'Shaniwar Peth': { latitude: 18.5650, longitude: 73.8567 },
        'Starbucks': { latitude: 18.5850, longitude: 73.8567 }
        
    };

    const coordinates = shopCoordinates[shop];

    if (!coordinates) {
        return res.status(404).json({ error: 'Shop not found.' });
    }

    try {
        const history = await History.find({
            'coordinates.latitude': coordinates.latitude,
            'coordinates.longitude': coordinates.longitude,
            timestamp: { $gte: pastTime, $lte: currentTime }
        }).sort({ timestamp: -1 }); 

        if (history.length === 0) {
            return res.json({ message: 'No data available for the selected time range.' });
        }
        res.json(history);
    } catch (error) {
        console.error('Error fetching history:', error);
        res.status(500).json({ error: 'Server error' });
    }
});

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cors());

mongoose.connect('mongodb+srv://kunalsonne:kunalsonne1847724@cluster0.95mdg.mongodb.net/Auth', {
    useNewUrlParser: true,
    useUnifiedTopology: true
}).then(() => {
    console.log('Connected to MongoDB');
}).catch(err => {
    console.error('MongoDB connection failed:', err);
});

const userSchema = new mongoose.Schema({
    email: { type: String, required: true, unique: true },
    password: { type: String, required: true }
});

const User = mongoose.model('User', userSchema);

const shopSchema = new mongoose.Schema({
    shopName: String,
    coordinates: String,
    videoFeed: String
});
const Shop = mongoose.model('Shop', shopSchema);

app.use(express.static(path.join(__dirname, 'admin')));

// app.get('/', (req, res) => {
//     res.sendFile(path.join(__dirname, 'admin', 'admin.html'));
// });

app.get('/addShop', (req, res) => {
    res.sendFile(path.join(__dirname, 'admin', 'shopDetails.html'));
});

app.post('/signup', async (req, res) => {
    const { email, password } = req.body;

    try {
        const newUser = new User({ email, password });
        await newUser.save();
        res.redirect('/crowd'); 
    } catch (error) {
        console.error('Error registering user:', error);
        res.status(500).send('Error registering user');
    }
});

app.post('/signin', async (req, res) => {
    const { email, password } = req.body;

    try {
        const user = await User.findOne({ email });
        if (!user) return res.status(404).send('User not found');

        if (password === user.password) {
            res.redirect('/crowd'); 
        } else {
            res.status(401).send('Invalid password');
        }
    } catch (error) {
        console.error('Error logging in:', error);
        res.status(500).send('Error logging in');
    }
});

app.post('/addShop', async (req, res) => {
    try {
        const newShop = new Shop({
            shopName: req.body.shopName,
            coordinates: req.body.coordinates,
            videoFeed: req.body.videoFeed
        });
        await newShop.save();
        res.status(201).send('Shop details saved successfully!');
    } catch (error) {
        console.error('Error saving shop details:', error);
        res.status(500).send('Error saving shop details');
    }
});
app.get('/shops', async (req, res) => {
    try {
        const shops = await Shop.find(); 
        res.status(200).json(shops); 
    } catch (error) {
        console.error('Error fetching shop details:', error);
        res.status(500).send('Error fetching shop details');
    }
});
const crowdSchema = new mongoose.Schema({
    count: Number,
    coordinates: {
        latitude: Number,
        longitude: Number
    },
    timestamp: String
});

const Crowd = mongoose.model('Crowd', crowdSchema);

app.get('/api/top-shops', async (req, res) => {
    try {
        const topShops = await Crowd.aggregate([
            { $group: { _id: "$coordinates", totalCrowd: { $sum: "$count" } } },
            { $sort: { totalCrowd: -1 } },
            { $limit: 5 }
        ]);
        res.json(topShops);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.get('/api/historical-data', async (req, res) => {
    const { latitude, longitude } = req.query;
    try {
        const historicalData = await Crowd.find({
            "coordinates.latitude": latitude,
            "coordinates.longitude": longitude
        }).sort({ timestamp: 1 }).limit(50); 
        res.json(historicalData);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.get('/api/heatmap', async (req, res) => {
    try {
        const heatmapData = await Crowd.find({}).select('coordinates count');
        res.json(heatmapData);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});
connectToDatabase().then(() => {
    app.listen(port, () => {
        console.log(`Server is running on http://localhost:${port}`);
    });
});


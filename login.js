// Import dependencies
const express = require('express');
const mongoose = require('mongoose');
const bodyParser = require('body-parser');
const cors = require('cors');
const path = require('path');
const app = express();
const port = 3001;

// Middleware setup
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));
app.use(cors());

// MongoDB connection (replace with your own connection string)
mongoose.connect('mongodb+srv://kunalsonne:kunalsonne1847724@cluster0.95mdg.mongodb.net/Auth', {
    useNewUrlParser: true,
    useUnifiedTopology: true
}).then(() => {
    console.log('Connected to MongoDB');
}).catch(err => {
    console.error('MongoDB connection failed:', err);
});

// Define Mongoose schema for user
const userSchema = new mongoose.Schema({
    email: { type: String, required: true, unique: true },
    password: { type: String, required: true }
});

// Create Mongoose model for user
const User = mongoose.model('User', userSchema);

// Serve the HTML file for the front-end
app.use(express.static('admin'));

// Route to serve static signup/login page (admin.html)
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'admin', 'admin.html'));
});

app.get('/home', (req, res) => {
    res.sendFile(path.join(__dirname,'public','index.html'));
});

// Sign-up route: Store email and plain-text password in the database
app.post('/signup', async (req, res) => {
    const { email, password } = req.body;

    const newUser = new User({
        email,
        password // Saving password in plain-text (not recommended for real applications)
    });

    try {
        // Save the new user to the database
        await newUser.save();
        res.status(201).send('User registered successfully');
        res.redirect('/'); // Redirect to the login page after successful registration
    } catch (error) {
        res.status(500).send('Error registering user');
    }
});

// Sign-in route: Compare plain-text password to authenticate
app.post('/signin', async (req, res) => {
    const { email, password } = req.body;

    try {
        // Find the user by email in the database
        const user = await User.findOne({ email });
        if (!user) return res.status(404).send('User not found');

        // Directly compare input password with stored password
        if (password === user.password) {
            res.status(200).send('Authentication successful');
            res.redirect('/home');
        } else {
            res.status(401).send('Invalid password');
        }
    } catch (error) {
        res.status(500).send('Error logging in');
    }
});

// Start the server
app.listen(port, () => {
    console.log(`Server is running on http://localhost:${port}`);
});

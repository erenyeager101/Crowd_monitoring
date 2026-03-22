const express = require("express");
const cors = require("cors");
const dotenv = require("dotenv");

dotenv.config();

const app = express();
const PORT = process.env.PORT || 10000;

// Allow your deployed frontend + local dev
const allowedOrigins = [
  "https://crowd-monitoring-hack2skill.vercel.app",
  "http://localhost:3000",
  "http://localhost:5173"
];

app.use(
  cors({
    origin: function (origin, callback) {
      // Allow requests with no origin (Postman/mobile apps/curl)
      if (!origin) return callback(null, true);

      if (allowedOrigins.includes(origin)) {
        return callback(null, true);
      }

      return callback(new Error("CORS not allowed for this origin: " + origin), false);
    },
    credentials: true
  })
);

app.use(express.json());

// Health check (Render will use this)
app.get("/health", (req, res) => {
  res.status(200).json({
    ok: true,
    service: "crowd-monitoring-backend",
    timestamp: new Date().toISOString()
  });
});

// Base route
app.get("/", (req, res) => {
  res.json({
    message: "Crowd Monitoring backend is running 🚀",
    docs: "Use /health for health checks"
  });
});

/**
 * POST /api/predict
 * Stub endpoint — replace the body with your real model/service logic.
 * Frontend should call: POST <BACKEND_URL>/api/predict
 */
app.post("/api/predict", async (req, res) => {
  try {
    const payload = req.body || {};

    // TODO: Replace with your actual prediction/business logic
    res.status(200).json({
      success: true,
      received: payload,
      result: {
        crowdDensity: "medium",
        confidence: 0.87
      }
    });
  } catch (error) {
    console.error("Error in /api/predict:", error);
    res.status(500).json({
      success: false,
      message: "Internal server error"
    });
  }
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: "Route not found"
  });
});

app.listen(PORT, () => {
  console.log(`Backend running on port ${PORT}`);
});

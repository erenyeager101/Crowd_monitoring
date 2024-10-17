@echo off
echo Setting up project dependencies...

:: Install Node.js dependencies
echo Installing Node.js dependencies...
cd .
npm install express path socket.io

:: Install Python dependencies
echo Installing Python dependencies...
cd .
python -m pip install --upgrade pip
pip install opencv-python-headless imutils numpy requests

:: Install React dependencies
echo Installing React dependencies...
cd .
npx create-react-app my-app
cd my-app
npm install leaflet react-leaflet socket.io-client axios @react-google-maps/api

:: Set up MongoDB (Optional, if you're using MongoDB)
echo Setting up MongoDB...
REM You can download and install MongoDB from https://www.mongodb.com/try/download/community
REM You can also use a cloud-based MongoDB service like MongoDB Atlas

:: Docker installation (Optional, if you're using Docker)
echo Setting up Docker...
REM You can download and install Docker from https://www.docker.com/products/docker-desktop

:: NGINX installation (Optional, if you're using NGINX)
echo Setting up NGINX...
REM You can download and install NGINX from https://nginx.org/en/download.html

echo Dependencies setup complete!
pause

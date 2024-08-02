
# Crowd Monitoring and Management

Crowd monitoring and management using real-time data from IP camera and Laptop camera footage which aims to provide users with insights into the crowd density at various locations espicially at local market places , shops ,malls. This helps users make informed decisions about visiting places based on the level of crowdiness.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Data Collection](#data-collection)
- [UI and Visualization](#ui-and-visualization)
- [Server-Side Functionality](#server-side-functionality)
- [Contributing](#contributing)
- [License](#license)

<p align="center">
  <img src="https://github.com/yourusername/crowd-monitoring-and-management/blob/main/images/crowd_monitoring_ui.png" alt="Crowd Monitoring UI" width="600" />
</p>

## Overview

The goal of this project is to track and manage crowd density in real-time using CCTV footage. The system detects the number of people at a location, provides an option to input coordinates, and displays the crowd data on a map. It also shows peak and average crowd levels, using color coding to indicate crowd intensity.

## Features

- Real-time detection of crowd density using IP camera and laptop camera footage(Prototype)
- Input of coordinates for location-specific monitoring
- Display of crowd data on a map with color coding (red for high crowd, yellow for low crowd)
- Calculation and display of `max_crowd`, `average_crowd`, and `preffered_shop`
- UI enhancements for a user-friendly experience

## Installation

To set up the project, clone the repository and install the required dependencies.

```bash
git clone https://github.com/erenyeager101/Crowd_monitoring.git
cd Crowd_monitoring
```

Ensure you have all dependencies installed by running:

```bash
dependencies.bat
```

## Usage

To start the application, run the main script in the root directory:

```bash
start.bat
```

Access the web interface at `http://localhost:3000` and follow the on-screen instructions to view and interact with the crowd data.

## Data Collection

The system uses IP camera on android device or laptop camera footage to detect the number of people at a specific location. This data, along with coordinates and IP address, is sent to the server to update the map with the crowd information.

## UI and Visualization

The project includes a visually appealing and user-friendly interface. The map visualization helps users easily identify crowded areas and make decisions accordingly.

```python
import matplotlib.pyplot as plt
import seaborn as sns

# Example code to plot crowd data
plt.figure(figsize=(10, 6))
sns.barplot(x=locations, y=crowd_levels)
plt.xlabel("Locations")
plt.ylabel("Crowd Levels")
plt.show()
```

## Server-Side Functionality

The server processes the incoming data, updates the crowd information on the map, and calculates the `max_crowd`, `average_crowd`, and `preffered_shop` values. It also provides real-time updates to the UI.

## Contributing

Contributions are welcome! Please create a pull request or raise an issue to discuss your ideas. Ensure that your contributions follow the project's coding standards and guidelines.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Additional Setup Instructions

1. **Dependencies Installation**:
   - All requirements are added in the `dependencies.bat` file. To install all dependencies, simply run this `.bat` file in the terminal.
   - After running the `dependencies.bat` file, add your own IP address in the `detection.py` file. To find the IP address, install the "IP Camera" app from the Play Store. Once the server starts on the IP Camera app, the IP address will be displayed.

2. **Running the Project**:
   - To run the project, navigate to the project directory in the terminal and run the command:
     ```bash
     start.bat
     ```
   - Ensure that the IP Camera server is started on your mobile device before running the project.
   - Point the camera to a crowd to count the number of people.


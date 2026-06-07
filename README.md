# AI-Powered Traffic Management and Digital Twin System

## Overview

This project presents an AI-powered traffic management system built using SUMO (Simulation of Urban Mobility), Python, Machine Learning, and Unity.

The system simulates real-world traffic conditions using a road network generated from OpenStreetMap data and provides:

* Adaptive traffic signal control
* Traffic prediction using machine learning
* Emergency vehicle prioritization
* Congestion analysis
* Real-time Unity digital twin visualization
* Traffic data collection for future reinforcement learning research

The implementation uses the MP Nagar road network (Bhopal, India) as the primary simulation environment.

---

## Features

### Adaptive Traffic Signal Control

The system continuously monitors:

* Vehicle queue lengths
* Lane occupancy
* Vehicle arrival rates
* Congestion levels

Traffic signals are dynamically adjusted based on current traffic conditions rather than fixed signal timings.

---

### Machine Learning Traffic Prediction

A Random Forest Multi-Output Regression model predicts:

* Future vehicle count
* Future travel time

Input features include:

* Day of week
* Hour of day
* Distance
* Lane count
* Congestion score
* Signal phase
* Source junction
* Destination junction

The trained model is integrated into the traffic controller to anticipate congestion before it occurs.

---

### Emergency Vehicle Priority

Special emergency vehicles can be introduced into the simulation.

The controller:

* Detects emergency vehicles
* Predicts arrival times
* Extends or prepares green signals
* Reduces waiting time along emergency corridors

---

### Mixed Traffic Simulation

The system supports custom vehicle types including:

* Cars
* Buses
* Trucks
* Ambulances
* Custom Indian traffic elements such as Thelas (street carts)

Custom vehicle routes can be created using NETEDIT and visualized in Unity using dedicated 3D models.

---

### Real-Time Unity Digital Twin

The SUMO simulation is synchronized with Unity through a custom communication bridge.

Features include:

* Real-time vehicle synchronization
* 3D road network visualization
* Custom vehicle prefabs
* Interactive camera controls
* Terrain support
* Performance monitoring

The Unity digital twin mirrors the live SUMO simulation and provides a realistic visualization environment.

---

## System Architecture

OpenStreetMap Data

↓

JOSM / Network Editing

↓

SUMO Network Generation

↓

SUMO Traffic Simulation

↓

TraCI API

↓

Python Adaptive Controller

↓

Machine Learning Traffic Predictor

↓

Unity Bridge (ZeroMQ / NetMQ)

↓

Unity Digital Twin

↓

Real-Time Traffic Visualization

---

## Technologies Used

### Simulation

* SUMO
* SUMO-GUI
* TraCI

### Machine Learning

* Scikit-Learn
* Random Forest Regressor
* MultiOutputRegressor
* Joblib

### Visualization

* Unity 6
* NetMQ
* ZeroMQ

### Development

* Python
* C#
* XML
* OpenStreetMap
* JOSM
* NETEDIT

---

## Machine Learning Model

### Targets

The model predicts:

1. Future Vehicle Count
2. Future Travel Time

### Performance

Latest model results:

Vehicle Count MAE: 1.48

Travel Time MAE: 10.51

Vehicle Count R²: 0.949

Travel Time R²: 0.866

These results demonstrate strong predictive performance for traffic forecasting.

---

## Unity Integration

The Unity Digital Twin receives:

* Vehicle IDs
* Vehicle types
* Vehicle positions
* Vehicle speeds
* Vehicle orientations

Vehicle models are mapped dynamically based on SUMO vehicle types.

Examples:

* Car → Standard vehicle prefab
* Ambulance → Emergency vehicle prefab
* Thela → Indian street cart prefab

---

## Project Structure

```text
.
├── adaptive_signal_demo.py
├── normal_signal_demo.py
├── unity_bridge.py
├── traffic_predictor.pkl
├── source_encoder.pkl
├── destination_encoder.pkl
├── mp_nagar_2.net.xml
├── mp_nagar_2.sumocfg
├── UnityDigitalTwin/
├── route_files/
├── training_data/
└── README.md
```

## Future Enhancements

* Reinforcement Learning based signal optimization
* Dynamic route guidance
* Traffic heatmap visualization
* Pedestrian simulation
* Smart parking integration
* Multi-city deployment
* Real-time IoT sensor integration

---

## Results

The system successfully demonstrates:

* Reduced waiting times
* Adaptive signal behavior
* Congestion prediction
* Emergency vehicle prioritization
* Real-time synchronization between SUMO and Unity

The project provides a foundation for developing intelligent transportation systems and smart city traffic management solutions.

## Authors

Developed as an AI-Based Traffic Management and Digital Twin project using SUMO, Machine Learning, and Unity.

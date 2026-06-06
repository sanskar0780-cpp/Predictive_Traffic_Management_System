# Smart Traffic Management System using SUMO and Predictive AI

## Overview

This project presents an intelligent traffic management framework built on top of **SUMO (Simulation of Urban Mobility)** and the **TraCI API**. The system combines predictive traffic signal control, congestion analytics, emergency vehicle prioritization, machine learning-based traffic forecasting, and smart routing recommendations to improve traffic flow in an urban road network.

The project was developed using a real road network extracted from OpenStreetMap and converted for use within SUMO.

---

## Key Features

### Adaptive Traffic Signal Control

* Predicts approaching traffic using route lookahead analysis.
* Dynamically prepares or extends green phases before vehicles arrive.
* Reduces unnecessary waiting and signal switching.

### AI-Based Traffic Prediction

* Multi-Output Random Forest Regression model.
* Predicts:

  * Future vehicle arrivals at junctions.
  * Expected travel time between junctions.
* Enables proactive traffic management rather than reactive control.

### Congestion Scoring Engine

* Continuously evaluates traffic conditions using:

  * Vehicle count
  * Waiting time
  * Halted vehicles
  * Average speed
* Produces a normalized congestion score between 0 and 100.
* Classifies congestion as:

  * Low
  * Medium
  * High

### Emergency Vehicle Priority

* Detects:

  * Ambulances
  * Fire vehicles
  * Police vehicles
* Creates temporary green corridors along the vehicle's route.
* Prioritizes emergency movement through intersections.

### Smart Route Recommendation

* Evaluates route quality using live congestion information.
* Estimates potential route improvements.
* Generates alternative route recommendations without modifying active vehicle routes.

### Peak-Hour Traffic Profiles

Supports multiple operating modes:

* Normal Traffic
* Morning Office Traffic
* Evening Return Traffic

Controller sensitivity and timing parameters automatically adapt to traffic conditions.

### RL-Compatible Data Generation

The system exports structured traffic data suitable for future Reinforcement Learning experiments.

Captured information includes:

* Vehicle movement history
* Source and destination junctions
* Travel time
* Congestion levels
* Signal states

### Smart City Dashboard

Provides network-wide performance analytics including:

* Average waiting time
* Average network speed
* Congested junction count
* Emergency vehicle statistics
* Signal optimization statistics
* Route recommendation statistics
* Environmental impact estimates

---

# System Architecture

```text
SUMO Simulation
       |
       v
Real-Time Traffic Collection
       |
       v
Congestion Scoring Engine
       |
       +-----> Emergency Vehicle Manager
       |
       +-----> Smart Routing Engine
       |
       +-----> RL Data Generator
       |
       +-----> AI Traffic Predictor
                     |
                     v
Adaptive Signal Controller
                     |
                     v
Traffic Signal Actions
                     |
                     v
Smart City Dashboard
```

---

# Project Structure

## adaptive_signal_demo.py

Main implementation of the intelligent traffic management system.

Responsibilities:

* Predictive signal control
* Peak-hour management
* AI traffic prediction integration
* RL dataset generation
* Emergency vehicle handling
* Smart routing integration
* Dashboard generation

---

## normal_signal_demo.py

Baseline traffic simulation.

Used for performance comparison against the adaptive controller.

Features:

* Static signal operation
* Traffic monitoring
* Congestion measurement
* Dashboard reporting

---

## congestion_engine.py

Calculates and maintains congestion scores for each monitored junction.

Provides:

* Congestion classification
* Historical congestion records
* Junction ranking
* Estimated congestion reduction metrics

---

## emergency_manager.py

Handles emergency vehicle detection and signal prioritization.

Features:

* Green corridor creation
* Multi-signal coordination
* Emergency traffic analytics

---

## routing_engine.py

Provides congestion-aware route evaluation and recommendation.

Capabilities:

* Route cost estimation
* Route comparison
* Improvement analysis

---

## traffic_config.py

Contains adaptive controller profiles and peak-hour configurations.

Profiles:

* Normal Traffic
* Morning Office Traffic
* Evening Return Traffic

---

## rl_interface.py

Prototype interface for future Reinforcement Learning integration.

Responsibilities:

* State generation
* Action logging
* Training sample creation
* RL export simulation

---

## smart_city_dashboard.py

Aggregates system-wide performance metrics and environmental impact estimates.

Metrics include:

* Waiting time
* Network speed
* Congestion reduction
* Fuel savings
* CO₂ reduction

---

# Machine Learning Model

## Traffic Prediction Model

Model Type:

```text
Multi-Output Random Forest Regressor
```

Predictions:

1. Future Vehicle Count
2. Future Travel Time

### Input Features

* Day of Week
* Hour
* Time Bucket
* Source Junction
* Destination Junction
* Congestion Score
* Distance
* Lane Count
* Vehicle Speed

### Performance

Latest evaluation results:

```text
Vehicle Count R² : 0.949
Travel Time R²   : 0.866

Vehicle Count MAE : 1.48
Travel Time MAE   : 10.51 seconds
```

The model provides accurate traffic forecasting and is integrated into the adaptive controller to support predictive signal decisions.

---

# RL Dataset Format

Generated training records contain:

```text
vehicle_id
timestamp
day_of_week
hour
minute
source_junction
destination_junction
distance
lane_count
vehicle_speed
congestion_score
signal_phase
travel_time
```

This dataset can be used for future Reinforcement Learning approaches such as:

* Q-Learning
* Deep Q Networks (DQN)
* Proximal Policy Optimization (PPO)

---

# Running the Project

## Adaptive Controller

```bash
python adaptive_signal_demo.py
```

## Baseline Controller

```bash
python normal_signal_demo.py
```

## Short Simulation

```bash
python adaptive_signal_demo.py --short-test
```

## Peak-Hour Modes

```bash
python adaptive_signal_demo.py --peak-mode=morning

python adaptive_signal_demo.py --peak-mode=evening

python adaptive_signal_demo.py --peak-mode=off
```

---

# Technologies Used

* Python
* SUMO
* TraCI API
* Scikit-Learn
* Random Forest Regression
* OpenStreetMap
* JOSM
* NetEdit

---

# Future Enhancements

* Deep Reinforcement Learning-based signal optimization
* Real-time camera integration
* Vehicle-to-Infrastructure communication
* Cloud-based traffic monitoring
* GPS traffic feed integration
* Multi-intersection cooperative control
* Large-scale city deployment

---

# License

This project was developed as a research and educational prototype demonstrating AI-assisted traffic management and predictive signal control using SUMO.

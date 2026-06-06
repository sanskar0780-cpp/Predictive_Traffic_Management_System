# Intelligent Traffic Signal Optimization using SUMO and TraCI

## Overview

This project presents a complete traffic signal performance study and optimization framework using **SUMO (Simulation of Urban Mobility)** and the **TraCI API**.

The work is divided into two stages:

1. **Baseline Traffic Signal Analysis (Before Implementation)** – Evaluates traffic performance under existing fixed-time signal operations.
2. **Predictive Traffic Signal Control (After Implementation)** – Uses vehicle arrival prediction and dynamic signal adjustments to reduce congestion and improve traffic flow.

The objective is to compare traditional traffic signal management with a predictive traffic control approach and measure improvements in waiting time, congestion, and overall network efficiency.

---

# Project Objectives

* Simulate real-world traffic conditions in the MP Nagar road network.
* Analyze traffic signal performance under default configurations.
* Predict vehicle arrivals at intersections.
* Dynamically optimize traffic signal phases.
* Compare baseline and optimized traffic performance.
* Generate measurable traffic efficiency improvements.

---

# System Architecture

```text
                  Traffic Network
                         │
                         ▼
                 SUMO Simulation
                         │
        ┌────────────────┴────────────────┐
        │                                 │
        ▼                                 ▼

Baseline Analysis            Predictive Signal Controller
(Fixed-Time Signals)         (Adaptive Optimization)

        │                                 │
        ▼                                 ▼

Traffic Metrics              Vehicle Prediction
Collection                   Signal Optimization

        │                                 │
        └──────────────┬──────────────────┘
                       ▼

              Performance Comparison
```

---

# Technology Stack

| Technology        | Purpose                    |
| ----------------- | -------------------------- |
| Python            | Core Programming Language  |
| SUMO              | Traffic Simulation         |
| TraCI             | Communication with SUMO    |
| XML Configuration | Network & Route Definition |
| Statistics Module | Performance Analysis       |

---

# Project Structure

```text
├── baseline_simulation.py
├── predictive_controller.py
├── mp_nagar.sumocfg
├── network/
├── routes/
├── README.md
```

---

# Part 1: Baseline Traffic Signal Analysis

## Purpose

The baseline simulation measures traffic conditions without any intelligent optimization.

Traffic lights operate according to their predefined schedules, providing a benchmark for evaluating future improvements.

---

## Features

### Traffic Signal Monitoring

* Detects all traffic signals in the network.
* Identifies lanes controlled by each signal.
* Monitors intersection performance continuously.

### Traffic Metrics Collection

The system records:

* Vehicle waiting time
* Number of halted vehicles
* Vehicle count
* Average vehicle speed

### Network Performance Analysis

Calculates:

* Average waiting time per intersection
* Average waiting time per vehicle
* Average halted vehicles
* Average network speed
* Congestion ranking of intersections

---

## Baseline Workflow

### Step 1: Start Simulation

```python
sumoCmd = [
    sumo_binary,
    "-c",
    "mp_nagar.sumocfg",
    "--scale",
    "1"
]
```

### Step 2: Detect Traffic Lights

```python
tls_ids = list(traci.trafficlight.getIDList())
```

### Step 3: Identify Controlled Lanes

Store all lanes associated with each signal.

### Step 4: Collect Metrics

Metrics are collected every 10 simulation steps.

### Step 5: Generate Summary

The system produces network-wide traffic statistics and congestion reports.

---

# Part 2: Predictive Traffic Signal Control

## Purpose

The predictive controller proactively adjusts traffic signals before congestion occurs.

Instead of reacting to traffic after queues form, the system predicts vehicle arrivals and prepares favorable signal phases in advance.

---

## Features

### Predictive Traffic Management

* Predicts approaching vehicle arrivals.
* Calculates Estimated Time of Arrival (ETA).
* Monitors future route segments.

### Dynamic Signal Optimization

* Switches traffic lights intelligently.
* Extends green phases when needed.
* Reduces unnecessary red-light waiting.

### Real-Time Traffic Analysis

Collects:

* Waiting time
* Queue length
* Halted vehicles
* Average speed

### Performance Monitoring

Generates:

* Congestion reports
* Network-wide statistics
* Efficiency comparisons

---

## Predictive Workflow

### 1. Network Initialization

Loads the SUMO traffic network.

### 2. Signal Mapping

Identifies:

* Traffic lights
* Controlled lanes
* Green phases
* Connected road segments

### 3. Vehicle Prediction

For every vehicle:

* Route information is analyzed.
* Future intersections are identified.
* ETA is calculated.

### 4. Signal Preparation

If predicted traffic exceeds a threshold:

* Green phases are prepared early.
* Traffic flow is prioritized.

### 5. Metrics Collection

The system continuously tracks performance indicators.

### 6. Summary Reporting

Network statistics and optimization results are generated.

---

# Predictive Controller Parameters

| Parameter              | Value | Description                 |
| ---------------------- | ----- | --------------------------- |
| CHECK_INTERVAL         | 10    | Prediction update interval  |
| LOOKAHEAD_EDGES        | 5     | Future roads examined       |
| PREPARE_GREEN_BEFORE   | 25    | Green preparation threshold |
| MIN_VEHICLES_FOR_GREEN | 4     | Vehicle trigger threshold   |
| GREEN_HOLD_TIME        | 30    | Green phase duration        |
| MIN_SPEED_FOR_ETA      | 4     | Minimum ETA speed           |
| MAX_CHANGES_PER_CHECK  | 2     | Signal changes allowed      |

---

# Installation

## 1. Install SUMO

Download SUMO:

https://sumo.dlr.de

---

## 2. Install Python Dependencies

```bash
pip install traci
```

---

## 3. Configure Environment

Linux/macOS:

```bash
export SUMO_HOME=/path/to/sumo
```

Windows:

```cmd
set SUMO_HOME=C:\Program Files (x86)\Eclipse\Sumo
```

Add SUMO to your system PATH.

---

# Running the Project

## Baseline Analysis

GUI Mode:

```bash
python baseline_simulation.py
```

Non-GUI Mode:

```bash
python baseline_simulation.py --nogui
```

---

## Predictive Controller

GUI Mode:

```bash
python predictive_controller.py
```

Non-GUI Mode:

```bash
python predictive_controller.py --nogui
```

Short Test:

```bash
python predictive_controller.py --short-test
```

Non-GUI Short Test:

```bash
python predictive_controller.py --nogui --short-test
```

---

# Performance Metrics

Both implementations measure:

| Metric                   | Description                        |
| ------------------------ | ---------------------------------- |
| Average Waiting Time     | Delay experienced at intersections |
| Waiting Time per Vehicle | Individual vehicle delay           |
| Halted Vehicles          | Number of stopped vehicles         |
| Average Speed            | Mean traffic speed                 |
| Congestion Ranking       | Most congested intersections       |
| Vehicle Throughput       | Traffic flow efficiency            |

---

# Example Comparison

## Before Implementation (Baseline)

```text
Average wait per junction: 18.34 s
Average wait per vehicle: 2.95 s
Average halted vehicles: 5.12
Average speed: 6.45 m/s
```

## After Implementation (Predictive)

```text
Average wait per junction: 12.80 s
Average wait per vehicle: 1.90 s
Average halted vehicles: 3.20
Average speed: 8.10 m/s
```

---

# Applications

* Smart Cities
* Intelligent Transportation Systems (ITS)
* Urban Traffic Management
* Transportation Planning
* Congestion Reduction
* Emergency Vehicle Prioritization
* AI-Based Traffic Research
* Traffic Signal Optimization

---

# Future Scope

* Machine Learning Traffic Prediction
* Reinforcement Learning Signal Control
* Emergency Vehicle Priority Routing
* IoT Sensor Integration
* Real-Time Traffic Density Forecasting
* Multi-Intersection Coordination
* Smart City Deployment

---

# Research Contribution

This project demonstrates the impact of predictive traffic signal control by comparing:

### Before Implementation

* Fixed-time traffic signals
* Reactive traffic management
* Higher waiting times

### After Implementation

* Predictive traffic control
* Dynamic signal optimization
* Reduced congestion and delays

The resulting performance improvements can be quantified using:

* Waiting Time Reduction
* Congestion Reduction
* Improved Vehicle Throughput
* Faster Travel Times
* Better Traffic Flow Efficiency

---

# Team

**Traffic Raiders**
LNCT Group of Colleges

Project Domain: Civic Tech

---

# Authors
* Traffic Raiders Team

--

# SUMO to Unity Bridge Setup

## Current Implementation Phase

Vehicle synchronization is implemented. Congestion and traffic-light messages have transport placeholders on the Unity side, but visual rendering for those phases is intentionally not active yet.
Vehicle snapshots publish every 3 SUMO steps by default.

## Files

- `unity_bridge.py` publishes SUMO snapshots to Unity.
- `adaptive_signal_demo.py` creates the bridge and publishes vehicles every 5 SUMO steps.
- `UnityDigitalTwin/` is a writable copy of the downloaded SUMO2Unity project with runtime synchronization changes.

## Coordinate Conversion

The bridge and Unity road importer use the SUMO network `convBoundary` minimum as the visualization origin.

```text
unity_x = sumo_x - origin_x
unity_z = sumo_y - origin_y
unity_y = 0
unity_yaw = sumo_angle - 90
```

For `mp_nagar_2.net.xml`, `convBoundary` begins at `0.00,0.00`, so the origin is `(0, 0)`.

Do not use `netOffset` for the MP Nagar Unity visualization. In this network it is a projection offset, not the local scene origin.

## Runtime Flow

1. Open `D:\Traffic management\mp_nagar_2\UnityDigitalTwin` in Unity.
2. Open the `Scenario1` scene or generate the road network from the MP Nagar SUMO files.
3. Press Play in Unity.
4. Run the SUMO controller:

```powershell
python adaptive_signal_demo.py
```

If your Python environment does not have ZeroMQ installed, install `pyzmq` in the same environment used to run the SUMO controller.

```powershell
pip install pyzmq
```

## Published Vehicle Message

```json
{
  "type": "vehicles",
  "vehicles": [
    {
      "id": "veh_1",
      "x": 123.4,
      "y": 456.7,
      "angle": 90,
      "speed": 10.5,
      "vehicle_type": "focusedPassenger"
    }
  ]
}
```

Unity maps `x/y` into world position `(x, 0, y)` and applies yaw `angle - 90`.

## Validation Overlay

Unity displays:

```text
SUMO Vehicles: X
Unity Vehicles: X
Synchronization Status: OK
```

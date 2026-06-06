"""Static-signal baseline with reporting comparable to the adaptive demo."""

import sys

import traci

from congestion_engine import CongestionScoringEngine
from emergency_manager import EmergencyVehicleManager
from rl_interface import RLIntegrationLayer
from routing_engine import SmartRouteRecommendationEngine
from smart_city_dashboard import build_dashboard_metrics, print_smart_city_dashboard


sumo_binary = "sumo" if "--nogui" in sys.argv else "sumo-gui"
short_test = "--short-test" in sys.argv
sumo_cmd = [sumo_binary]

if short_test:
    sumo_cmd += ["--end", "60"]

sumo_cmd += ["-c", "mp_nagar_2.sumocfg", "--scale", "0.7"]

METRIC_INTERVAL = 10
RL_EXPORT_INTERVAL = 30
EMERGENCY_OBSERVATION_INTERVAL = 10

TARGET_TLS_IDS = [
    "cluster_3673120471_3778155308_8865441836_8865441838",
    "cluster_3713300554_3713300555_3713300572",
    "cluster_3650501033_3650501039",
    "3778150947",
]


def get_controlled_lanes(tls_id):
    """Return incoming lanes monitored by one traffic light."""

    lanes = set()

    for link_group in traci.trafficlight.getControlledLinks(tls_id):
        for link in link_group:
            if link:
                lanes.add(link[0])

    return lanes


def collect_signal_metrics(tls_id, lanes, metrics):
    """Update cumulative metrics and return the same snapshot as adaptive mode."""

    waiting_time = 0
    halted = 0
    vehicles = 0
    speed_total = 0
    speed_samples = 0
    observed_vehicle_ids = set()

    for lane_id in lanes:
        try:
            waiting_time += traci.lane.getWaitingTime(lane_id)
            halted += traci.lane.getLastStepHaltingNumber(lane_id)
            lane_vehicles = traci.lane.getLastStepVehicleNumber(lane_id)
            observed_vehicle_ids.update(traci.lane.getLastStepVehicleIDs(lane_id))
            speed = traci.lane.getLastStepMeanSpeed(lane_id)
        except traci.TraCIException:
            continue

        vehicles += lane_vehicles

        if lane_vehicles > 0 and speed >= 0:
            speed_total += speed
            speed_samples += 1

    metrics[tls_id]["waiting_time_total"] += waiting_time
    metrics[tls_id]["halted_total"] += halted
    metrics[tls_id]["vehicle_total"] += vehicles
    metrics[tls_id]["speed_total"] += speed_total
    metrics[tls_id]["speed_samples"] += speed_samples
    metrics[tls_id]["samples"] += 1
    metrics[tls_id]["waiting_vehicle_seconds"] += halted * METRIC_INTERVAL
    metrics[tls_id]["unique_vehicle_ids"].update(observed_vehicle_ids)

    return {
        "waiting_time": waiting_time,
        "halted_vehicles": halted,
        "vehicle_count": vehicles,
        "average_speed": speed_total / max(1, speed_samples),
    }


def print_summary(metrics):
    """Print the same comparison table used by the adaptive controller."""

    rows = []

    for tls_id, data in metrics.items():
        samples = max(1, data["samples"])
        unique_vehicles = max(1, len(data["unique_vehicle_ids"]))
        speed_samples = max(1, data["speed_samples"])
        rows.append(
            {
                "tls_id": tls_id,
                "avg_wait_per_step": data["waiting_time_total"] / samples,
                "avg_wait_per_vehicle": data["waiting_vehicle_seconds"] / unique_vehicles,
                "avg_halted": data["halted_total"] / samples,
                "avg_speed": data["speed_total"] / speed_samples,
            }
        )

    rows.sort(key=lambda item: item["avg_wait_per_step"], reverse=True)

    print("\n================ Baseline Simulation Summary ================")
    print(f"Traffic lights monitored: {len(rows)}")
    print(f"Simulation time: {int(traci.simulation.getTime())} seconds")
    print("\nTop junctions by average waiting time:")
    print(
        f"{'Traffic light ID':55} "
        f"{'Avg wait/step':>14} "
        f"{'Avg wait/veh':>14} "
        f"{'Avg halted':>12} "
        f"{'Avg speed':>11}"
    )
    print("-" * 112)

    for row in rows[:10]:
        print(
            f"{row['tls_id'][:55]:55} "
            f"{row['avg_wait_per_step']:14.2f} "
            f"{row['avg_wait_per_vehicle']:14.2f} "
            f"{row['avg_halted']:12.2f} "
            f"{row['avg_speed']:11.2f}"
        )

    network_halted = sum(item["halted_total"] for item in metrics.values())
    network_samples = max(1, sum(item["samples"] for item in metrics.values()))
    network_speed_samples = max(
        1,
        sum(item["speed_samples"] for item in metrics.values()),
    )
    network_speed = sum(item["speed_total"] for item in metrics.values())

    print("\n================ BASELINE AVERAGES =================")
    print(
        f"Average halted vehicles per junction sample: "
        f"{network_halted / network_samples:.2f}"
    )
    print(
        f"Average network speed samples: "
        f"{network_speed / network_speed_samples:.2f} m/s"
    )
    print("====================================================\n")


traci.start(sumo_cmd)

tls_ids = TARGET_TLS_IDS or list(traci.trafficlight.getIDList())

# BASELINE INTEGRATION: these subsystems observe and report the same scenario
# as adaptive mode, but they never alter signal phases or active vehicle routes.
steps = 0
tls_controlled_lanes = {
    tls_id: get_controlled_lanes(tls_id)
    for tls_id in tls_ids
}
signal_metrics = {
    tls_id: {
        "waiting_time_total": 0,
        "halted_total": 0,
        "vehicle_total": 0,
        "speed_total": 0,
        "speed_samples": 0,
        "samples": 0,
        "waiting_vehicle_seconds": 0,
        "unique_vehicle_ids": set(),
    }
    for tls_id in tls_ids
}

latest_snapshots = {}
congestion_engine = CongestionScoringEngine()
rl_layer = RLIntegrationLayer()
emergency_manager = EmergencyVehicleManager({})
route_engine = SmartRouteRecommendationEngine({})

print("\nRunning BASELINE traffic simulation...")
print("Focused corridor traffic and emergency fleet: enabled")
print("No adaptive optimization, emergency priority, or rerouting enabled.\n")

while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()
    simulation_time = traci.simulation.getTime()

    if short_test and simulation_time >= 60:
        break

    if steps % METRIC_INTERVAL == 0:
        for tls_id, lanes in tls_controlled_lanes.items():
            snapshot = collect_signal_metrics(tls_id, lanes, signal_metrics)
            latest_snapshots[tls_id] = snapshot
            congestion_engine.update(tls_id, snapshot, simulation_time)

    # Emergency vehicles are counted for comparison but receive no assistance.
    if steps % EMERGENCY_OBSERVATION_INTERVAL == 0:
        emergency_manager.observe()

    # The baseline exports identical RL state fields with an empty action list.
    if steps % RL_EXPORT_INTERVAL == 0 and latest_snapshots:
        rl_layer.export_state(
            latest_snapshots,
            congestion_engine.latest,
            simulation_time,
            actions=[],
        )

    steps += 1

print_summary(signal_metrics)

# Baseline improvement metrics remain zero because this run performs no control.
dashboard_metrics = build_dashboard_metrics(
    signal_metrics,
    congestion_engine,
    emergency_manager,
    rl_layer,
    route_engine,
    signal_optimizations=0,
    predicted_vehicles_processed=0,
    congestion_reduction_override=0.0,
)
print_smart_city_dashboard(dashboard_metrics, congestion_engine)
traci.close()

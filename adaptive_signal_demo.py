import sys
import traci
import os
import csv
from datetime import datetime, timedelta
import joblib
import pandas as pd

from congestion_engine import CongestionScoringEngine
from emergency_manager import EmergencyVehicleManager
from rl_interface import RLIntegrationLayer
from routing_engine import SmartRouteRecommendationEngine
from smart_city_dashboard import build_dashboard_metrics, print_smart_city_dashboard
from traffic_config import PeakHourManager, get_peak_mode_from_args
from unity_bridge import UnityBridge, UNITY_UPDATE_INTERVAL

RL_CSV = "rl_training_data.csv"
RL_CSV_HEADER = [
    "vehicle_id",
    "timestamp",
    "day_of_week",
    "hour",
    "minute",
    "source_junction",
    "destination_junction",
    "distance",
    "lane_count",
    "vehicle_speed",
    "congestion_score",
    "signal_phase",
    "travel_time",
]
SIMULATION_START_DATETIME = datetime.now().replace(
    hour=8,
    minute=0,
    second=0,
    microsecond=0,
)
TRACKING_TIMEOUT_SECONDS = 600
vehicle_tracking = {}


def initialize_rl_csv():
    """making a predictive dataset for rl training"""

    if os.path.exists(RL_CSV):
        with open(RL_CSV, newline="") as f:
            reader = csv.reader(f)
            existing_header = next(reader, [])
            first_data_row = next(reader, [])

        has_numeric_day_of_week = (
            not first_data_row
            or (
                len(first_data_row) > 2
                and first_data_row[2].isdigit()
            )
        )

        if existing_header == RL_CSV_HEADER and has_numeric_day_of_week:
            return

        base_name, extension = os.path.splitext(RL_CSV)
        backup_path = f"{base_name}_legacy{extension}"
        backup_index = 1

        while os.path.exists(backup_path):
            backup_path = f"{base_name}_legacy_{backup_index}{extension}"
            backup_index += 1

        os.replace(RL_CSV, backup_path)
        print(f"Old RL CSV schema preserved as {backup_path}")

    with open(RL_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(RL_CSV_HEADER)


initialize_rl_csv()

sumo_binary = "sumo" if "--nogui" in sys.argv else "sumo-gui"
short_test = "--short-test" in sys.argv
sumoCmd = [sumo_binary]

if short_test:
    sumoCmd += ["--end", "60"]

sumoCmd += ["-c", "mp_nagar_2.sumocfg", "--scale", "0.7"]

CHECK_INTERVAL = 10
LOOKAHEAD_EDGES = 5
PREPARE_GREEN_BEFORE = 25
MIN_VEHICLES_FOR_GREEN = 4
MIN_SECONDS_BETWEEN_CHANGES = 30
GREEN_HOLD_TIME = 30
MAX_GREEN_HOLD_TIME = 25
MAX_CONSECUTIVE_ACTIONS_PER_TLS = 2
MIN_SPEED_FOR_ETA = 4
MAX_CHANGES_PER_CHECK = 2
METRIC_INTERVAL = 10
RL_EXPORT_INTERVAL = 1
ROUTE_RECOMMENDATION_INTERVAL = 50

TARGET_TLS_IDS = []

def is_green_state(state):
    return state in ("G", "g")


def activate_better_program_if_available(tls_id):
    try:
        program_ids = [logic.programID for logic in traci.trafficlight.getAllProgramLogics(tls_id)]
    except traci.TraCIException:
        return

    if "1" in program_ids:
        traci.trafficlight.setProgram(tls_id, "1")


def get_edge_length(edge_id):
    try:
        lane_count = traci.edge.getLaneNumber(edge_id)
        if lane_count == 0:
            return 80
        return traci.lane.getLength(f"{edge_id}_0")
    except traci.TraCIException:
        return 80


def build_signal_maps(tls_ids):
    lane_to_tls = {}
    lane_green_phases = {}

    for tls_id in tls_ids:
        lane_green_phases[tls_id] = {}
        logics = traci.trafficlight.getAllProgramLogics(tls_id)
        current_program = traci.trafficlight.getProgram(tls_id)
        logic = next((item for item in logics if item.programID == current_program), None)

        if logic is None:
            continue

        controlled_links = traci.trafficlight.getControlledLinks(tls_id)

        for phase_index, phase in enumerate(logic.phases):
            for link_index, state in enumerate(phase.state):
                if not is_green_state(state) or link_index >= len(controlled_links):
                    continue

                for link in controlled_links[link_index]:
                    if not link:
                        continue

                    lane_id = link[0]
                    edge_id = traci.lane.getEdgeID(lane_id)

                    if edge_id.startswith(":"):
                        continue

                    lane_to_tls.setdefault(edge_id, []).append((tls_id, lane_id))
                    lane_green_phases[tls_id].setdefault(lane_id, set()).add(phase_index)

    return lane_to_tls, lane_green_phases


def estimate_arrival_time(route, current_index, target_index, speed):
    distance = 0

    for edge_index in range(current_index + 1, target_index + 1):
        distance += get_edge_length(route[edge_index])

    return distance / max(speed, MIN_SPEED_FOR_ETA)


def predict_arrivals(
    edge_to_tls_lanes,
    lookahead_edges=LOOKAHEAD_EDGES,
    prepare_green_before=PREPARE_GREEN_BEFORE,
):
    #predicting the lookahead with runtimne sens.

    predictions = {}

    for vehicle_id in traci.vehicle.getIDList():
        route = traci.vehicle.getRoute(vehicle_id)
        current_index = traci.vehicle.getRouteIndex(vehicle_id)

        if current_index < 0:
            continue

        try:
            speed = traci.vehicle.getSpeed(vehicle_id)
        except traci.TraCIException:
            continue
        end_index = min(len(route), current_index + lookahead_edges + 1)

        for edge_index in range(current_index + 1, end_index):
            edge_id = route[edge_index]

            if edge_id not in edge_to_tls_lanes:
                continue

            eta = estimate_arrival_time(route, current_index, edge_index, speed)

            if eta > prepare_green_before:
                continue

            for tls_id, lane_id in edge_to_tls_lanes[edge_id]:
                key = (tls_id, lane_id)
                predictions.setdefault(key, {"vehicles": 0, "eta": eta})
                predictions[key]["vehicles"] += 1
                predictions[key]["eta"] = min(predictions[key]["eta"], eta)

            break

    return predictions


def current_phase_serves_lane(tls_id, lane_id, lane_green_phases):
    current_phase = traci.trafficlight.getPhase(tls_id)
    return current_phase in lane_green_phases.get(tls_id, {}).get(lane_id, set())


def prepare_green(tls_id, lane_id, lane_green_phases, hold_time=GREEN_HOLD_TIME):

    #prepare the green by normal and emergency control

    green_phases = sorted(lane_green_phases.get(tls_id, {}).get(lane_id, []))

    if not green_phases:
        return None

    if current_phase_serves_lane(tls_id, lane_id, lane_green_phases):
        traci.trafficlight.setPhaseDuration(tls_id, hold_time)
        return "held"

    traci.trafficlight.setPhase(tls_id, green_phases[0])
    traci.trafficlight.setPhaseDuration(tls_id, hold_time)
    return "prepared"


def get_controlled_lanes(tls_id):
    lanes = set()

    for link_group in traci.trafficlight.getControlledLinks(tls_id):
        for link in link_group:
            if link:
                lanes.add(link[0])

    return lanes


def collect_signal_metrics(tls_id, lanes, metrics):

    #Update the metrics and send the live junction snapshot

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


def get_prediction_priority(prediction, profile):

    #When high flow are there we give em extra priority

    vehicle_count = prediction["vehicles"]
    multiplier = 1.0

    if vehicle_count >= profile.high_flow_vehicle_threshold:
        multiplier = profile.high_flow_priority_multiplier

    return vehicle_count * multiplier


def evaluate_route_recommendations(route_engine, congestion_scores, max_vehicles=5):

    #Recommend routes from sumo withour altering it

    evaluated = 0

    for vehicle_id in traci.vehicle.getIDList():
        if evaluated >= max_vehicles:
            break

        try:
            route = traci.vehicle.getRoute(vehicle_id)
            current_index = traci.vehicle.getRouteIndex(vehicle_id)
        except traci.TraCIException:
            continue

        if current_index < 0 or current_index >= len(route) - 1:
            continue

        remaining_route = list(route[current_index:])

        try:
            sumo_route = traci.simulation.findRoute(
                remaining_route[0],
                remaining_route[-1],
            )
            candidate_routes = [list(sumo_route.edges)] if sumo_route.edges else []
        except traci.TraCIException:
            candidate_routes = []

        route_engine.evaluate(
            vehicle_id,
            remaining_route,
            candidate_routes,
            congestion_scores,
        )
        evaluated += 1


def print_summary(metrics):
    rows = []

    for tls_id, data in metrics.items():
        samples = max(1, data["samples"])
        unique_vehicles = max(1, len(data["unique_vehicle_ids"]))
        speed_samples = max(1, data["speed_samples"])
        avg_wait_per_step = data["waiting_time_total"] / samples
        avg_wait_per_vehicle = data["waiting_vehicle_seconds"] / unique_vehicles
        avg_halted = data["halted_total"] / samples
        avg_speed = data["speed_total"] / speed_samples

        rows.append(
            {
                "tls_id": tls_id,
                "avg_wait_per_step": avg_wait_per_step,
                "avg_wait_per_vehicle": avg_wait_per_vehicle,
                "avg_halted": avg_halted,
                "avg_speed": avg_speed,
                "vehicle_samples": data["vehicle_total"],
            }
        )

    rows.sort(key=lambda item: item["avg_wait_per_step"], reverse=True)

    print("\n================ Simulation Summary ================")
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

    network_wait = sum(item["waiting_time_total"] for item in metrics.values())
    network_halted = sum(item["halted_total"] for item in metrics.values())
    network_samples = max(1, sum(item["samples"] for item in metrics.values()))
    network_speed_samples = max(1, sum(item["speed_samples"] for item in metrics.values()))
    network_speed = sum(item["speed_total"] for item in metrics.values())
    network_vehicle_samples = max(1, sum(item["vehicle_total"] for item in metrics.values()))

    print("\n============= AFTER IMPLEMENTATION AVERAGES ===============")
    print(f"Average halted vehicles per junction sample: {network_halted / network_samples:.2f}")
    print(f"Average network speed samples: {network_speed / network_speed_samples:.2f} m/s")
    print("=============================================================\n")


traci.start(sumoCmd)
unity_bridge = UnityBridge("mp_nagar_2.net.xml", update_interval=UNITY_UPDATE_INTERVAL)

traffic_predictor = joblib.load("traffic_predictor.pkl")

source_encoder = joblib.load("source_encoder.pkl")

destination_encoder = joblib.load("destination_encoder.pkl")

print("Traffic prediction model loaded")

# NEW SUBSYSTEM INTEGRATION: all feature managers consume the existing
# controller maps and metrics rather than replacing the predictive controller.
steps = 0
last_signal_change = {}
consecutive_signal_actions = {}
tls_ids = TARGET_TLS_IDS or list(traci.trafficlight.getIDList())

for tls_id in tls_ids:
    activate_better_program_if_available(tls_id)
    last_signal_change[tls_id] = -MIN_SECONDS_BETWEEN_CHANGES
    consecutive_signal_actions[tls_id] = 0

edge_to_tls_lanes, lane_green_phases = build_signal_maps(tls_ids)
tls_controlled_lanes = {tls_id: get_controlled_lanes(tls_id) for tls_id in tls_ids}
peak_hour_manager = PeakHourManager(get_peak_mode_from_args(sys.argv))
congestion_engine = CongestionScoringEngine()
emergency_manager = EmergencyVehicleManager(edge_to_tls_lanes)
rl_layer = RLIntegrationLayer()
route_engine = SmartRouteRecommendationEngine(edge_to_tls_lanes)

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
actions_since_rl_sample = []
signal_optimizations = 0
predicted_vehicles_processed = 0

print(f"Predictive controller started for {len(tls_ids)} traffic lights")
print("Traffic scale set to 0.7")
print(f"Peak-hour mode: {peak_hour_manager.mode}")
print("Focused corridor traffic and emergency fleet: enabled")

def get_simulation_datetime(simulation_time):
    #convert SUMO seconds into calender format

    return SIMULATION_START_DATETIME + timedelta(seconds=int(simulation_time))


def get_primary_junction_for_edge(edge_to_tls_lanes, edge_id):
    #Return one monitored junction for an incoming edge without duplicates

    junction_info = edge_to_tls_lanes.get(edge_id, [])

    if not junction_info:
        return None, None

    return junction_info[0]


def get_route_distance(route, source_index, destination_index):
    #calculate travel time between two routes

    if source_index < 0 or destination_index < source_index:
        return 0.0

    distance = 0.0

    for edge_index in range(source_index + 1, destination_index + 1):
        if edge_index >= len(route):
            break
        distance += get_edge_length(route[edge_index])

    return distance


def predict_future_traffic(
    source_junction,
    destination_junction,
    congestion_score,
    distance,
    lane_count,
    vehicle_speed,
):
    try:

        source_encoded = (
            source_encoder.transform(
                [source_junction]
            )[0]
        )

        destination_encoded = (
            destination_encoder.transform(
                [destination_junction]
            )[0]
        )

    except ValueError:

        return None

    sim_time = traci.simulation.getTime()

    hour = int(
        (sim_time // 3600) % 24
    )

    day_of_week = int(
        (sim_time // 86400) % 7
    )

    minute_bucket = int(
        ((sim_time % 3600) // 900)
    )

    sample = pd.DataFrame([{
        "day_of_week": day_of_week,
        "hour": hour,
        "minute_bucket": minute_bucket,
        "source_junction": source_encoded,
        "destination_junction": destination_encoded,
        "avg_congestion": congestion_score,
        "distance": distance,
        "lane_count": lane_count,
        "vehicle_speed": vehicle_speed,
    }])

    prediction = (
        traffic_predictor.predict(sample)
    )

    return {
        "vehicles":
            prediction[0][0],
        "travel_time":
            prediction[0][1]
    }


def cleanup_vehicle_tracking(active_vehicle_ids, current_time):
    #cleanup of vehicles from memory

    stale_vehicle_ids = []

    for vehicle_id, data in vehicle_tracking.items():
        timed_out = current_time - data["entry_time"] > TRACKING_TIMEOUT_SECONDS

        if vehicle_id not in active_vehicle_ids or timed_out:
            stale_vehicle_ids.append(vehicle_id)

    for vehicle_id in stale_vehicle_ids:
        vehicle_tracking.pop(vehicle_id, None)


def export_rl_vehicle_data(edge_to_tls_lanes, congestion_engine):
    #create a csv for exporting data to train the rl model

    simulation_time = traci.simulation.getTime()
    current_time = int(simulation_time)
    current_datetime = get_simulation_datetime(simulation_time)
    active_vehicle_ids = set(traci.vehicle.getIDList())
    rows = []

    cleanup_vehicle_tracking(active_vehicle_ids, simulation_time)

    for vehicle_id in active_vehicle_ids:
        try:
            lane_id = traci.vehicle.getLaneID(vehicle_id)
            route = traci.vehicle.getRoute(vehicle_id)
            route_index = traci.vehicle.getRouteIndex(vehicle_id)
            vehicle_speed = traci.vehicle.getSpeed(vehicle_id)
        except traci.TraCIException:
            continue

        if route_index < 0 or not lane_id:
            continue

        try:
            current_edge = traci.lane.getEdgeID(lane_id)
        except traci.TraCIException:
            continue

        if current_edge.startswith(":"):
            continue

        destination_junction, _controlled_lane = get_primary_junction_for_edge(
            edge_to_tls_lanes,
            current_edge,
        )

        if destination_junction is None:
            continue

        tracked_vehicle = vehicle_tracking.get(vehicle_id)

        if tracked_vehicle is None:
            vehicle_tracking[vehicle_id] = {
                "source_junction": destination_junction,
                "entry_time": simulation_time,
                "source_route_index": route_index,
                "source_edge": current_edge,
            }
            continue

        if tracked_vehicle["source_junction"] == destination_junction:
            continue

        travel_time = simulation_time - tracked_vehicle["entry_time"]
        distance = get_route_distance(
            route,
            tracked_vehicle["source_route_index"],
            route_index,
        )

        try:
            lane_count = traci.edge.getLaneNumber(current_edge)
        except traci.TraCIException:
            lane_count = 0

        congestion_score = 0

        if destination_junction in congestion_engine.latest:
            congestion_score = congestion_engine.latest[destination_junction]["score"]

        try:
            signal_phase = traci.trafficlight.getPhase(destination_junction)
        except traci.TraCIException:
            signal_phase = -1

        rows.append([
            vehicle_id,
            current_time,
            current_datetime.weekday(),
            current_datetime.hour,
            current_datetime.minute,
            tracked_vehicle["source_junction"],
            destination_junction,
            round(distance, 2),
            lane_count,
            round(vehicle_speed, 2),
            congestion_score,
            signal_phase,
            round(travel_time, 2),
        ])

        vehicle_tracking[vehicle_id] = {
            "source_junction": destination_junction,
            "entry_time": simulation_time,
            "source_route_index": route_index,
            "source_edge": current_edge,
        }

    if rows:
        with open(RL_CSV, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()
    simulation_time = traci.simulation.getTime()
    active_profile = peak_hour_manager.get_profile(simulation_time)
    peak_hour_manager.report_profile_change(active_profile)

    if unity_bridge.should_publish(steps):
        unity_bridge.publish_vehicles(traci)

    if short_test and simulation_time >= 60:
        break

    if steps % METRIC_INTERVAL == 0:
        for tls_id, lanes in tls_controlled_lanes.items():
            snapshot = collect_signal_metrics(tls_id, lanes, signal_metrics)
            latest_snapshots[tls_id] = snapshot
            congestion_engine.update(tls_id, snapshot, simulation_time)

#sanskar
    # if steps % RL_EXPORT_INTERVAL == 0 and latest_snapshots:
    #     export_rl_vehicle_data(edge_to_tls_lanes, congestion_engine)
    #
    #     rl_layer.export_state(
    #         latest_snapshots,
    #         congestion_engine.latest,
    #         simulation_time,
    #         actions_since_rl_sample,
    #     )
    #     actions_since_rl_sample = []

    # SMART ROUTING INTEGRATION POINT: recommendations are advisory in this
    # prototype and therefore do not overwrite active SUMO vehicle routes.
    if steps % ROUTE_RECOMMENDATION_INTERVAL == 0 and congestion_engine.latest:
        evaluate_route_recommendations(
            route_engine,
            congestion_engine.get_scores(),
        )

    if steps % CHECK_INTERVAL == 0:
        # Emergency corridors run before normal prediction decisions and reserve
        # their traffic lights for this control cycle.
        emergency_tls, emergency_events = emergency_manager.process(
            simulation_time,
            lambda tls_id, lane_id, hold_time: prepare_green(
                tls_id,
                lane_id,
                lane_green_phases,
                hold_time,
            ),
        )
        for event in emergency_events:
            last_signal_change[event["tls_id"]] = steps
            consecutive_signal_actions[event["tls_id"]] = 0
            signal_optimizations += 1
            actions_since_rl_sample.append(
                f"emergency:{event['tls_id']}:{event['action']}"
            )

        predictions = predict_arrivals(
            edge_to_tls_lanes,
            prepare_green_before=active_profile.prepare_green_before,
        )
        predicted_vehicles_processed += sum(
            data["vehicles"] for data in predictions.values()
        )
        print("\n-------- Predictive Signal Data --------")

        changes_this_check = 0

        future_predictions = {}

        for (tls_id, lane_id), data in sorted(
            predictions.items(),
            key=lambda item: get_prediction_priority(item[1], active_profile),
            reverse=True,
        ):
            if changes_this_check >= active_profile.max_changes_per_check:
                break

            future = None

            if tls_id not in future_predictions:

                current_snapshot = latest_snapshots.get(tls_id)

                if (
                        current_snapshot
                        and tls_id in source_encoder.classes_
                        and tls_id in destination_encoder.classes_
                ):
                    future_predictions[tls_id] = predict_future_traffic(
                        source_junction=tls_id,
                        destination_junction=tls_id,
                        congestion_score=congestion_engine.latest.get(
                            tls_id,
                            {}
                        ).get(
                            "score",
                            0
                        ),
                        distance=500,
                        lane_count=2,
                        vehicle_speed=current_snapshot["average_speed"],
                    )

            future = future_predictions.get(tls_id)

            if future:
                print(f"\nAI Prediction [{tls_id}]")
                print(f"Future Vehicles: {future['vehicles']:.1f}")
                print(f"Future Travel Time: {future['travel_time']:.1f}s")

            predicted_volume = data["vehicles"]

            if future:
                predicted_volume = max(
                    predicted_volume,
                    int(future["vehicles"])
                )

            enough_vehicles = (
                    predicted_volume >= active_profile.min_vehicles_for_green
            )
            cooldown_done = steps - last_signal_change[tls_id] >= MIN_SECONDS_BETWEEN_CHANGES
            fairness_available = (
                consecutive_signal_actions[tls_id] < MAX_CONSECUTIVE_ACTIONS_PER_TLS
            )

            if (
                tls_id in emergency_tls
                or not enough_vehicles
                or not cooldown_done
                or not fairness_available
            ):
                continue

            action = prepare_green(
                tls_id,
                lane_id,
                lane_green_phases,
                min(active_profile.green_hold_time, MAX_GREEN_HOLD_TIME),
            )

            if action:
                changes_this_check += 1
                last_signal_change[tls_id] = steps
                consecutive_signal_actions[tls_id] += 1
                signal_optimizations += 1
                actions_since_rl_sample.append(f"predictive:{tls_id}:{action}")
                edge_id = traci.lane.getEdgeID(lane_id)
                print(f"\nSignal: {tls_id}")
                print(f"Incoming road: {edge_id}")
                print(f"Current Vehicles: {data['vehicles']}")

                if future:
                    print(f"AI Predicted Volume: " f"{future['vehicles']:.1f}")

                    print(f"AI Predicted Travel Time: " f"{future['travel_time']:.1f}s")

                print(f"Nearest arrival: {int(data['eta'])} seconds")
                print(
                    f"AI optimized signal "
                    f"({action}) before congestion formed"
                )

        # Let signals return to their programmed cycles after two consecutive
        # interventions so less-busy approaches are not starved indefinitely.
        for tls_id in consecutive_signal_actions:
            if steps - last_signal_change[tls_id] >= MIN_SECONDS_BETWEEN_CHANGES * 2:
                consecutive_signal_actions[tls_id] = 0

    steps += 1

print_summary(signal_metrics)
dashboard_metrics = build_dashboard_metrics(
    signal_metrics,
    congestion_engine,
    emergency_manager,
    rl_layer,
    route_engine,
    signal_optimizations,
    predicted_vehicles_processed,
)
print_smart_city_dashboard(dashboard_metrics, congestion_engine)
unity_bridge.close()
traci.close()

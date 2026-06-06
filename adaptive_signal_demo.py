import sys
import traci


sumo_binary = "sumo" if "--nogui" in sys.argv else "sumo-gui"
short_test = "--short-test" in sys.argv
sumoCmd = [sumo_binary]

if short_test:
    sumoCmd += ["--end", "60"]

sumoCmd += ["-c", "mp_nagar.sumocfg", "--scale", "0.4"]

CHECK_INTERVAL = 10
LOOKAHEAD_EDGES = 5
PREPARE_GREEN_BEFORE = 25
MIN_VEHICLES_FOR_GREEN = 4
MIN_SECONDS_BETWEEN_CHANGES = 30
GREEN_HOLD_TIME = 30
MIN_SPEED_FOR_ETA = 4
MAX_CHANGES_PER_CHECK = 2
METRIC_INTERVAL = 10

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


def predict_arrivals(edge_to_tls_lanes):
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
        end_index = min(len(route), current_index + LOOKAHEAD_EDGES + 1)

        for edge_index in range(current_index + 1, end_index):
            edge_id = route[edge_index]

            if edge_id not in edge_to_tls_lanes:
                continue

            eta = estimate_arrival_time(route, current_index, edge_index, speed)

            if eta > PREPARE_GREEN_BEFORE:
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


def prepare_green(tls_id, lane_id, lane_green_phases):
    green_phases = sorted(lane_green_phases.get(tls_id, {}).get(lane_id, []))

    if not green_phases:
        return None

    if current_phase_serves_lane(tls_id, lane_id, lane_green_phases):
        traci.trafficlight.setPhaseDuration(tls_id, GREEN_HOLD_TIME)
        return "held"

    traci.trafficlight.setPhase(tls_id, green_phases[0])
    traci.trafficlight.setPhaseDuration(tls_id, GREEN_HOLD_TIME)
    return "prepared"


def get_controlled_lanes(tls_id):
    lanes = set()

    for link_group in traci.trafficlight.getControlledLinks(tls_id):
        for link in link_group:
            if link:
                lanes.add(link[0])

    return lanes


def collect_signal_metrics(tls_id, lanes, metrics):
    waiting_time = 0
    halted = 0
    vehicles = 0
    speed_total = 0
    speed_samples = 0

    for lane_id in lanes:
        try:
            waiting_time += traci.lane.getWaitingTime(lane_id)
            halted += traci.lane.getLastStepHaltingNumber(lane_id)
            lane_vehicles = traci.lane.getLastStepVehicleNumber(lane_id)
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


def print_summary(metrics):
    rows = []

    for tls_id, data in metrics.items():
        samples = max(1, data["samples"])
        vehicle_samples = max(1, data["vehicle_total"])
        speed_samples = max(1, data["speed_samples"])
        avg_wait_per_step = data["waiting_time_total"] / samples
        avg_wait_per_vehicle = data["waiting_time_total"] / vehicle_samples
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
    network_vehicle_samples = max(1, sum(item["vehicle_total"] for item in metrics.values()))

    print("\nNetwork averages:")
    print(f"Average wait per junction sample: {network_wait / network_samples:.2f} seconds")
    print(f"Average wait per vehicle sample: {network_wait / network_vehicle_samples:.2f} seconds")
    print(f"Average halted vehicles per junction sample: {network_halted / network_samples:.2f}")
    print("====================================================\n")


traci.start(sumoCmd)

steps = 0
last_signal_change = {}
tls_ids = TARGET_TLS_IDS or list(traci.trafficlight.getIDList())

for tls_id in tls_ids:
    activate_better_program_if_available(tls_id)
    last_signal_change[tls_id] = -MIN_SECONDS_BETWEEN_CHANGES

edge_to_tls_lanes, lane_green_phases = build_signal_maps(tls_ids)
tls_controlled_lanes = {tls_id: get_controlled_lanes(tls_id) for tls_id in tls_ids}
signal_metrics = {
    tls_id: {
        "waiting_time_total": 0,
        "halted_total": 0,
        "vehicle_total": 0,
        "speed_total": 0,
        "speed_samples": 0,
        "samples": 0,
    }
    for tls_id in tls_ids
}

print(f"Predictive controller started for {len(tls_ids)} traffic lights")
print("Traffic scale set to 0.45")

while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()

    if short_test and traci.simulation.getTime() >= 60:
        break

    if steps % METRIC_INTERVAL == 0:
        for tls_id, lanes in tls_controlled_lanes.items():
            collect_signal_metrics(tls_id, lanes, signal_metrics)

    if steps % CHECK_INTERVAL == 0:
        predictions = predict_arrivals(edge_to_tls_lanes)
        print("\n-------- Predictive Signal Data --------")

        changes_this_check = 0

        for (tls_id, lane_id), data in sorted(
            predictions.items(),
            key=lambda item: item[1]["vehicles"],
            reverse=True,
        ):
            if changes_this_check >= MAX_CHANGES_PER_CHECK:
                break

            enough_vehicles = data["vehicles"] >= MIN_VEHICLES_FOR_GREEN
            cooldown_done = steps - last_signal_change[tls_id] >= MIN_SECONDS_BETWEEN_CHANGES

            if not enough_vehicles or not cooldown_done:
                continue

            action = prepare_green(tls_id, lane_id, lane_green_phases)

            if action:
                changes_this_check += 1
                last_signal_change[tls_id] = steps
                edge_id = traci.lane.getEdgeID(lane_id)
                print(f"\nSignal: {tls_id}")
                print(f"Incoming road: {edge_id}")
                print(f"Predicted vehicles: {data['vehicles']}")
                print(f"Nearest arrival: {int(data['eta'])} seconds")
                print(f"Green {action} before vehicles arrive")

    steps += 1

print_summary(signal_metrics)
traci.close()

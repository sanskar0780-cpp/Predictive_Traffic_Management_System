import sys
import traci


sumo_binary = "sumo" if "--nogui" in sys.argv else "sumo-gui"

sumoCmd = [
    sumo_binary,
    "-c",
    "mp_nagar.sumocfg",
    "--scale",
    "1"
]

TARGET_TLS_IDS = [
    "cluster_3673120471_3778155308_8865441836_8865441838",
    "cluster_3713300554_3713300555_3713300572",
    "cluster_3650501033_3650501039",
    "3778150947",
    "315917050",
    "366143607",
    "366143610",
    "3673163439",
    "3691364000",
    "3778155323"
]

traci.start(sumoCmd)

steps = 0
METRIC_INTERVAL = 10

tls_ids = list(traci.trafficlight.getIDList())

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

def get_controlled_lanes(tls_id):

    lanes = set()

    for link_group in traci.trafficlight.getControlledLinks(tls_id):

        for link in link_group:

            if link:
                lanes.add(link[0])

    return lanes

tls_ids = TARGET_TLS_IDS or list(traci.trafficlight.getIDList())

tls_controlled_lanes = {
    tls_id: get_controlled_lanes(tls_id)
    for tls_id in tls_ids
}

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

        avg_wait_per_vehicle = (
            data["waiting_time_total"] / vehicle_samples
        )

        avg_halted = data["halted_total"] / samples

        avg_speed = data["speed_total"] / speed_samples

        rows.append({

            "tls_id": tls_id,
            "avg_wait_per_step": avg_wait_per_step,
            "avg_wait_per_vehicle": avg_wait_per_vehicle,
            "avg_halted": avg_halted,
            "avg_speed": avg_speed,
        })

    rows.sort(
        key=lambda item: item["avg_wait_per_step"],
        reverse=True
    )

    print("\n================ BEFORE IMPLEMENTATION SUMMARY ================")

    print(f"Traffic lights monitored: {len(rows)}")

    print(
        f"\n{'Traffic Light ID':55}"
        f"{'Avg Wait':>12}"
        f"{'Avg Halted':>14}"
        f"{'Avg Speed (m/s)':>12}"
    )

    print("-" * 95)

    for row in rows[:10]:

        print(

            f"{row['tls_id'][:55]:55}"

            f"{row['avg_wait_per_step']:12.2f}"

            f"{row['avg_halted']:14.2f}"

            f"{row['avg_speed']:12.2f}"
        )

    print("\n==================================================")

    network_wait = sum(
        item["waiting_time_total"]
        for item in metrics.values()
    )

    network_halted = sum(
        item["halted_total"]
        for item in metrics.values()
    )

    network_speed = sum(
        item["speed_total"]
        for item in metrics.values()
    )

    network_speed_samples = max(
        1,
        sum(item["speed_samples"] for item in metrics.values())
    )

    network_samples = max(
        1,
        sum(item["samples"] for item in metrics.values())
    )

    network_vehicle_samples = max(
        1,
        sum(item["vehicle_total"] for item in metrics.values())
    )

    print("\n================ BEFORE IMPLEMENTATION SUMMARY ================")

    print(
        f"Average wait per junction sample: "
        f"{network_wait / network_samples:.2f} seconds"
    )

    print(
        f"Average wait per vehicle sample: "
        f"{network_wait / network_vehicle_samples:.2f} seconds"
    )

    print(
        f"Average halted vehicles per junction sample: "
        f"{network_halted / network_samples:.2f}"
    )

    print(
        f"Average network speed: "
        f"{network_speed / network_speed_samples:.2f} m/s"
    )

    print("====================================================\n")

print("\nRunning BASELINE traffic simulation...")
print("No adaptive optimization enabled.\n")


while traci.simulation.getMinExpectedNumber() > 0:

    traci.simulationStep()

    # collect metrics every few steps
    if steps % METRIC_INTERVAL == 0:

        for tls_id, lanes in tls_controlled_lanes.items():

            collect_signal_metrics(
                tls_id,
                lanes,
                signal_metrics
            )

    steps += 1


# ---------------- FINAL SUMMARY ---------------- #

print_summary(signal_metrics)

traci.close()
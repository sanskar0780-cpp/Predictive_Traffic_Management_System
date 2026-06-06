"""Emergency vehicle detection and predictive green-corridor management."""

import traci


EMERGENCY_PREFIXES = ("ambulance_", "fire_", "police_")


class EmergencyVehicleManager:
    """Prioritizes signals found ahead on emergency vehicle routes."""

    def __init__(self, edge_to_tls_lanes, lookahead_edges=12, max_corridor_signals=3):
        self.edge_to_tls_lanes = edge_to_tls_lanes
        self.lookahead_edges = lookahead_edges
        self.max_corridor_signals = max_corridor_signals
        self.detected_vehicle_ids = set()
        self.assisted_vehicle_ids = set()
        self.last_priority_time = {}
        self.emergency_priority_events = 0

    @property
    def emergency_vehicles_detected(self):
        return len(self.detected_vehicle_ids)

    @property
    def emergency_vehicles_assisted(self):
        return len(self.assisted_vehicle_ids)

    @staticmethod
    def is_emergency_vehicle(vehicle_id):
        return vehicle_id.startswith(EMERGENCY_PREFIXES)

    def observe(self):
        """Detect emergency vehicles without applying signal priority."""

        newly_detected = []

        for vehicle_id in traci.vehicle.getIDList():
            if not self.is_emergency_vehicle(vehicle_id):
                continue
            if vehicle_id in self.detected_vehicle_ids:
                continue

            self.detected_vehicle_ids.add(vehicle_id)
            newly_detected.append(vehicle_id)
            print(f"\n[EMERGENCY DETECTED] {vehicle_id}")

        return newly_detected

    def _find_upcoming_signals(self, vehicle_id):
        route = traci.vehicle.getRoute(vehicle_id)
        current_index = traci.vehicle.getRouteIndex(vehicle_id)
        upcoming = []
        seen_tls = set()

        if current_index < 0:
            return upcoming

        end_index = min(len(route), current_index + self.lookahead_edges + 1)

        # Include the current edge so an emergency vehicle already approaching
        # a controlled junction can receive immediate priority.
        for edge_index in range(current_index, end_index):
            edge_id = route[edge_index]

            for tls_id, lane_id in self.edge_to_tls_lanes.get(edge_id, []):
                if tls_id in seen_tls:
                    continue
                seen_tls.add(tls_id)
                upcoming.append(
                    {
                        "tls_id": tls_id,
                        "lane_id": lane_id,
                        "edge_id": edge_id,
                        "edges_ahead": edge_index - current_index,
                    }
                )

        return upcoming[: self.max_corridor_signals]

    def process(self, simulation_time, prepare_green_callback):
        """Create corridors and return traffic lights reserved this cycle."""

        prioritized_tls = set()
        events = []

        self.observe()

        for vehicle_id in traci.vehicle.getIDList():
            if not self.is_emergency_vehicle(vehicle_id):
                continue

            upcoming = self._find_upcoming_signals(vehicle_id)

            if upcoming:
                print(
                    f"[GREEN CORRIDOR] {vehicle_id}: preparing "
                    f"{len(upcoming)} upcoming signal(s)"
                )

            for corridor_item in upcoming:
                tls_id = corridor_item["tls_id"]
                event_key = (vehicle_id, tls_id)
                last_time = self.last_priority_time.get(event_key, -30)

                if simulation_time - last_time < 20:
                    prioritized_tls.add(tls_id)
                    continue

                action = prepare_green_callback(
                    tls_id,
                    corridor_item["lane_id"],
                    hold_time=45,
                )

                if not action:
                    continue

                self.last_priority_time[event_key] = simulation_time
                self.emergency_priority_events += 1
                self.assisted_vehicle_ids.add(vehicle_id)
                prioritized_tls.add(tls_id)
                event = {
                    "vehicle_id": vehicle_id,
                    "tls_id": tls_id,
                    "edge_id": corridor_item["edge_id"],
                    "edges_ahead": corridor_item["edges_ahead"],
                    "action": action,
                }
                events.append(event)
                print(
                    f"  -> Signal {tls_id} {action} for "
                    f"{corridor_item['edge_id']} "
                    f"({corridor_item['edges_ahead']} edges ahead)"
                )

        return prioritized_tls, events

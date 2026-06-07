import json
import threading
import time
import xml.etree.ElementTree as ET

try:
    import zmq
except ImportError:  # Keep the SUMO controller usable without Unity tooling.
    zmq = None


UNITY_UPDATE_INTERVAL = 3


class UnityBridge:
    """Publish SUMO state snapshots to Unity's existing NetMQ listener."""

    def __init__(
        self,
        net_file,
        pub_endpoint="tcp://*:5556",
        router_endpoint="tcp://*:5557",
        update_interval=UNITY_UPDATE_INTERVAL,
        enabled=True,
    ):
        self.net_file = net_file
        self.pub_endpoint = pub_endpoint
        self.router_endpoint = router_endpoint
        self.update_interval = update_interval
        self.enabled = enabled and zmq is not None
        self.origin_x, self.origin_y = self._read_conv_boundary_origin(net_file)

        self._context = None
        self._publisher = None
        self._router = None
        self._router_thread = None
        self._running = False
        self.messages_published = 0
        self.bytes_published = 0
        self._last_stats_log = time.monotonic()

        if not self.enabled:
            if zmq is None:
                print("Unity bridge disabled: pyzmq is not installed.")
            return

        self._context = zmq.Context.instance()
        self._publisher = self._context.socket(zmq.PUB)
        self._publisher.setsockopt(zmq.SNDHWM, 10)
        self._publisher.bind(pub_endpoint)

        self._router = self._context.socket(zmq.ROUTER)
        self._router.setsockopt(zmq.RCVHWM, 100)
        self._router.setsockopt(zmq.SNDHWM, 100)
        self._router.bind(router_endpoint)

        self._running = True
        self._router_thread = threading.Thread(
            target=self._drain_unity_responses,
            name="UnityBridgeRouter",
            daemon=True,
        )
        self._router_thread.start()

        # Give subscribers a small window to connect before the first publish.
        time.sleep(0.2)
        print(
            "Unity bridge started "
            f"(PUB {pub_endpoint}, ROUTER {router_endpoint}, "
            f"origin=({self.origin_x:.2f}, {self.origin_y:.2f}))"
        )

    def should_publish(self, step):
        return self.enabled and step % self.update_interval == 0

    def collect_vehicles(self, traci_module):
        vehicles = []

        for vehicle_id in traci_module.vehicle.getIDList():
            try:
                sumo_x, sumo_y = traci_module.vehicle.getPosition(vehicle_id)
                angle = traci_module.vehicle.getAngle(vehicle_id)
                speed = traci_module.vehicle.getSpeed(vehicle_id)
                vehicle_type = traci_module.vehicle.getTypeID(vehicle_id)
            except traci_module.TraCIException:
                continue

            unity_x, _unity_y, unity_z = self.sumo_to_unity_position(sumo_x, sumo_y)
            vehicles.append(
                {
                    "id": vehicle_id,
                    "x": round(unity_x, 3),
                    "y": round(unity_z, 3),
                    "angle": round(angle, 3),
                    "speed": round(speed, 3),
                    "vehicle_type": vehicle_type,
                }
            )

        return vehicles

    def publish_vehicles(self, traci_module):
        if not self.enabled:
            return

        vehicles = self.collect_vehicles(traci_module)
        vehicle_payload = {
            "type": "vehicles",
            "vehicles": vehicles,
            "sumo_vehicle_count": len(vehicles),
            "simulation_time": round(traci_module.simulation.getTime(), 3),
        }
        self._publish(vehicle_payload)
        self._log_stats_if_due(len(vehicles))

    def publish_status(self, sumo_vehicle_count, simulation_time):
        if not self.enabled:
            return

        self._publish(
            {
                "type": "status",
                "sumo_vehicle_count": sumo_vehicle_count,
                "simulation_time": round(simulation_time, 3),
            }
        )

    def publish_status_legacy(self, sumo_vehicle_count, simulation_time):
        if not self.enabled:
            return

        self._publish(
            {
                "type": "status",
                "sumo_vehicle_count": sumo_vehicle_count,
                "simulation_time": round(simulation_time, 3),
            }
        )

    def publish_congestion(self, congestion_latest):
        if not self.enabled:
            return

        junctions = []
        for junction_id, data in congestion_latest.items():
            if isinstance(data, dict):
                score = data.get("score", 0)
            else:
                score = data
            junctions.append({"id": junction_id, "score": score})

        self._publish({"type": "congestion", "junctions": junctions})

    def publish_traffic_lights(self, traci_module):
        if not self.enabled:
            return

        lights = []
        for tls_id in traci_module.trafficlight.getIDList():
            try:
                lights.append(
                    {
                        "id": tls_id,
                        "current_phase": traci_module.trafficlight.getPhase(tls_id),
                        "state": traci_module.trafficlight.getRedYellowGreenState(tls_id),
                    }
                )
            except traci_module.TraCIException:
                continue

        self._publish({"type": "trafficlights", "lights": lights})

    def sumo_to_unity_position(self, sumo_x, sumo_y):
        unity_x = sumo_x - self.origin_x
        unity_y = 0.0
        unity_z = sumo_y - self.origin_y
        return unity_x, unity_y, unity_z

    @staticmethod
    def sumo_to_unity_yaw(sumo_angle):
        return sumo_angle - 90.0

    def close(self):
        self._running = False

        if self._router_thread is not None:
            self._router_thread.join(timeout=1.0)

        if self._publisher is not None:
            self._publisher.close(linger=0)

        if self._router is not None:
            self._router.close(linger=0)

    def _publish(self, payload):
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        self._publisher.send_string(encoded)
        self.messages_published += 1
        self.bytes_published += len(encoded.encode("utf-8"))

    def _log_stats_if_due(self, vehicle_count):
        now = time.monotonic()
        if now - self._last_stats_log < 10:
            return

        average_size = self.bytes_published / max(1, self.messages_published)
        print(
            "Unity bridge stats: "
            f"vehicles={vehicle_count}, "
            f"messages={self.messages_published}, "
            f"avg_message_size={average_size:.0f} bytes"
        )
        self._last_stats_log = now

    def _drain_unity_responses(self):
        poller = zmq.Poller()
        poller.register(self._router, zmq.POLLIN)

        while self._running:
            events = dict(poller.poll(100))
            if self._router not in events:
                continue

            try:
                _frames = self._router.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.Again:
                continue

    @staticmethod
    def _read_conv_boundary_origin(net_file):
        root = ET.parse(net_file).getroot()
        location = root.find("location")
        if location is None:
            return 0.0, 0.0

        conv_boundary = location.attrib.get("convBoundary", "")
        parts = conv_boundary.split(",")
        if len(parts) >= 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                pass

        return 0.0, 0.0

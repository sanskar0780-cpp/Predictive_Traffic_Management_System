"""Junction congestion scoring and history management."""

from collections import defaultdict


class CongestionScoringEngine:
    """Converts live junction measurements into a normalized 0-100 score."""

    def __init__(self):
        self.history = defaultdict(list)
        self.latest = {}

    def calculate_score(self, snapshot):
        # Each component is normalized against a prototype-level saturation
        # point, making the result understandable and easy to tune.
        if (
            snapshot["vehicle_count"] == 0
            and snapshot["halted_vehicles"] == 0
            and snapshot["waiting_time"] == 0
        ):
            return 0.0

        waiting_pressure = min(snapshot["waiting_time"] / 120.0, 1.0)
        halted_pressure = min(snapshot["halted_vehicles"] / 10.0, 1.0)
        vehicle_pressure = min(snapshot["vehicle_count"] / 20.0, 1.0)
        speed_pressure = 1.0 - min(snapshot["average_speed"] / 13.9, 1.0)

        return round(
            100
            * (
                0.35 * waiting_pressure
                + 0.30 * halted_pressure
                + 0.20 * speed_pressure
                + 0.15 * vehicle_pressure
            ),
            2,
        )

    @staticmethod
    def classify(score):
        if score >= 65:
            return "HIGH"
        if score >= 35:
            return "MEDIUM"
        return "LOW"

    def update(self, tls_id, snapshot, simulation_time):
        score = self.calculate_score(snapshot)
        record = {
            "time": simulation_time,
            "score": score,
            "classification": self.classify(score),
            **snapshot,
        }
        self.latest[tls_id] = record
        self.history[tls_id].append(record)
        return record

    def get_scores(self):
        return {
            tls_id: record["score"]
            for tls_id, record in self.latest.items()
        }

    def congested_junction_count(self):
        # Final snapshots are often empty after traffic clears. Count junctions
        # that reached high congestion at any point during the run.
        return sum(
            any(record["classification"] == "HIGH" for record in records)
            for records in self.history.values()
        )

    def estimated_reduction_percent(self):
        """Estimate within-run improvement using active-traffic score windows."""

        early_scores = []
        recent_scores = []

        for records in self.history.values():
            # Ignore empty-junction snapshots at the beginning and end. Including
            # them can falsely report a 100% reduction merely because traffic has
            # finished leaving the simulation.
            active_records = [
                item
                for item in records
                if item["vehicle_count"] > 0
                or item["halted_vehicles"] > 0
                or item["waiting_time"] > 0
            ]

            if len(active_records) < 4:
                continue

            window = min(10, max(2, len(active_records) // 4))
            early_scores.extend(item["score"] for item in active_records[:window])
            recent_scores.extend(item["score"] for item in active_records[-window:])

        if not early_scores or not recent_scores:
            return 0.0

        early_average = sum(early_scores) / len(early_scores)
        recent_average = sum(recent_scores) / len(recent_scores)

        if early_average <= 0:
            return 0.0

        reduction = max(0.0, (early_average - recent_average) / early_average * 100)
        return round(min(50.0, reduction), 2)

    def ranked_junctions(self):
        rankings = []

        for tls_id, records in self.history.items():
            if not records:
                continue

            average_score = sum(item["score"] for item in records) / len(records)
            peak_score = max(item["score"] for item in records)
            rankings.append(
                (
                    tls_id,
                    {
                        "score": round(average_score, 2),
                        "peak_score": round(peak_score, 2),
                        "classification": self.classify(average_score),
                    },
                )
            )

        return sorted(
            rankings,
            key=lambda item: item[1]["score"],
            reverse=True,
        )

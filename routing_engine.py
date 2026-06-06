"""Congestion-aware route quality estimation and recommendation helpers."""


def estimate_route_cost(route_edges, edge_to_tls_lanes, congestion_scores):
    """Estimate route cost from length and congestion at controlled junctions."""

    base_cost = len(route_edges) * 10.0
    congestion_cost = 0.0
    seen_tls = set()

    for edge_id in route_edges:
        for tls_id, _lane_id in edge_to_tls_lanes.get(edge_id, []):
            if tls_id in seen_tls:
                continue
            seen_tls.add(tls_id)
            congestion_cost += congestion_scores.get(tls_id, 0.0)

    return round(base_cost + congestion_cost, 2)


def recommend_route(vehicle_id, current_route, candidate_routes, edge_to_tls_lanes, congestion_scores):
    """Select the lowest-cost candidate and estimate improvement over current."""

    current_cost = estimate_route_cost(
        current_route,
        edge_to_tls_lanes,
        congestion_scores,
    )
    best_route = current_route
    best_cost = current_cost

    for candidate in candidate_routes:
        candidate_cost = estimate_route_cost(
            candidate,
            edge_to_tls_lanes,
            congestion_scores,
        )
        if candidate_cost < best_cost:
            best_route = candidate
            best_cost = candidate_cost

    improvement = 0.0
    if current_cost > 0:
        improvement = (current_cost - best_cost) / current_cost * 100

    return {
        "vehicle_id": vehicle_id,
        "recommended_route": best_route,
        "current_cost": current_cost,
        "recommended_cost": best_cost,
        "estimated_improvement_percent": round(improvement, 2),
    }


class SmartRouteRecommendationEngine:
    """Tracks route recommendations produced from live congestion scores."""

    def __init__(self, edge_to_tls_lanes):
        self.edge_to_tls_lanes = edge_to_tls_lanes
        self.recommendations = []

    def evaluate(self, vehicle_id, current_route, candidate_routes, congestion_scores):
        recommendation = recommend_route(
            vehicle_id,
            current_route,
            candidate_routes,
            self.edge_to_tls_lanes,
            congestion_scores,
        )

        if recommendation["estimated_improvement_percent"] > 0:
            self.recommendations.append(recommendation)
            print(
                f"[SMART ROUTING] {vehicle_id}: estimated route improvement "
                f"{recommendation['estimated_improvement_percent']:.2f}%"
            )

        return recommendation

    def average_improvement(self):
        if not self.recommendations:
            return 0.0
        return round(
            sum(
                item["estimated_improvement_percent"]
                for item in self.recommendations
            )
            / len(self.recommendations),
            2,
        )

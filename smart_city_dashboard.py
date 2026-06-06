"""Final smart-city dashboard and prototype environmental estimates."""


class EnvironmentalImpactEstimator:
    """Converts estimated avoided idling into fuel and CO2 savings."""

    IDLE_FUEL_LITERS_PER_SECOND = 0.00022
    CO2_KG_PER_LITER = 2.31

    def estimate(self, signal_optimizations, emergency_priority_events, congestion_reduction):
        # Prototype estimate: each useful signal action avoids a small amount
        # of idling, adjusted by the observed congestion-score improvement.
        idle_time_reduction = (
            signal_optimizations * 4.5
            + emergency_priority_events * 7.0
        ) * (1.0 + congestion_reduction / 100.0)
        fuel_savings = idle_time_reduction * self.IDLE_FUEL_LITERS_PER_SECOND
        co2_reduction = fuel_savings * self.CO2_KG_PER_LITER

        return {
            "idle_time_reduction_seconds": round(idle_time_reduction, 2),
            "fuel_savings_liters": round(fuel_savings, 3),
            "co2_reduction_kg": round(co2_reduction, 3),
        }


def build_dashboard_metrics(
    signal_metrics,
    congestion_engine,
    emergency_manager,
    rl_layer,
    route_engine,
    signal_optimizations,
    predicted_vehicles_processed,
    congestion_reduction_override=None,
):
    network_waiting_vehicle_seconds = sum(
        item.get("waiting_vehicle_seconds", 0)
        for item in signal_metrics.values()
    )
    network_halted = sum(item["halted_total"] for item in signal_metrics.values())
    network_samples = max(1, sum(item["samples"] for item in signal_metrics.values()))
    network_unique_vehicles = set()
    for item in signal_metrics.values():
        network_unique_vehicles.update(item.get("unique_vehicle_ids", set()))
    network_speed_samples = max(
        1,
        sum(item["speed_samples"] for item in signal_metrics.values()),
    )
    network_speed = sum(item["speed_total"] for item in signal_metrics.values())
    junction_average_waits = [
        item.get("waiting_vehicle_seconds", 0)
        / max(1, len(item.get("unique_vehicle_ids", set())))
        for item in signal_metrics.values()
    ]
    observed_reduction = congestion_engine.estimated_reduction_percent()
    congestion_reduction = observed_reduction

    if congestion_reduction_override is not None:
        congestion_reduction = congestion_reduction_override

    environmental = EnvironmentalImpactEstimator().estimate(
        signal_optimizations,
        emergency_manager.emergency_priority_events,
        congestion_reduction,
    )

    return {
        "average_wait_per_vehicle": (
            network_waiting_vehicle_seconds / max(1, len(network_unique_vehicles))
        ),
        "average_wait_per_junction": (
            sum(junction_average_waits) / max(1, len(junction_average_waits))
        ),
        "average_network_speed": network_speed / network_speed_samples,
        "average_halted_vehicles": network_halted / network_samples,
        "congested_junction_count": congestion_engine.congested_junction_count(),
        "emergency_vehicles_detected": emergency_manager.emergency_vehicles_detected,
        "emergency_vehicles_assisted": emergency_manager.emergency_vehicles_assisted,
        "emergency_priority_events": emergency_manager.emergency_priority_events,
        "signal_optimizations_applied": signal_optimizations,
        "predicted_vehicles_processed": predicted_vehicles_processed,
        "rl_training_samples_generated": rl_layer.sample_count,
        "route_recommendations_generated": len(route_engine.recommendations),
        "average_route_improvement": route_engine.average_improvement(),
        "estimated_congestion_reduction": congestion_reduction,
        **environmental,
    }


def print_smart_city_dashboard(metrics, congestion_engine):
    """Print platform-level results after the existing controller summary."""

    print("\n================ SMART CITY DASHBOARD ================")
    print(f"Average wait per vehicle: {metrics['average_wait_per_vehicle']:.2f} s")
    print(f"Average wait per junction: {metrics['average_wait_per_junction']:.2f} s")
    print(f"Average network speed: {metrics['average_network_speed']:.2f} m/s")
    print(f"Congested junction count: {metrics['congested_junction_count']}")
    print(f"Emergency vehicles detected: {metrics['emergency_vehicles_detected']}")
    print(f"Emergency vehicles assisted: {metrics['emergency_vehicles_assisted']}")
    print(f"Emergency priority events: {metrics['emergency_priority_events']}")
    print(f"Signal optimizations applied: {metrics['signal_optimizations_applied']}")
    print(f"Predicted vehicles processed: {metrics['predicted_vehicles_processed']}")
    print(f"RL training samples generated: {metrics['rl_training_samples_generated']}")
    print(f"Route recommendations generated: {metrics['route_recommendations_generated']}")
    print(f"Average route improvement: {metrics['average_route_improvement']:.2f}%")
    print(
        f"Estimated congestion reduction: "
        f"{metrics['estimated_congestion_reduction']:.2f}%"
    )

    print("\nJunction congestion ranking:")
    for tls_id, record in congestion_engine.ranked_junctions():
        print(
            f"  {tls_id}: average={record['score']:.2f}, "
            f"peak={record['peak_score']:.2f} "
            f"({record['classification']})"
        )

    print("\nEnvironmental impact estimates:")
    print(
        f"  Idle time reduction: "
        f"{metrics['idle_time_reduction_seconds']:.2f} s"
    )
    print(f"  Fuel savings: {metrics['fuel_savings_liters']:.3f} liters")
    print(f"  CO2 reduction: {metrics['co2_reduction_kg']:.3f} kg")
    print("======================================================\n")

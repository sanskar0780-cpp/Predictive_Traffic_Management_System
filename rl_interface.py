"""Prototype integration boundary for a future reinforcement-learning system."""


def get_rl_state(junction_snapshots, congestion_records):
    """Build a serializable state vector from the current traffic snapshot."""

    state = {}

    for tls_id, snapshot in junction_snapshots.items():
        congestion = congestion_records.get(tls_id, {})
        state[tls_id] = {
            "waiting_time": round(snapshot["waiting_time"], 2),
            "halted_vehicles": snapshot["halted_vehicles"],
            "average_speed": round(snapshot["average_speed"], 2),
            "vehicle_count": snapshot["vehicle_count"],
            "congestion_score": congestion.get("score", 0.0),
        }

    return state


def send_state_to_rl(state, simulation_time):
    """Simulate sending a state vector to an external RL training service."""

    print(
        f"[RL INTERFACE] Sent state for {len(state)} junctions "
        f"at t={int(simulation_time)}s"
    )
    return True


def log_rl_training_sample(state, simulation_time, actions):
    """Create one in-memory training sample for future model training."""

    sample = {
        "simulation_time": simulation_time,
        "state": state,
        "actions": list(actions),
        "reward_pending": True,
    }
    print(
        f"[RL TRAINING] Sample generated with {len(actions)} "
        "controller actions"
    )
    return sample


class RLIntegrationLayer:
    """Owns prototype RL exports while keeping ML concerns out of control code."""

    def __init__(self):
        self.latest_state = {}
        self.training_samples = []

    @property
    def sample_count(self):
        return len(self.training_samples)

    def export_state(self, junction_snapshots, congestion_records, simulation_time, actions):
        self.latest_state = get_rl_state(junction_snapshots, congestion_records)
        send_state_to_rl(self.latest_state, simulation_time)
        sample = log_rl_training_sample(self.latest_state, simulation_time, actions)
        self.training_samples.append(sample)
        return self.latest_state

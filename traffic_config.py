"""Configurable operating profiles for the adaptive traffic controller."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ControllerProfile:
    """Runtime tuning values consumed by the existing predictive controller."""

    name: str
    min_vehicles_for_green: int
    prepare_green_before: int
    green_hold_time: int
    max_changes_per_check: int
    high_flow_vehicle_threshold: int
    high_flow_priority_multiplier: float


@dataclass(frozen=True)
class PeakPeriod:
    """A configurable peak period expressed in SUMO simulation seconds."""

    name: str
    start_second: int
    end_second: int
    profile: ControllerProfile


NORMAL_PROFILE = ControllerProfile(
    name="Normal Traffic",
    min_vehicles_for_green=4,
    prepare_green_before=25,
    green_hold_time=30,
    max_changes_per_check=2,
    high_flow_vehicle_threshold=6,
    high_flow_priority_multiplier=1.0,
)

MORNING_OFFICE_PROFILE = ControllerProfile(
    name="Morning Office Traffic",
    min_vehicles_for_green=3,
    prepare_green_before=35,
    green_hold_time=38,
    max_changes_per_check=3,
    high_flow_vehicle_threshold=5,
    high_flow_priority_multiplier=1.35,
)

EVENING_RETURN_PROFILE = ControllerProfile(
    name="Evening Return Traffic",
    min_vehicles_for_green=3,
    prepare_green_before=32,
    green_hold_time=36,
    max_changes_per_check=3,
    high_flow_vehicle_threshold=5,
    high_flow_priority_multiplier=1.30,
)

# Prototype schedule. These windows can later be replaced with clock-time or
# externally supplied smart-city schedules without changing the controller.
DEFAULT_PEAK_PERIODS = (
    PeakPeriod("morning", 200, 450, MORNING_OFFICE_PROFILE),
    PeakPeriod("evening", 650, 900, EVENING_RETURN_PROFILE),
)


class PeakHourManager:
    """Selects controller sensitivity for normal, morning, or evening traffic."""

    VALID_MODES = {"auto", "off", "morning", "evening"}

    def __init__(self, mode="auto", periods=DEFAULT_PEAK_PERIODS):
        if mode not in self.VALID_MODES:
            raise ValueError(f"Unsupported peak mode: {mode}")

        self.mode = mode
        self.periods = periods
        self.last_profile_name = None

    def get_profile(self, simulation_time):
        if self.mode == "off":
            return NORMAL_PROFILE
        if self.mode == "morning":
            return MORNING_OFFICE_PROFILE
        if self.mode == "evening":
            return EVENING_RETURN_PROFILE

        for period in self.periods:
            if period.start_second <= simulation_time < period.end_second:
                return period.profile

        return NORMAL_PROFILE

    def report_profile_change(self, profile):
        """Log mode transitions once instead of on every simulation step."""

        if profile.name == self.last_profile_name:
            return

        self.last_profile_name = profile.name
        print(
            f"\n[PEAK MODE] {profile.name}: threshold="
            f"{profile.min_vehicles_for_green}, lookahead="
            f"{profile.prepare_green_before}s, green hold="
            f"{profile.green_hold_time}s"
        )


def get_peak_mode_from_args(args):
    """Read --peak-mode=<mode> without adding a command-line dependency."""

    for arg in args:
        if arg.startswith("--peak-mode="):
            return arg.split("=", 1)[1].strip().lower()

    return "auto"

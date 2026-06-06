"""
Calculus function.

S(t) = v*t - (v/a)*t²

where:

v = predicted vehicles
a = average arrival time
t = green duration

Differentiating:

dS/dt = v - (2v/a)t

Setting:

dS/dt = 0

gives:

t = a/2
"""


class CalculusTrafficOptimizer:

    def __init__(
        self,
        min_green=5,
        max_green=25,
        cooldown=30,
    ):
        self.min_green = min_green
        self.max_green = max_green
        self.cooldown = cooldown

    def calculate_optimal_green_time(
        self,
        vehicle_count,
        arrival_time,
    ):
        if vehicle_count <= 0:
            return self.min_green

        arrival_time = max(1, arrival_time)

        optimal_time = arrival_time / 2

        optimal_time = int(
            max(
                self.min_green,
                min(
                    self.max_green,
                    optimal_time,
                )
            )
        )

        return optimal_time

    def benefit_function(
        self,
        vehicles,
        arrival_time,
        green_time,
    ):
        arrival_time = max(1, arrival_time)

        return (
            vehicles * green_time
            - (vehicles / arrival_time)
            * (green_time ** 2)
        )

    def choose_best_signal(
        self,
        predictions,
        last_signal_change,
        current_step,
    ):
        """
        predictions format:
        {
            (tls_id, lane_id):
            {
                "vehicles": 10,
                "eta": 15
            }
        }
        """

        best_decision = None

        best_score = float("-inf")

        for (
            tls_id,
            lane_id,
        ), data in predictions.items():

            vehicles = data["vehicles"]

            eta = data["eta"]

            green_time = (
                self.calculate_optimal_green_time(
                    vehicles,
                    eta,
                )
            )

            score = self.benefit_function(
                vehicles,
                eta,
                green_time,
            )

            cooldown_done = (
                current_step
                - last_signal_change[tls_id]
                >= self.cooldown
            )

            if not cooldown_done:
                continue

            if score > best_score:

                best_score = score

                best_decision = {
                    "tls_id": tls_id,
                    "lane_id": lane_id,
                    "green_time": green_time,
                    "vehicles": vehicles,
                    "eta": eta,
                    "score": score,
                }

        return best_decision
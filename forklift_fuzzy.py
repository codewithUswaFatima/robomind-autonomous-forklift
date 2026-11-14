"""
RoboMind - Autonomous Forklift 

Inputs (3):
  obstacle_distance : 0-10 m        (near, medium, far)
  load_weight       : 0-2000 kg     (light, medium, heavy)   <- LoadWeightSensor
  floor_wetness     : 0-100 %       (dry, damp, wet)         <- WetFloor
Output:
  speed             : 0-100 % of max speed (stop, slow, medium, fast)

12 rules, Mamdani inference, centroid defuzzification.

Run:  pip install scikit-fuzzy numpy matplotlib
      python forklift_fuzzy.py          
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")               # save plots to files, no window needed
import matplotlib.pyplot as plt
import skfuzzy as fuzz
from skfuzzy import control as ctrl

# ---------------------------------------------------------------- variables
distance = ctrl.Antecedent(np.arange(0, 10.01, 0.1), "obstacle_distance")
load = ctrl.Antecedent(np.arange(0, 2000.1, 10), "load_weight")
wetness = ctrl.Antecedent(np.arange(0, 100.1, 1), "floor_wetness")
speed = ctrl.Consequent(np.arange(0, 100.1, 1), "speed")

# ---------------------------------------------------------------- membership functions
distance["near"] = fuzz.trimf(distance.universe, [0, 0, 3])
distance["medium"] = fuzz.trimf(distance.universe, [2, 5, 8])
distance["far"] = fuzz.trimf(distance.universe, [6, 10, 10])

load["light"] = fuzz.trimf(load.universe, [0, 0, 800])
load["medium"] = fuzz.trimf(load.universe, [500, 1000, 1500])
load["heavy"] = fuzz.trimf(load.universe, [1200, 2000, 2000])

wetness["dry"] = fuzz.trimf(wetness.universe, [0, 0, 30])
wetness["damp"] = fuzz.trimf(wetness.universe, [20, 50, 80])
wetness["wet"] = fuzz.trimf(wetness.universe, [60, 100, 100])

speed["stop"] = fuzz.trimf(speed.universe, [0, 0, 15])
speed["slow"] = fuzz.trimf(speed.universe, [10, 30, 50])
speed["medium"] = fuzz.trimf(speed.universe, [40, 60, 80])
speed["fast"] = fuzz.trimf(speed.universe, [70, 100, 100])

# ---------------------------------------------------------------- 12 rules
d, l, w, s = distance, load, wetness, speed
rules = [
    ctrl.Rule(d["near"], s["stop"]),                                         # R1
    ctrl.Rule(d["medium"] & l["heavy"] & ~w["wet"], s["slow"]),              # R2
    ctrl.Rule(d["medium"] & w["dry"] & ~l["heavy"], s["medium"]),            # R3
    ctrl.Rule(d["medium"] & w["damp"] & ~l["heavy"], s["medium"]),           # R4
    ctrl.Rule(d["medium"] & w["wet"] & ~l["heavy"], s["slow"]),              # R5
    ctrl.Rule(d["medium"] & l["heavy"] & w["wet"], s["stop"]),               # R6
    ctrl.Rule(d["far"] & l["light"] & w["dry"], s["fast"]),                  # R7
    ctrl.Rule(d["far"] & l["medium"] & w["dry"], s["fast"]),                 # R8
    ctrl.Rule(d["far"] & w["damp"] & ~l["heavy"], s["medium"]),              # R9
    ctrl.Rule(d["far"] & l["heavy"] & ~w["wet"], s["medium"]),               # R10
    ctrl.Rule(d["far"] & w["wet"] & ~l["heavy"], s["slow"]),                 # R11
    ctrl.Rule(d["far"] & l["heavy"] & w["wet"], s["slow"]),                  # R12
]

system = ctrl.ControlSystem(rules)


def compute_speed(dist_m, load_kg, wet_pct):
    """Return recommended speed (% of max) for the given inputs."""
    sim = ctrl.ControlSystemSimulation(system)
    sim.input["obstacle_distance"] = dist_m
    sim.input["load_weight"] = load_kg
    sim.input["floor_wetness"] = wet_pct
    sim.compute()
    return float(sim.output["speed"])


def speed_to_action(value):
    """Map fuzzy speed to the ontology's RecoveryAction names."""
    if value < 15:
        return "Stop"
    if value < 45:
        return "SlowDown"
    return "Continue"


# ---------------------------------------------------------------- scenarios
SCENARIOS = [
    # (name, distance m, load kg, wetness %)
    ("F1 Clear aisle, light load, dry floor", 9, 200, 5),
    ("F2 Clear aisle, medium load, dry floor", 9, 1000, 5),
    ("F3 Obstacle very close", 1, 500, 10),
    ("F4 Medium distance, heavy load, dry", 5, 1800, 10),
    ("F5 Medium distance, heavy load, wet floor", 5, 1800, 95),
    ("F6 Far, heavy load, wet floor", 9, 1800, 95),
    ("F7 Medium distance, light load, damp floor", 5, 300, 50),
    ("F8 Far, light load, wet floor", 9, 300, 90),
]


def save_membership_plots(path="fuzzy_membership.png"):
    fig, axes = plt.subplots(4, 1, figsize=(8, 12))
    for ax, var in zip(axes, [distance, load, wetness, speed]):
        for term in var.terms:
            ax.plot(var.universe, var[term].mf, label=term, linewidth=2)
        ax.set_title(var.label)
        ax.legend()
        ax.set_ylim(0, 1.05)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    print(f"Rules: {len(rules)}")
    print(f"{'Scenario':45s} {'dist':>5s} {'load':>6s} {'wet':>4s} {'speed%':>7s}  action")
    for name, dist_m, load_kg, wet_pct in SCENARIOS:
        v = compute_speed(dist_m, load_kg, wet_pct)
        print(f"{name:45s} {dist_m:5.1f} {load_kg:6.0f} {wet_pct:4.0f} {v:7.1f}  "
              f"{speed_to_action(v)}")
    save_membership_plots()
    print("\nSaved membership function plots to fuzzy_membership.png")

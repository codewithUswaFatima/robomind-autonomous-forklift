"""
RoboMind - Autonomous Forklift 

Nodes (9):
  Root causes : WetFloor, PersonNearby, LowVisibility, SensorFault, LoadHeavy, BatteryLow
  Intermediate: LongBraking       (WetFloor, LoadHeavy)
  Risk nodes  : CollisionRisk     (PersonNearby, LongBraking, SensorFault, LowVisibility)
                MissionFailure    (BatteryLow, SensorFault)

Run:  pip install pgmpy
      python forklift_bayesian.py
"""
import itertools

try:  # newer pgmpy versions
    from pgmpy.models import DiscreteBayesianNetwork as BayesNet
except ImportError:  # older pgmpy versions
    from pgmpy.models import BayesianNetwork as BayesNet
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination

STATES = ["No", "Yes"]          # index 0 = No, index 1 = Yes
STATE_NAMES = {}                # filled per variable below


# ---------------------------------------------------------------- structure
model = BayesNet([
    ("WetFloor", "LongBraking"),
    ("LoadHeavy", "LongBraking"),
    ("PersonNearby", "CollisionRisk"),
    ("LongBraking", "CollisionRisk"),
    ("SensorFault", "CollisionRisk"),
    ("LowVisibility", "CollisionRisk"),
    ("BatteryLow", "MissionFailure"),
    ("SensorFault", "MissionFailure"),
])


# ---------------------------------------------------------------- helpers
def root_cpd(name, p_yes):
    """CPD for a node with no parents."""
    return TabularCPD(name, 2, [[1 - p_yes], [p_yes]],
                      state_names={name: STATES})


def child_cpd(name, parents, p_yes_fn):
    """CPD for a node with binary parents. p_yes_fn takes a tuple of 0/1."""
    combos = list(itertools.product([0, 1], repeat=len(parents)))
    p_yes = [p_yes_fn(c) for c in combos]
    values = [[1 - p for p in p_yes], p_yes]
    state_names = {name: STATES}
    for p in parents:
        state_names[p] = STATES
    return TabularCPD(name, 2, values, evidence=parents,
                      evidence_card=[2] * len(parents),
                      state_names=state_names)


# ---------------------------------------------------------------- CPDs
cpd_wet = root_cpd("WetFloor", 0.20)
cpd_person = root_cpd("PersonNearby", 0.25)
cpd_vis = root_cpd("LowVisibility", 0.15)
cpd_sensor = root_cpd("SensorFault", 0.05)
cpd_heavy = root_cpd("LoadHeavy", 0.40)
cpd_battery = root_cpd("BatteryLow", 0.10)

# LongBraking | WetFloor, LoadHeavy
braking_table = {(0, 0): 0.05, (0, 1): 0.40, (1, 0): 0.50, (1, 1): 0.90}
cpd_braking = child_cpd("LongBraking", ["WetFloor", "LoadHeavy"],
                        lambda c: braking_table[c])


# CollisionRisk | PersonNearby, LongBraking, SensorFault, LowVisibility
def collision_p(c):
    person, braking, sensor, vis = c
    p = 0.01                                   # base risk
    p += 0.35 * person
    p += 0.25 * braking
    p += 0.20 * sensor
    p += 0.10 * vis
    if person and braking:                     # worst combination
        p += 0.15
    return min(p, 0.99)


cpd_collision = child_cpd(
    "CollisionRisk",
    ["PersonNearby", "LongBraking", "SensorFault", "LowVisibility"],
    collision_p)

# MissionFailure | BatteryLow, SensorFault
mission_table = {(0, 0): 0.02, (0, 1): 0.45, (1, 0): 0.60, (1, 1): 0.95}
cpd_mission = child_cpd("MissionFailure", ["BatteryLow", "SensorFault"],
                        lambda c: mission_table[c])

model.add_cpds(cpd_wet, cpd_person, cpd_vis, cpd_sensor, cpd_heavy,
               cpd_battery, cpd_braking, cpd_collision, cpd_mission)
assert model.check_model(), "Model is not valid"

infer = VariableElimination(model)


# ---------------------------------------------------------------- queries
def p_yes(variable, evidence=None):
    result = infer.query([variable], evidence=evidence or {}, show_progress=False)
    return float(result.get_value(**{variable: "Yes"}))


def decide(evidence):
    """Turn probabilities into a recovery action (same names as the ontology)."""
    collision = p_yes("CollisionRisk", evidence)
    mission = p_yes("MissionFailure", evidence)
    if collision >= 0.60:
        action = "Stop"
    elif collision >= 0.35:
        action = "SlowDown"
    elif mission >= 0.50:
        action = "Recharge"
    else:
        action = "Continue"
    return collision, mission, action


SCENARIOS = {
    "S1 Normal operation": {},
    "S2 Person nearby": {"PersonNearby": "Yes"},
    "S3 Wet floor + heavy load": {"WetFloor": "Yes", "LoadHeavy": "Yes"},
    "S4 Person nearby + wet floor + heavy load":
        {"PersonNearby": "Yes", "WetFloor": "Yes", "LoadHeavy": "Yes"},
    "S5 Low battery": {"BatteryLow": "Yes"},
    "S6 Sensor fault": {"SensorFault": "Yes"},
}

if __name__ == "__main__":
    print("Nodes :", sorted(model.nodes()))
    print("Edges :", sorted(model.edges()))

    print("\n--- Prior probabilities (no evidence) ---")
    for v in ["LongBraking", "CollisionRisk", "MissionFailure"]:
        print(f"P({v}=Yes) = {p_yes(v):.3f}")

    print("\n--- Scenarios (evidence -> risk -> action) ---")
    for name, ev in SCENARIOS.items():
        c, m, a = decide(ev)
        print(f"{name:45s} P(Collision)={c:.2f}  P(MissionFail)={m:.2f}  -> {a}")

    print("\n--- Diagnostic (backward) reasoning ---")
    print("Given CollisionRisk=Yes, probability of causes:")
    for cause in ["PersonNearby", "LongBraking", "SensorFault", "LowVisibility"]:
        print(f"  P({cause}=Yes | CollisionRisk=Yes) = "
              f"{p_yes(cause, {'CollisionRisk': 'Yes'}):.3f}")

    print("\n--- Explaining away ---")
    print("P(SensorFault=Yes | MissionFailure=Yes)                  = "
          f"{p_yes('SensorFault', {'MissionFailure': 'Yes'}):.3f}")
    print("P(SensorFault=Yes | MissionFailure=Yes, BatteryLow=Yes)  = "
          f"{p_yes('SensorFault', {'MissionFailure': 'Yes', 'BatteryLow': 'Yes'}):.3f}")

    print("\n--- CPT: CollisionRisk ---")
    print(cpd_collision)

"""
RoboMind - Autonomous Forklift


  Step 2  forklift.owl            -> rdflib + SPARQL   (components / location of the forklift)
  Step 4  forklift_bayesian.py    -> P(CollisionRisk), P(MissionFailure) -> action
  Step 5  forklift_fuzzy.py       -> speed % (3 inputs, 12 rules)        -> action
  Step 3+7 forklift.pl + forklift_nonmonotonic.pl (swipl)               -> action
  FUSION  most urgent action wins (+ non-monotonic barrier override)
  Step 6  pddl/domain.pddl + generated problem -> pyperplan -> mission plan

Run:  python forklift_integration.py
Needs: pip install rdflib pgmpy scikit-fuzzy pyperplan matplotlib 
"""
import os, re, subprocess, sys, tempfile, warnings
from dataclasses import dataclass, field

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rdflib
import forklift_bayesian as bayes        # Step 4
import forklift_fuzzy as fuzzy           # Step 5

SWIPL = os.environ.get("SWIPL", "swipl")
PL_FILE = os.path.join(HERE, "pl", "forklift_nonmonotonic.pl").replace("\\","/")
DOMAIN = os.path.join(HERE, "pddl", "domain.pddl")
OWL = os.path.join(HERE, "forklift.owl")
F = "forklift_01"

# ============================================================== scenario / state
@dataclass
class Scenario:
    name: str
    # raw sensor readings
    distance_m: float = 9.0
    load_kg: float = 200.0
    wetness_pct: float = 5.0
    battery_pct: float = 90.0
    loc: str = "aisle_a"            # aisle_a | aisle_b2 | charging_station_01
    person: bool = False
    blocked: bool = False
    unstable: bool = False
    sensor_faulty: bool = False
    barrier: bool = False
    # expected result
    expect_decision: str = "continue"
    expect_has: tuple = ()          # PDDL action names that must appear in the plan
    expect_first: str = ""          # first PDDL action name ("" = don't check)

@dataclass
class State:
    sc: Scenario
    components: list = field(default_factory=list)
    votes: dict = field(default_factory=dict)       # source -> action
    p_collision: float = 0.0
    p_mission: float = 0.0
    fuzzy_speed: float = 0.0
    prolog: dict = field(default_factory=dict)
    decision: str = ""
    decided_by: str = ""
    speed: float = 0.0
    plan: list = field(default_factory=list)
    trace: list = field(default_factory=list)

# ============================================================== Step 2: KG (SPARQL)
_GRAPH = rdflib.Graph()
_GRAPH.parse(OWL)
Q_COMPONENTS = """PREFIX : <http://example.org/forklift#>
SELECT ?t WHERE { :Forklift_01 :hasComponent ?c . ?c a ?t .
  FILTER(?t != <http://www.w3.org/2002/07/owl#NamedIndividual>) }"""

def step_kg(s: State) -> State:
    s.components = sorted(str(r[0]).split("#")[1] for r in _GRAPH.query(Q_COMPONENTS))
    s.trace.append(f"KG: forklift_01 components = {s.components}")
    return s

# ============================================================== Step 4: Bayesian
def to_bayes_evidence(sc: Scenario, components: list) -> dict:
    ev = {"BatteryLow": "Yes" if sc.battery_pct < 20 else "No",
          "PersonNearby": "Yes" if sc.person else "No",
          "WetFloor": "Yes" if sc.wetness_pct >= 60 else "No",
          "LoadHeavy": "Yes" if sc.load_kg >= 1200 else "No"}
    # a sensor fault only matters if the KG says the forklift actually has a sensor
    has_sensor = any("Sensor" in c for c in components)
    ev["SensorFault"] = "Yes" if (sc.sensor_faulty and has_sensor) else "No"
    return ev

NAME = {"Stop": "stop", "SlowDown": "slow_down", "Recharge": "recharge", "Continue": "continue"}

def step_bayes(s: State) -> State:
    s.p_collision, s.p_mission, act = bayes.decide(to_bayes_evidence(s.sc, s.components))
    s.votes["bayes"] = NAME[act]
    s.trace.append(f"Bayes: P(collision)={s.p_collision:.2f} P(mission fail)={s.p_mission:.2f} -> {act}")
    return s

# ============================================================== Step 5: Fuzzy
def step_fuzzy(s: State) -> State:
    s.fuzzy_speed = round(fuzzy.compute_speed(s.sc.distance_m, s.sc.load_kg, s.sc.wetness_pct), 1)
    s.votes["fuzzy"] = NAME[fuzzy.speed_to_action(s.fuzzy_speed)]
    s.trace.append(f"Fuzzy: speed={s.fuzzy_speed}% -> {s.votes['fuzzy']}")
    return s

# ============================================================== Step 3 + 7: Prolog via swipl
def prolog_query(sc: Scenario) -> dict:
    setup = [
        "retractall(hazard_at(_,_))", "retractall(has_fault(_,_))",
        "retractall(floor_condition(_,_))", "retractall(sensor_status(_,_))",
        "retractall(battery_level(battery_01,_))", "retractall(barrier_at(_))",
        f"retractall(located_in({F},_))", f"retractall(carries({F},_))",
        f"assertz(located_in({F},{sc.loc}))",
        f"assertz(carries({F},{'heavy_load_01' if sc.load_kg >= 1200 else 'pallet_01'}))",
        f"assertz(battery_level(battery_01,{sc.battery_pct}))",
        f"assertz(sensor_status(lidar_sensor_01,{'faulty' if sc.sensor_faulty else 'ok'}))",
    ]
    if sc.person:   setup.append(f"assertz(hazard_at(person_in_path_01,{sc.loc}))")
    if sc.blocked:  setup.append(f"assertz(hazard_at(blocked_aisle_01,{sc.loc}))")
    if sc.unstable: setup.append(f"assertz(hazard_at(unstable_load_01,{sc.loc}))")
    if sc.wetness_pct >= 60: setup.append(f"assertz(floor_condition({sc.loc},wet_floor_01))")
    if sc.barrier:  setup.append(f"assertz(barrier_at({sc.loc}))")
    goal = f"""
main :-
    {', '.join(setup)},
    F = {F},
    risk_level(F, R), !,
    best_action(F, B),
    findall(A, nm_action(F, A), NM),
    truth(sensor_fault_detected(F), SF),
    format("RESULT|~w|~w|~w|~w~n", [R, B, NM, SF]).
"""
    with tempfile.NamedTemporaryFile("w", suffix=".pl", delete=False) as f:
        f.write(f":- consult('{PL_FILE}').\n" + goal)
        path = f.name
    try:
        out = subprocess.run([SWIPL, "-q", "-g", "main", "-t", "halt", path],
                             capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(path)
    m = re.search(r"RESULT\|(\w+)\|(\w+)\|\[(.*?)\]\|(\w+)", out.stdout)
    if not m:
        raise RuntimeError(f"Prolog failed:\n{out.stdout}\n{out.stderr}")
    risk, best, nm, sf = m.groups()
    return {"risk": risk, "best": best, "nm": [a for a in nm.split(",") if a], "sensor_fault": sf == "true"}

def step_prolog(s: State) -> State:
    s.prolog = prolog_query(s.sc)
    vote = s.prolog["best"]
    # Non-monotonic exception-to-exception: a safety barrier downgrades 'stop' for a person to
    # 'slow_down' (nm_action) - but never when the sensors themselves are faulty.
    if vote == "stop" and s.prolog["nm"] == ["slow_down"] and not s.prolog["sensor_fault"]:
        vote = "slow_down"
        s.trace.append("Prolog NM override: barrier present -> stop downgraded to slow_down")
    s.votes["prolog"] = vote
    s.trace.append(f"Prolog: risk={s.prolog['risk']} best={s.prolog['best']} nm={s.prolog['nm']} -> {vote}")
    return s

# ============================================================== FUSION (the hard part)
URGENCY = ["stop", "reroute", "slow_down", "recharge", "continue"]     # same order as action_priority/2
CAP = {"stop": 0.0, "reroute": 40.0, "slow_down": 25.0, "recharge": 40.0, "continue": 100.0}

def step_fuse(s: State) -> State:
    """Most urgent vote wins (safety-first). Speed = min(fuzzy speed, cap of the chosen action)."""
    s.decided_by, s.decision = min(s.votes.items(), key=lambda kv: URGENCY.index(kv[1]))
    s.speed = min(s.fuzzy_speed, CAP[s.decision])
    s.trace.append(f"FUSION: votes={s.votes} -> {s.decision} (by {s.decided_by}), speed={s.speed}")
    return s

# ============================================================== Step 6: PDDL via pyperplan
LEVELS = 10      # 1 battery level ~ 10 %, 1 move costs 1 level (domain.pddl is generic over levels)

def make_problem(sc: Scenario, blocked_zone: bool) -> str:
    lv = min(LEVELS - 1, int(sc.battery_pct / 10 + 0.5))
    levels = " ".join(f"l{i}" for i in range(LEVELS))
    decs = " ".join(f"(dec l{i+1} l{i})" for i in range(LEVELS - 1))
    clear = "(clear charging_station_01) (clear aisle_a) (clear aisle_b2) (clear intersection_01) (clear loading_dock_01)"
    if not blocked_zone:
        clear += " (clear aisle_c)"
    return f"""(define (problem forklift-mission)
  (:domain autonomous-forklift)
  (:objects forklift_01 - forklift  pallet_01 - pallet
    charging_station_01 aisle_a aisle_b2 aisle_c intersection_01 loading_dock_01 - zone
    {levels} - level)
  (:init
    (connected charging_station_01 intersection_01) (connected intersection_01 charging_station_01)
    (connected aisle_a intersection_01) (connected intersection_01 aisle_a)
    (connected aisle_b2 intersection_01) (connected intersection_01 aisle_b2)
    (connected loading_dock_01 intersection_01) (connected intersection_01 loading_dock_01)
    (connected aisle_a aisle_c) (connected aisle_c aisle_a)
    (connected aisle_c loading_dock_01) (connected loading_dock_01 aisle_c)
    {clear}
    (charging-station charging_station_01)
    {decs} (full l{LEVELS-1})
    (at forklift_01 {sc.loc}) (empty forklift_01) (battery-at forklift_01 l{lv})
    (pallet-at pallet_01 aisle_b2))
  (:goal (and (pallet-at pallet_01 loading_dock_01) (empty forklift_01))))
"""

def pyperplan_plan(sc: Scenario, blocked_zone: bool) -> list:
    with tempfile.TemporaryDirectory() as d:
        prob = os.path.join(d, "problem.pddl")
        open(prob, "w").write(make_problem(sc, blocked_zone))
        subprocess.run([sys.executable, "-m", "pyperplan", "-s", "astar", "-H", "hff", DOMAIN, prob],
                       capture_output=True, text=True, timeout=120)
        soln = prob + ".soln"
        if not os.path.exists(soln):
            return []                               # unsolvable, e.g. battery too low to reach the charger
        return [l.strip().strip("()") for l in open(soln) if l.strip()]

def step_pddl(s: State) -> State:
    if s.decision == "stop":
        s.plan = ["emergency-stop"]                 # no mission planning while stopped
    else:
        plan = pyperplan_plan(s.sc, blocked_zone=s.sc.blocked)
        s.plan = plan or ["NO-PLAN (stranded) -> request-assistance"]
    s.trace.append(f"PDDL: {len(s.plan)} steps, first = {s.plan[0] if s.plan else None}")
    return s

PIPELINE = [step_kg, step_bayes, step_fuzzy, step_prolog, step_fuse, step_pddl]

def run(sc: Scenario) -> State:
    s = State(sc)
    for step in PIPELINE:
        s = step(s)
    return s

# ============================================================== 10 test scenarios
SCENARIOS = [
    Scenario("1 Normal operation",
             expect_decision="continue", expect_has=("pick", "drop")),
    Scenario("2 Low battery 15%", battery_pct=15,
             expect_decision="recharge", expect_has=("charge", "pick", "drop")),
    Scenario("3 Person in path", distance_m=6, person=True,
             expect_decision="stop", expect_first="emergency-stop"),
    Scenario("4 Person + safety barrier (NM exception)", distance_m=6, person=True, barrier=True,
             expect_decision="slow_down", expect_has=("pick", "drop")),
    Scenario("5 Blocked aisle", blocked=True,
             expect_decision="reroute", expect_has=("pick", "drop")),
    Scenario("6 Wet floor + heavy load", load_kg=1800, wetness_pct=95,
             expect_decision="slow_down", expect_has=("pick", "drop")),
    Scenario("7 Lidar sensor faulty", sensor_faulty=True,
             expect_decision="stop", expect_first="emergency-stop"),
    Scenario("8 Unstable load (only Prolog knows)", unstable=True,
             expect_decision="slow_down", expect_has=("pick", "drop")),
    Scenario("9 Low battery + person (stop beats recharge)", battery_pct=12, distance_m=6, person=True,
             expect_decision="stop", expect_first="emergency-stop"),
    Scenario("10 Low battery at charging station", battery_pct=12, loc="charging_station_01",
             expect_decision="recharge", expect_first="charge"),
]

def check(sc: Scenario, s: State) -> bool:
    names = [p.split()[0] for p in s.plan]
    ok = s.decision == sc.expect_decision
    ok &= all(a in names for a in sc.expect_has)
    ok &= (not sc.expect_first) or names[0] == sc.expect_first
    return ok

def main():
    passed = 0
    for sc in SCENARIOS:
        s = run(sc)
        ok = check(sc, s)
        passed += ok
        names = [p.split()[0] for p in s.plan]
        print(f"[{'PASS' if ok else 'FAIL'}] {sc.name}")
        print(f"       votes={s.votes} -> {s.decision} (by {s.decided_by}) speed={s.speed}%")
        print(f"       plan({len(s.plan)}): {' > '.join(names)}")
        if not ok:
            print("       expected:", sc.expect_decision, sc.expect_has, sc.expect_first)
            print("       trace:", *s.trace, sep="\n         ")
    print(f"\n{passed}/{len(SCENARIOS)} passed")

if __name__ == "__main__":
    main()

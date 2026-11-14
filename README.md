# Autonomous Forklift - Knowledge Representation & Reasoning (KRR) Lab Project

An autonomous warehouse forklift that decides what to do (continue, slow down, reroute,
recharge, stop) by combining five KRR techniques in one pipeline.

## Project steps

| Step | Technique | File |
|------|-----------|------|
| 2 | Knowledge graph (OWL) + 6 SPARQL queries | `ontology/forklift.owl` |
| 3 | Prolog rules (38) + why/how explanation | `prolog/forklift.pl` |
| 4 | Bayesian network (9 nodes) | `bayesian/forklift_bayesian.py` |
| 5 | Fuzzy controller (3 inputs, 12 rules) | `fuzzy/forklift_fuzzy.py` |
| 6 | PDDL mission planning | `pddl/domain.pddl`, `pddl/problem.pddl` |
| 7 | Non-monotonic reasoning (defaults, exceptions) | `prolog/forklift_nonmonotonic.pl` |
| 8 | Integration + 10 test scenarios | `forklift_integration.py` |

## How the integration works

```
Scenario (sensor readings)
   -> KG (rdflib + SPARQL)        forklift components
   -> Bayesian network            P(collision), P(mission failure) -> action
   -> Fuzzy controller            speed % -> action
   -> Prolog (swipl)              rule-based action, non-monotonic override
   -> FUSION                      most urgent action wins
   -> PDDL (pyperplan)            mission plan
```

**Fusion rule:** the most urgent vote wins (`stop > reroute > slow_down > recharge > continue`).
Final speed = `min(fuzzy speed, cap of the chosen action)`.

**Non-monotonic exception:** a safety barrier downgrades `stop` (person in path) to `slow_down`,
but never when the sensors themselves are faulty.

## Requirements

- Python 3.10+
- [SWI-Prolog](https://www.swi-prolog.org/Download.html) - `swipl` must be in PATH
  (on Windows tick "Add swipl to the system PATH" during install),
  or set the `SWIPL` environment variable to the full path of `swipl`.

```bash
pip install -r requirements.txt
```

## Run

```bash
python forklift_integration.py
```

Expected: all 10 scenarios `[PASS]` and `10/10 passed`.

## The 10 test scenarios

| # | Scenario | Final decision |
|---|----------|----------------|
| 1 | Normal operation | continue |
| 2 | Low battery 15% | recharge (plan includes `charge`) |
| 3 | Person in path | stop |
| 4 | Person + safety barrier | slow_down (non-monotonic exception) |
| 5 | Blocked aisle | reroute |
| 6 | Wet floor + heavy load | slow_down |
| 7 | Lidar sensor faulty | stop |
| 8 | Unstable load (only Prolog knows) | slow_down |
| 9 | Low battery + person | stop (stop beats recharge) |
| 10 | Low battery at charging station | recharge (plan starts with `charge`) |

## Individual modules

```bash
python bayesian/forklift_bayesian.py      # Step 4 demo
python fuzzy/forklift_fuzzy.py         # Step 5 demo (saves fuzzy_membership.png)
cd prolog && swipl -s forklift.pl    # then:  ?- demo.
cd prolog && swipl -s forklift_nonmonotonic.pl   # then:  ?- demo_nm.
pyperplan pddl/domain.pddl pddl/problem.pddl # Step 6 plan
```

## Folder structure

```
robomind-autonomous-forklift/
├── README.md
├── requirements.txt
├── forklift_integration.py
├── bayesian/
│   └── forklift_bayesian.py
├── fuzzy/
│   └── forklift_fuzzy.py
├── ontology/
│   └── forklift.owl
├── prolog/
│   ├── forklift.pl
│   └── forklift_nonmonotonic.pl
└── pddl/
    ├── domain.pddl
    ├── problem.pddl
    └── plan_pyperplan.txt
```

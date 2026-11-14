%% =====================================================================
%%  RoboMind - Autonomous Forklift | Step 7: Non-monotonic reasoning
%%  Needs forklift.pl in the SAME folder.
%%  Run:  swipl -s forklift_nonmonotonic.pl
%%        ?- demo_nm.
%%
%%  Non-monotonic = conclusions can be WITHDRAWN when new evidence arrives.
%%  (Classical logic and OWL are monotonic: adding facts never removes
%%   conclusions. Prolog's negation as failure (\+) lets us model
%%   "assume X unless there is evidence against it".)
%% =====================================================================

:- ensure_loaded('forklift.pl').
:- dynamic barrier_at/1.

%% ---------------------------------------------------------------------
%% PART 1: DEFAULT RULES ("normally ... unless ...")
%% ---------------------------------------------------------------------

% D1: A forklift is normally operational unless it is abnormal.
normally_operational(F) :- autonomous_forklift(F), \+ abnormal(F).
abnormal(F) :- forklift_with_fault(F).
abnormal(F) :- sensor_fault_detected(F).

% D2: An aisle is assumed passable unless a blockage has been reported.
passable(Z) :- instance_of(Z, aisle), \+ blocked(Z).
blocked(Z) :- hazard_at(H, Z), instance_of(H, blocked_aisle).

% D3: A sensor is assumed healthy unless reported faulty.
sensor_healthy(S) :- instance_of(S, sensor), \+ sensor_status(S, faulty).

% D4: A floor is assumed dry unless wetness has been observed.
assumed_dry(Z) :- instance_of(Z, zone), \+ floor_condition(Z, _).

% D5: A forklift is assumed to have enough battery unless low battery is known.
battery_ok(F) :- autonomous_forklift(F), \+ low_battery_detected(F).

%% ---------------------------------------------------------------------
%% PART 2: EXCEPTIONS and EXCEPTIONS TO EXCEPTIONS
%% ---------------------------------------------------------------------

% Default: a forklift may proceed at normal speed.
% Exception 1: if a person is in its path, it must stop.
% Exception to exception: if a safety barrier is present, it only slows down.
barrier_here(F) :- located_in(F, Z), barrier_at(Z).

nm_action(F, stop)      :- person_in_path(F), \+ barrier_here(F).
nm_action(F, slow_down) :- person_in_path(F), barrier_here(F).
nm_action(F, proceed)   :- normally_operational(F), \+ person_in_path(F).
nm_action(F, hold)      :- autonomous_forklift(F), abnormal(F), \+ person_in_path(F).

% Mission default: ready unless something abnormal is known.
nm_mission_ready(F) :-
    normally_operational(F), battery_ok(F), \+ person_in_path(F).

%% ---------------------------------------------------------------------
%% PART 3: BELIEF REVISION (adding and retracting evidence)
%% ---------------------------------------------------------------------

% Observe new evidence: adds the fact if not already known.
observe(Fact) :- ( call(Fact) -> true ; assertz(Fact) ),
                 format("  [observed] ~w~n", [Fact]).
% Withdraw evidence.
forget(Fact)  :- ( retract(Fact) -> true ; true ),
                 format("  [retracted] ~w~n", [Fact]).

%% ---------------------------------------------------------------------
%% PART 4: DEMO - shows conclusions appearing and disappearing
%% ---------------------------------------------------------------------

truth(G, true)  :- call(G), !.
truth(_, false).

show_beliefs(F) :-
    truth(normally_operational(F), Op),
    truth(battery_ok(F), Bat),
    truth(nm_mission_ready(F), Ready),
    findall(A, nm_action(F, A), As),
    format("  ~w: operational=~w, battery_ok=~w, mission_ready=~w, action=~w~n",
           [F, Op, Bat, Ready, As]).

demo_nm :-
    format("~n=== NM1: Default conclusions (no evidence against them) ===~n"),
    show_beliefs(forklift_02),

    format("~n=== NM2: New evidence arrives -> conclusions are WITHDRAWN ===~n"),
    observe(is_a(sensor_fault_02, sensor_fault)),
    observe(has_fault(forklift_02, sensor_fault_02)),
    show_beliefs(forklift_02),
    how(abnormal(forklift_02)),

    format("~n=== NM3: Evidence removed -> conclusions are RESTORED ===~n"),
    forget(has_fault(forklift_02, sensor_fault_02)),
    forget(is_a(sensor_fault_02, sensor_fault)),
    show_beliefs(forklift_02),

    format("~n=== NM4: Aisle assumed passable until blockage is reported ===~n"),
    forall(member(Z, [aisle_a, aisle_b2]),
           ( truth(passable(Z), P), format("  passable(~w) = ~w~n", [Z, P]) )),
    format("  -- blockage cleared --~n"),
    forget(hazard_at(blocked_aisle_01, aisle_b2)),
    truth(passable(aisle_b2), P2), format("  passable(aisle_b2) = ~w~n", [P2]),
    observe(hazard_at(blocked_aisle_01, aisle_b2)),

    format("~n=== NM5: Exception to an exception (safety barrier) ===~n"),
    show_beliefs(forklift_01),
    format("  -- safety barrier installed in aisle_a --~n"),
    observe(barrier_at(aisle_a)),
    findall(A, nm_action(forklift_01, A), As2),
    format("  forklift_01 action with barrier: ~w~n", [As2]),
    forget(barrier_at(aisle_a)),

    format("~n=== NM6: Sensor assumed healthy until reported faulty ===~n"),
    truth(sensor_healthy(lidar_sensor_01), H1),
    format("  sensor_healthy(lidar_sensor_01) = ~w~n", [H1]),
    forget(sensor_status(lidar_sensor_01, ok)),
    observe(sensor_status(lidar_sensor_01, faulty)),
    truth(sensor_healthy(lidar_sensor_01), H2),
    format("  after fault report: sensor_healthy(lidar_sensor_01) = ~w~n", [H2]),
    forget(sensor_status(lidar_sensor_01, faulty)),
    observe(sensor_status(lidar_sensor_01, ok)),
    format("~nDone. All facts restored to the original state.~n").

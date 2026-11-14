%% =====================================================================
%%  RoboMind - Autonomous Forklift  |  Step 3: Prolog rules + why/how
%%  Run:  swipl -s forklift.pl
%%        ?- demo.
%% =====================================================================

:- dynamic is_a/2, located_in/2, carries/2, has_fault/2, has_component/2,
           performs/2, hazard_at/2, floor_condition/2, battery_level/2,
           sensor_status/2, autonomous_forklift/1.

%% ---------------------------------------------------------------------
%% PART 1: FACTS (taken from the Protege ontology forklift.owl)
%% ---------------------------------------------------------------------

% Class hierarchy: sub(Child, Parent)
sub(autonomous_forklift, robot).
sub(lidar_sensor, sensor).      sub(camera_sensor, sensor).
sub(load_weight_sensor, sensor). sub(tilt_sensor, sensor).
sub(fork, actuator).  sub(mast, actuator).
sub(drive_motor, actuator). sub(brake, actuator).
sub(sensor, component). sub(actuator, component). sub(battery, component).
sub(aisle, zone). sub(intersection, zone). sub(loading_dock, zone).
sub(charging_station, zone). sub(narrow_doorway, zone).
sub(wet_floor, floor_condition).
sub(pallet, load). sub(fragile_load, load). sub(heavy_load, load).
sub(worker, person). sub(supervisor, person).
sub(manual_forklift, other_vehicle).
sub(pick_task, task). sub(transport_task, task). sub(charge_task, task).
sub(person_in_path, hazard). sub(blocked_aisle, hazard). sub(unstable_load, hazard).
sub(sensor_fault, fault). sub(low_battery, fault).
sub(stop, recovery_action). sub(slow_down, recovery_action).
sub(reroute, recovery_action). sub(recharge, recovery_action).

% Individuals: is_a(Individual, Class)
is_a(forklift_01, autonomous_forklift).
is_a(forklift_02, autonomous_forklift).
is_a(aisle_a, aisle).
is_a(aisle_b2, aisle).
is_a(charging_station_01, charging_station).
is_a(battery_01, battery).
is_a(battery_02, battery).             % extra (not in OWL) for comparison
is_a(lidar_sensor_01, lidar_sensor).
is_a(heavy_load_01, heavy_load).
is_a(pallet_01, pallet).
is_a(low_battery_01, low_battery).
is_a(person_in_path_01, person_in_path).
is_a(blocked_aisle_01, blocked_aisle).
is_a(unstable_load_01, unstable_load).
is_a(worker_01, worker).
is_a(manual_forklift_01, manual_forklift).
is_a(wet_floor_01, wet_floor).
is_a(pick_task_01, pick_task).
is_a(charge_task_01, charge_task).

% Forklift facts (object property assertions)
autonomous_forklift(forklift_01).
autonomous_forklift(forklift_02).
located_in(forklift_01, aisle_a).
located_in(forklift_02, charging_station_01).
carries(forklift_01, heavy_load_01).
carries(forklift_02, pallet_01).
has_fault(forklift_01, low_battery_01).
has_component(forklift_01, battery_01).
has_component(forklift_01, lidar_sensor_01).
has_component(forklift_02, battery_02).
performs(forklift_01, pick_task_01).
performs(forklift_02, charge_task_01).

% Extra scenario facts (not in the OWL file, needed for reasoning)
hazard_at(person_in_path_01, aisle_a).
hazard_at(unstable_load_01, aisle_a).
hazard_at(blocked_aisle_01, aisle_b2).
floor_condition(aisle_a, wet_floor_01).
battery_level(battery_01, 15).
battery_level(battery_02, 85).
sensor_status(lidar_sensor_01, ok).      % change to 'faulty' to test

% Priority of recovery actions (1 = most urgent)
action_priority(stop, 1).
action_priority(reroute, 2).
action_priority(slow_down, 3).
action_priority(recharge, 4).

% Plain-language reason for each action (used by why/2)
action_reason(stop, 'stopping avoids a collision or an unsafe operation').
action_reason(reroute, 'the planned path is blocked, so another route is needed').
action_reason(slow_down, 'reduced speed keeps the load and people safe').
action_reason(recharge, 'the battery is too low to finish the mission').

%% ---------------------------------------------------------------------
%% PART 2: RULES (38 rules)
%% ---------------------------------------------------------------------

% --- R1-R4: class hierarchy reasoning ---
instance_of(X, C) :- is_a(X, C).                              % R1
instance_of(X, C) :- is_a(X, C0), subclass_of(C0, C).         % R2
subclass_of(A, B) :- sub(A, B).                               % R3
subclass_of(A, C) :- sub(A, B), subclass_of(B, C).            % R4

% --- R5-R10: defined classes from Protege ---
forklift_in_aisle(F) :-                                       % R5
    autonomous_forklift(F), located_in(F, Z), instance_of(Z, aisle).
forklift_with_fault(F) :-                                     % R6
    autonomous_forklift(F), has_fault(F, Fa), instance_of(Fa, fault).
forklift_needing_recharge(F) :-                               % R7
    autonomous_forklift(F), has_fault(F, Fa), instance_of(Fa, low_battery).
heavy_load_carrier(F) :-                                      % R8
    autonomous_forklift(F), carries(F, L), instance_of(L, heavy_load).
fragile_load_carrier(F) :-                                    % R9
    autonomous_forklift(F), carries(F, L), instance_of(L, fragile_load).
forklift_at_charging_station(F) :-                            % R10
    autonomous_forklift(F), located_in(F, Z), instance_of(Z, charging_station).

% --- R11-R14: fault detection ---
low_battery_reading(F) :-                                     % R11
    has_component(F, B), instance_of(B, battery),
    battery_level(B, Level), Level < 20.
low_battery_detected(F) :- forklift_needing_recharge(F).      % R12
low_battery_detected(F) :- low_battery_reading(F).            % R13
sensor_fault_detected(F) :-                                   % R14
    has_component(F, S), instance_of(S, sensor), sensor_status(S, faulty).

% --- R15-R19: hazard and environment detection ---
hazard_in_zone(F, H) :-                                       % R15
    autonomous_forklift(F), located_in(F, Z), hazard_at(H, Z).
person_in_path(F) :-                                          % R16
    hazard_in_zone(F, H), instance_of(H, person_in_path).
blocked_aisle_ahead(F) :-                                     % R17
    hazard_in_zone(F, H), instance_of(H, blocked_aisle).
unstable_load_risk(F) :-                                      % R18
    hazard_in_zone(F, H), instance_of(H, unstable_load).
wet_zone(F) :-                                                % R19
    located_in(F, Z), floor_condition(Z, W), instance_of(W, wet_floor).

% --- R20-R27: recovery action recommendation ---
recommended_action(F, stop) :- person_in_path(F).             % R20
recommended_action(F, reroute) :- blocked_aisle_ahead(F).     % R21
recommended_action(F, slow_down) :- unstable_load_risk(F).    % R22
recommended_action(F, slow_down) :-                           % R23
    wet_zone(F), heavy_load_carrier(F).
recommended_action(F, slow_down) :-                           % R24
    wet_zone(F), fragile_load_carrier(F).
recommended_action(F, recharge) :-                            % R25
    forklift_needing_recharge(F).
recommended_action(F, recharge) :- low_battery_reading(F).    % R26
recommended_action(F, stop) :- sensor_fault_detected(F).      % R27

% --- R28-R33: risk level ---
high_risk(F) :- person_in_path(F).                            % R28
high_risk(F) :- sensor_fault_detected(F).                     % R29
medium_risk(F) :-                                             % R30
    (   unstable_load_risk(F)
    ;   wet_zone(F), heavy_load_carrier(F)
    ;   low_battery_detected(F)
    ).
risk_level(F, high) :-                                        % R31
    autonomous_forklift(F), high_risk(F).
risk_level(F, medium) :-                                      % R32
    autonomous_forklift(F), medium_risk(F), \+ high_risk(F).
risk_level(F, low) :-                                         % R33
    autonomous_forklift(F), \+ high_risk(F), \+ medium_risk(F).

% --- R34: choose the most urgent action ---
best_action(F, Action) :-                                     % R34
    autonomous_forklift(F),
    findall(P-A, (recommended_action(F, A), action_priority(A, P)), L0),
    sort(L0, L),
    (   L = [_-Best|_] -> Action = Best ; Action = continue ).

% --- R35-R38: mission rules (negation as failure; used later in Step 7) ---
needs_charging_mission(F) :-                                  % R35
    forklift_needing_recharge(F), \+ forklift_at_charging_station(F).
can_navigate(F) :-                                            % R36
    autonomous_forklift(F), \+ blocked_aisle_ahead(F), \+ person_in_path(F).
safe_forklift(F) :-                                           % R37
    autonomous_forklift(F), \+ forklift_with_fault(F).
mission_ready(F) :-                                           % R38
    safe_forklift(F), can_navigate(F), \+ forklift_needing_recharge(F).

%% ---------------------------------------------------------------------
%% PART 3: EXPLANATION - meta-interpreter that builds a proof tree
%% ---------------------------------------------------------------------

prove(true, true) :- !.
prove((A, B), (PA, PB)) :- !, prove(A, PA), prove(B, PB).
prove((A ; B), P) :- !, ( prove(A, P) ; prove(B, P) ).
prove(\+ G, not(G)) :- !, \+ prove(G, _).
prove(G, builtin(G)) :- predicate_property(G, built_in), !, call(G).
prove(G, fact(G)) :- clause(G, true).
prove(G, rule(G, P)) :- clause(G, Body), Body \== true, prove(Body, P).

% HOW: shows the full chain of reasoning
how(Goal) :-
    (   prove(Goal, Proof)
    ->  format("~nHOW: ~w is TRUE because:~n", [Goal]),
        print_proof(Proof, 1)
    ;   format("~nHOW: ~w cannot be proved.~n", [Goal])
    ).

print_proof(true, _) :- !.
print_proof((A, B), D) :- !, print_proof(A, D), print_proof(B, D).
print_proof(fact(G), D) :- !, indent(D), format("~w   [fact]~n", [G]).
print_proof(builtin(G), D) :- !, indent(D), format("~w   [calculation]~n", [G]).
print_proof(not(G), D) :- !,
    indent(D), format("not ~w   [no evidence found (negation as failure)]~n", [G]).
print_proof(rule(G, P), D) :-
    indent(D), format("~w   [rule]~n", [G]),
    D1 is D + 1, print_proof(P, D1).

indent(D) :- N is D * 3, format("~*c", [N, 32]).

% WHY: explains why an action is recommended and lists the evidence
why(F, Action) :-
    (   prove(recommended_action(F, Action), Proof)
    ->  action_reason(Action, Reason),
        format("~nWHY: ~w should ~w, because ~w.~nEvidence:~n", [F, Action, Reason]),
        findall(G, leaf(Proof, G), L0), sort(L0, Facts),
        forall(member(X, Facts), format("   - ~w~n", [X]))
    ;   format("~nWHY: no rule recommends '~w' for ~w.~n", [Action, F])
    ).

leaf(fact(G), G).
leaf((A, _), G) :- leaf(A, G).
leaf((_, B), G) :- leaf(B, G).
leaf(rule(_, P), G) :- leaf(P, G).

% Full report for one forklift
report(F) :-
    format("~n=== Report for ~w ===~n", [F]),
    risk_level(F, Risk), format("Risk level : ~w~n", [Risk]),
    best_action(F, Best), format("Best action : ~w~n", [Best]),
    forall(( setof(A, recommended_action(F, A), As), member(A, As) ), why(F, A)).

%% ---------------------------------------------------------------------
%% PART 4: DEMO
%% ---------------------------------------------------------------------
demo :-
    report(forklift_01),
    report(forklift_02),
    how(forklift_with_fault(forklift_01)),
    how(best_action(forklift_01, stop)),
    how(mission_ready(forklift_02)),
    how(mission_ready(forklift_01)).

% Try in the SWI-Prolog console:
%   ?- forklift_in_aisle(X).
%   ?- recommended_action(forklift_01, A).
%   ?- best_action(forklift_01, A).
%   ?- risk_level(F, R).
%   ?- why(forklift_01, stop).
%   ?- how(recommended_action(forklift_01, recharge)).

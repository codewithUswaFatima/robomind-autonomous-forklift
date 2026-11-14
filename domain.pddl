;; RoboMind - Autonomous Forklift | Step 6: PDDL domain
;; Battery is modelled in discrete levels (STRIPS style, no numbers needed).
(define (domain autonomous-forklift)
  (:requirements :strips :typing)

  (:types
    forklift zone pallet level)

  (:predicates
    (at ?f - forklift ?z - zone)                 ; forklift location
    (connected ?z1 ?z2 - zone)                   ; road between two zones
    (clear ?z - zone)                            ; zone is not a BlockedAisle
    (charging-station ?z - zone)                 ; zone is a ChargingStation
    (pallet-at ?p - pallet ?z - zone)            ; pallet location
    (carrying ?f - forklift ?p - pallet)         ; forklift holds a pallet
    (empty ?f - forklift)                        ; forks are free
    (battery-at ?f - forklift ?l - level)        ; current battery level
    (dec ?hi ?lo - level)                        ; ?lo is one level below ?hi
    (full ?l - level))                           ; ?l is the full level

  ;; Move one step along a road. Costs one battery level.
  ;; Blocked zones (not clear) can never be entered -> forces Reroute.
  (:action move
    :parameters (?f - forklift ?from ?to - zone ?hi ?lo - level)
    :precondition (and (at ?f ?from) (connected ?from ?to) (clear ?to)
                       (battery-at ?f ?hi) (dec ?hi ?lo))
    :effect (and (not (at ?f ?from)) (at ?f ?to)
                 (not (battery-at ?f ?hi)) (battery-at ?f ?lo)))

  ;; PickTask
  (:action pick
    :parameters (?f - forklift ?p - pallet ?z - zone)
    :precondition (and (at ?f ?z) (pallet-at ?p ?z) (empty ?f))
    :effect (and (carrying ?f ?p) (not (pallet-at ?p ?z)) (not (empty ?f))))

  ;; TransportTask (drop at the current zone)
  (:action drop
    :parameters (?f - forklift ?p - pallet ?z - zone)
    :precondition (and (at ?f ?z) (carrying ?f ?p))
    :effect (and (pallet-at ?p ?z) (empty ?f) (not (carrying ?f ?p))))

  ;; ChargeTask (Recharge recovery action), only at a charging station
  (:action charge
    :parameters (?f - forklift ?z - zone ?old ?new - level)
    :precondition (and (at ?f ?z) (charging-station ?z)
                       (battery-at ?f ?old) (full ?new))
    :effect (and (not (battery-at ?f ?old)) (battery-at ?f ?new)))
)

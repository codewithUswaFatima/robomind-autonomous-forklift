;; RoboMind - Autonomous Forklift 
;; Mission: bring pallet_01 from aisle_b2 to loading_dock_01.
;; Forklift_01 starts in aisle_a with a LOW battery (level l2 of l0..l4),
;; and the shortcut through aisle_c is a BlockedAisle.
;; Expected plan: go to charging station, recharge, pick pallet, deliver.
(define (problem forklift-mission-01)
  (:domain autonomous-forklift)

  (:objects
    forklift_01 - forklift
    pallet_01 - pallet
    charging_station_01 aisle_a aisle_b2 aisle_c intersection_01 loading_dock_01 - zone
    l0 l1 l2 l3 l4 - level)

  (:init
    ;; roads (both directions) - everything meets at the intersection
    (connected charging_station_01 intersection_01) (connected intersection_01 charging_station_01)
    (connected aisle_a intersection_01)             (connected intersection_01 aisle_a)
    (connected aisle_b2 intersection_01)            (connected intersection_01 aisle_b2)
    (connected loading_dock_01 intersection_01)     (connected intersection_01 loading_dock_01)
    ;; shortcut through the blocked aisle
    (connected aisle_a aisle_c)                     (connected aisle_c aisle_a)
    (connected aisle_c loading_dock_01)             (connected loading_dock_01 aisle_c)

    ;; zone status: aisle_c is blocked (no clear fact)
    (clear charging_station_01) (clear aisle_a) (clear aisle_b2)
    (clear intersection_01) (clear loading_dock_01)
    (charging-station charging_station_01)

    ;; battery levels
    (dec l4 l3) (dec l3 l2) (dec l2 l1) (dec l1 l0)
    (full l4)

    ;; forklift and pallet
    (at forklift_01 aisle_a)
    (empty forklift_01)
    (battery-at forklift_01 l2)
    (pallet-at pallet_01 aisle_b2))

  (:goal (and (pallet-at pallet_01 loading_dock_01)
              (empty forklift_01))))

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Tuple

from graph import Graph


ProductName = str


@dataclass(frozen=True)
class DetourCandidate:
    node: str
    anchor: str
    rejoin: str
    anchor_index: int
    rejoin_index: int
    path_to_candidate: List[str]
    path_from_candidate: List[str]
    path_anchor_to_rejoin: List[str]
    detour_cost: float
    inventory: Dict[ProductName, int]


@dataclass
class DetourSelection:
    candidate: DetourCandidate
    goods_picked: Dict[ProductName, int]


@dataclass
class RoutePlan:
    base_path: List[str]
    base_cost: float
    detours: List[DetourSelection] = field(default_factory=list)
    detour_cost: float = 0.0
    final_route: List[str] = field(default_factory=list)
    goods_picked: Dict[str, Dict[ProductName, int]] = field(default_factory=dict)
    verification_cost: float | None = None

    @property
    def total_cost(self) -> float:
        return self.base_cost + self.detour_cost


def collect_on_path(
    path: Sequence[str],
    inventory: Dict[str, Dict[ProductName, int]],
    required: Dict[ProductName, int],
) -> Tuple[Dict[str, Dict[ProductName, int]], Dict[ProductName, int]]:
    picked: Dict[str, Dict[ProductName, int]] = {}
    remaining = required.copy()

    for node in path:
        stock = inventory.get(node, {})
        for product, need in remaining.items():
            if need <= 0:
                continue
            available = stock.get(product, 0)
            if available <= 0:
                continue
            # We are forced to take whole units, up to the remaining demand.
            take = min(available, need)
            if take > 0:
                picked.setdefault(node, {})[product] = take
                remaining[product] -= take

    return picked, remaining


def remaining_requirements_met(remaining: Dict[ProductName, int]) -> bool:
    return all(amount <= 0 for amount in remaining.values())


def verify_detour_optimality(
    candidates: Sequence[DetourCandidate],
    remaining: Dict[ProductName, int],
    product_order: List[ProductName],
    expected_cost: float,
) -> float:
    """Explicitly verify no cheaper detour combination meets the remaining demand."""

    target = tuple(max(0, remaining[product]) for product in product_order)
    if all(value == 0 for value in target):
        if not math.isclose(expected_cost, 0.0, abs_tol=1e-9):
            raise RuntimeError(
                "Verification failed: zero remaining demand yet detour cost is non-zero."
            )
        return 0.0

    best_cost: float | None = None

    def dfs(index: int, state: Tuple[int, ...], cost: float) -> None:
        nonlocal best_cost
        if best_cost is not None and cost >= best_cost - 1e-9:
            return

        if index == len(candidates):
            if state == target:
                if best_cost is None or cost < best_cost:
                    best_cost = cost
            return

        candidate = candidates[index]

        # Option 1: skip this candidate entirely.
        dfs(index + 1, state, cost)

        # Option 2: take a non-zero pickup combination from this candidate.
        for option in generate_pick_options(candidate, remaining, product_order):
            new_state_list: List[int] = []
            feasible = True
            for dim, value in enumerate(option):
                total = state[dim] + value
                if total > target[dim]:
                    feasible = False
                    break
                new_state_list.append(total)

            if not feasible:
                continue

            dfs(
                index + 1,
                tuple(new_state_list),
                cost + candidate.detour_cost,
            )

    dfs(0, tuple(0 for _ in product_order), 0.0)

    if best_cost is None:
        raise RuntimeError(
            "Verification failed: remaining demand cannot be met by any detour combination."
        )

    if best_cost + 1e-9 < expected_cost:
        raise RuntimeError(
            "Detour plan is not cost-optimal: "
            f"verification found cheaper cost {best_cost} < planned cost {expected_cost}."
        )

    return best_cost


def compute_detour_candidates(
    graph: Graph,
    base_path: Sequence[str],
    inventory: Dict[str, Dict[ProductName, int]],
) -> List[DetourCandidate]:
    base_nodes = set(base_path)
    base_index = {node: idx for idx, node in enumerate(base_path)}
    base_segment_cost: Dict[Tuple[str, str], float] = {}
    for u, v in zip(base_path[:-1], base_path[1:]):
        base_segment_cost[(u, v)] = graph.path_cost([u, v])
    candidates: List[DetourCandidate] = []

    for node, stock in inventory.items():
        if node in base_nodes:
            continue
        if all(amount <= 0 for amount in stock.values()):
            continue

        for anchor_idx, anchor in enumerate(base_path):
            try:
                outbound_cost, outbound_path = graph.shortest_path(anchor, node)
            except ValueError:
                continue

            # Return-to-anchor detour.
            try:
                return_cost, return_path = graph.shortest_path(node, anchor)
            except ValueError:
                continue
            path_anchor_to_rejoin = outbound_path + return_path[1:]
            detour_cost = outbound_cost + return_cost
            detour = DetourCandidate(
                node=node,
                anchor=anchor,
                rejoin=anchor,
                anchor_index=anchor_idx,
                rejoin_index=anchor_idx,
                path_to_candidate=list(outbound_path),
                path_from_candidate=list(return_path),
                path_anchor_to_rejoin=path_anchor_to_rejoin,
                detour_cost=detour_cost,
                inventory=stock,
            )
            candidates.append(detour)

            # Bridging detour to immediate successor along base path.
            if anchor_idx < len(base_path) - 1:
                rejoin = base_path[anchor_idx + 1]
                base_cost = base_segment_cost[(anchor, rejoin)]
                try:
                    back_cost, back_path = graph.shortest_path(node, rejoin)
                except ValueError:
                    continue
                total_cost = outbound_cost + back_cost
                incremental_cost = total_cost - base_cost
                if incremental_cost < -1e-9:
                    raise RuntimeError(
                        "Detour reduces cost below base path segment, contradicting optimal base path."
                    )
                path_anchor_to_rejoin = outbound_path + back_path[1:]
                detour_bridge = DetourCandidate(
                    node=node,
                    anchor=anchor,
                    rejoin=rejoin,
                    anchor_index=anchor_idx,
                    rejoin_index=anchor_idx + 1,
                    path_to_candidate=list(outbound_path),
                    path_from_candidate=list(back_path),
                    path_anchor_to_rejoin=path_anchor_to_rejoin,
                    detour_cost=incremental_cost,
                    inventory=stock,
                )
                candidates.append(detour_bridge)

    return candidates


def generate_pick_options(
    candidate: DetourCandidate,
    remaining: Dict[ProductName, int],
    product_order: List[ProductName],
) -> List[Tuple[int, ...]]:
    limits = [
        min(candidate.inventory.get(product, 0), max(0, remaining[product]))
        for product in product_order
    ]

    options: List[Tuple[int, ...]] = []

    def backtrack(index: int, current: List[int]) -> None:
        if index == len(product_order):
            if any(amount > 0 for amount in current):
                options.append(tuple(current))
            return

        for take in range(limits[index] + 1):
            current.append(take)
            backtrack(index + 1, current)
            current.pop()

    backtrack(0, [])
    return options


def select_detours(
    candidates: List[DetourCandidate],
    remaining: Dict[ProductName, int],
    product_order: List[ProductName],
) -> Tuple[List[List[DetourSelection]], float]:
    target_state = tuple(max(0, remaining[product]) for product in product_order)
    initial_state = tuple(0 for _ in product_order)
    if all(value == 0 for value in target_state):
        return [[]], 0.0

    # DP state encodes how many units of each product have been satisfied so far.
    dp: Dict[Tuple[int, ...], Tuple[float, set[Tuple[Tuple[int, Tuple[int, ...]], ...]]]] = {
        initial_state: (0.0, {()})
    }
    tol = 1e-9

    for idx, candidate in enumerate(candidates):
        # Enumerate all non-zero pickup combinations (whole units only) available at this detour.
        pick_options = generate_pick_options(candidate, remaining, product_order)
        if not pick_options:
            continue

        next_dp: Dict[
            Tuple[int, ...], Tuple[float, set[Tuple[Tuple[int, Tuple[int, ...]], ...]]]
        ] = {}

        def update_state(
            store: Dict[
                Tuple[int, ...],
                Tuple[float, set[Tuple[Tuple[int, Tuple[int, ...]], ...]]],
            ],
            state: Tuple[int, ...],
            cost: float,
            combos: Iterable[Tuple[Tuple[int, Tuple[int, ...]], ...]],
        ) -> None:
            combos_set = set(combos)
            existing = store.get(state)
            if existing is None or cost + tol < existing[0]:
                store[state] = (cost, combos_set)
            elif abs(cost - existing[0]) <= tol:
                existing[1].update(combos_set)

        for state, (state_cost, selections) in dp.items():
            update_state(next_dp, state, state_cost, selections)
            for option in pick_options:
                new_state_list: List[int] = []
                feasible = True
                for dim, value in enumerate(option):
                    new_total = state[dim] + value
                    if new_total > target_state[dim]:
                        feasible = False
                        break
                    new_state_list.append(new_total)

                if not feasible:
                    continue

                new_state = tuple(new_state_list)
                new_cost = state_cost + candidate.detour_cost
                new_combos: set[
                    Tuple[Tuple[int, Tuple[int, ...]], ...]
                ] = set()
                for selection in selections:
                    if any(candidates[s_idx].node == candidate.node for s_idx, _ in selection):
                        continue
                    new_combos.add(selection + ((idx, option),))
                if new_combos:
                    update_state(next_dp, new_state, new_cost, new_combos)

        dp = next_dp

    if target_state not in dp:
        raise RuntimeError(
            "Unable to satisfy product requirements with available detours."
        )

    total_cost, encoded_selection = dp[target_state]
    detour_selections: List[List[DetourSelection]] = []

    for combination in sorted(encoded_selection):
        combo_selections: List[DetourSelection] = []
        for candidate_idx, option in combination:
            candidate = candidates[candidate_idx]
            goods = {
                product_order[i]: option[i]
                for i in range(len(product_order))
                if option[i] > 0
            }
            combo_selections.append(
                DetourSelection(candidate=candidate, goods_picked=goods)
            )
        detour_selections.append(combo_selections)

    return detour_selections, total_cost


def build_final_route(
    base_path: Sequence[str], detours: Sequence[DetourSelection]
) -> List[str]:
    final_route: List[str] = [base_path[0]]
    detours_by_anchor_idx: Dict[int, List[DetourSelection]] = {}
    for detour in detours:
        detours_by_anchor_idx.setdefault(
            detour.candidate.anchor_index, []
        ).append(detour)

    for idx, node in enumerate(base_path):
        if final_route[-1] != node:
            final_route.append(node)

        anchor_detours = detours_by_anchor_idx.get(idx, [])
        if not anchor_detours:
            continue

        anchor_detours.sort(
            key=lambda detour: (
                detour.candidate.rejoin_index,
                detour.candidate.node,
            )
        )

        for detour in anchor_detours:
            path = detour.candidate.path_anchor_to_rejoin
            if len(path) < 2:
                continue
            final_route.extend(path[1:])

    return final_route


def plan_route(
    graph: Graph,
    inventory: Dict[str, Dict[ProductName, int]],
    target_counts: Dict[ProductName, int],
    start: str,
    end: str,
) -> List[RoutePlan]:
    # Phase 1: find all backbone shortest paths (globally optimal A→N routes).
    base_cost, base_paths = graph.all_shortest_paths(start, end)
    all_plans: List[RoutePlan] = []
    tol = 1e-9

    for base_path in base_paths:
        collected_on_base, remaining = collect_on_path(
            base_path, inventory, target_counts
        )
        goods_on_base = {
            node: dict(products) for node, products in collected_on_base.items()
        }

        base_path_cost = graph.path_cost(list(base_path))
        remaining_needed = {
            product: max(0, remaining[product]) for product in target_counts
        }

        if remaining_requirements_met(remaining_needed):
            plan = RoutePlan(
                base_path=list(base_path),
                base_cost=base_path_cost,
                detours=[],
                detour_cost=0.0,
                final_route=list(base_path),
                goods_picked=goods_on_base,
                verification_cost=0.0,
            )
            all_plans.append(plan)
            continue

        # Phase 2: compute all cheapest detour combinations that fill remaining demand.
        candidates = compute_detour_candidates(graph, base_path, inventory)
        product_order = list(target_counts.keys())
        detour_combinations, detour_cost = select_detours(
            candidates, remaining_needed, product_order
        )

        verified_cost = verify_detour_optimality(
            candidates=candidates,
            remaining=remaining_needed,
            product_order=product_order,
            expected_cost=detour_cost,
        )

        anchor_index = {node: idx for idx, node in enumerate(base_path)}

        for combination in detour_combinations:
            sorted_combo = sorted(
                combination,
                key=lambda detour: (
                    anchor_index.get(detour.candidate.anchor, len(base_path)),
                    detour.candidate.node,
                ),
            )

            plan_goods: Dict[str, Dict[ProductName, int]] = {
                node: dict(goods) for node, goods in goods_on_base.items()
            }

            for detour in sorted_combo:
                node = detour.candidate.node
                if not detour.goods_picked:
                    continue
                node_goods = plan_goods.setdefault(node, {})
                for product, amount in detour.goods_picked.items():
                    if amount <= 0:
                        continue
                    node_goods[product] = node_goods.get(product, 0) + amount

            totals = {product: 0 for product in target_counts}
            for node_goods in plan_goods.values():
                for product, amount in node_goods.items():
                    if product in totals:
                        totals[product] += amount

            for product, required in target_counts.items():
                if totals.get(product, 0) != required:
                    raise RuntimeError(
                        "Planned pickups do not match target product counts. "
                        f"Need {required} {product}, planned {totals.get(product, 0)}."
                    )

            combo_cost = sum(detour.candidate.detour_cost for detour in sorted_combo)
            if not math.isclose(combo_cost, detour_cost, abs_tol=tol):
                raise RuntimeError(
                    "Detour combination cost mismatch: "
                    f"expected {detour_cost}, got {combo_cost}."
                )

            plan = RoutePlan(
                base_path=list(base_path),
                base_cost=base_path_cost,
                detours=list(sorted_combo),
                detour_cost=combo_cost,
                final_route=build_final_route(base_path, sorted_combo),
                goods_picked=plan_goods,
                verification_cost=verified_cost,
            )
            all_plans.append(plan)

    if not all_plans:
        raise RuntimeError("No feasible route plan found for the given instance.")

    # Remove duplicates that yield identical routes and pickup distributions.
    unique_plans: Dict[
        Tuple[Tuple[str, ...], Tuple[Tuple[str, Tuple[Tuple[str, int], ...]], ...]],
        RoutePlan,
    ] = {}

    for plan in all_plans:
        goods_key = tuple(
            sorted(
                (node, tuple(sorted(goods.items())))
                for node, goods in plan.goods_picked.items()
            )
        )
        key = (tuple(plan.final_route), goods_key)
        if key not in unique_plans:
            unique_plans[key] = plan

    plans = list(unique_plans.values())
    best_total_cost = min(plan.total_cost for plan in plans)
    optimal_plans = [
        plan
        for plan in plans
        if math.isclose(plan.total_cost, best_total_cost, abs_tol=tol)
    ]

    optimal_plans.sort(
        key=lambda plan: (" -> ".join(plan.final_route), plan.detour_cost)
    )

    return optimal_plans

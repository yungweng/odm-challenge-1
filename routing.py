from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from graph import Graph


ProductName = str


@dataclass(frozen=True)
class DetourCandidate:
    node: str
    anchor: str
    path_to_candidate: List[str]
    cost_outbound: float
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


def compute_detour_candidates(
    graph: Graph,
    base_path: Sequence[str],
    inventory: Dict[str, Dict[ProductName, int]],
) -> List[DetourCandidate]:
    base_nodes = set(base_path)
    candidates: List[DetourCandidate] = []

    for node, stock in inventory.items():
        if node in base_nodes:
            continue
        if all(amount <= 0 for amount in stock.values()):
            continue

        best_anchor: str | None = None
        best_path: List[str] | None = None
        best_outbound_cost: float | None = None

        for anchor in base_path:
            try:
                cost, path = graph.shortest_path(anchor, node)
            except ValueError:
                continue

            if best_outbound_cost is None or cost < best_outbound_cost:
                best_anchor = anchor
                best_path = path
                best_outbound_cost = cost

        if best_anchor is None or best_path is None or best_outbound_cost is None:
            continue

        detour = DetourCandidate(
            node=node,
            anchor=best_anchor,
            path_to_candidate=best_path,
            cost_outbound=best_outbound_cost,
            detour_cost=2 * best_outbound_cost,  # go out + return along same path
            inventory=stock,
        )
        candidates.append(detour)

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
) -> Tuple[List[DetourSelection], float]:
    target_state = tuple(max(0, remaining[product]) for product in product_order)
    initial_state = tuple(0 for _ in product_order)
    if all(value == 0 for value in target_state):
        return [], 0.0

    # DP state encodes how many units of each product have been satisfied so far.
    dp: Dict[Tuple[int, ...], Tuple[float, List[Tuple[int, Tuple[int, ...]]]]] = {
        initial_state: (0.0, [])
    }

    for idx, candidate in enumerate(candidates):
        # Enumerate all non-zero pickup combinations (whole units only) available at this detour.
        pick_options = generate_pick_options(candidate, remaining, product_order)
        if not pick_options:
            continue

        next_dp = dict(dp)
        for state, (state_cost, selections) in dp.items():
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
                existing = next_dp.get(new_state)
                if existing is None or new_cost < existing[0]:
                    next_dp[new_state] = (
                        new_cost,
                        selections + [(idx, option)],
                    )

        dp = next_dp

    if target_state not in dp:
        raise RuntimeError(
            "Unable to satisfy product requirements with available detours."
        )

    total_cost, encoded_selection = dp[target_state]
    detour_selections: List[DetourSelection] = []

    for candidate_idx, option in encoded_selection:
        candidate = candidates[candidate_idx]
        goods = {
            product_order[i]: option[i]
            for i in range(len(product_order))
            if option[i] > 0
        }
        detour_selections.append(
            DetourSelection(candidate=candidate, goods_picked=goods)
        )

    return detour_selections, total_cost


def build_final_route(
    base_path: Sequence[str], detours: Sequence[DetourSelection]
) -> List[str]:
    final_route: List[str] = [base_path[0]]
    detours_by_anchor: Dict[str, List[DetourSelection]] = {}
    for detour in detours:
        detours_by_anchor.setdefault(detour.candidate.anchor, []).append(detour)

    for node in base_path:
        if node != final_route[-1]:
            final_route.append(node)

        for detour in detours_by_anchor.get(node, []):
            path = detour.candidate.path_to_candidate
            if len(path) < 2:
                continue

            # Walk the stored shortest path out to the detour node and straight back.
            forward_segment = path[1:]
            return_segment = list(reversed(path[:-1]))
            final_route.extend(forward_segment)
            final_route.extend(return_segment)

    return final_route


def plan_route(
    graph: Graph,
    inventory: Dict[str, Dict[ProductName, int]],
    target_counts: Dict[ProductName, int],
    start: str,
    end: str,
) -> RoutePlan:
    # Phase 1: find the lexicographic backbone (globally shortest path A→N).
    base_cost, base_path = graph.shortest_path(start, end)

    collected_on_base, remaining = collect_on_path(base_path, inventory, target_counts)

    goods_picked = {
        node: dict(products) for node, products in collected_on_base.items()
    }

    plan = RoutePlan(
        base_path=list(base_path),
        base_cost=base_cost,
        goods_picked=goods_picked,
    )

    if remaining_requirements_met(remaining):
        plan.final_route = list(base_path)
        return plan

    # Phase 2: compute cheapest detours that fill remaining demand.
    candidates = compute_detour_candidates(graph, base_path, inventory)

    product_order = list(target_counts.keys())
    detour_selections, detour_cost = select_detours(
        candidates, remaining, product_order
    )

    for detour in detour_selections:
        node = detour.candidate.node
        for product, amount in detour.goods_picked.items():
            if amount <= 0:
                continue
            plan.goods_picked.setdefault(node, {})
            plan.goods_picked[node][product] = (
                plan.goods_picked[node].get(product, 0) + amount
            )

    plan.detours = detour_selections
    plan.detour_cost = detour_cost
    plan.final_route = build_final_route(base_path, detour_selections)

    totals = {product: 0 for product in target_counts}
    for node_goods in plan.goods_picked.values():
        for product, amount in node_goods.items():
            if product in totals:
                totals[product] += amount

    for product, required in target_counts.items():
        if totals.get(product, 0) != required:
            raise RuntimeError(
                "Planned pickups do not match target product counts. "
                f"Need {required} {product}, planned {totals.get(product, 0)}."
            )

    return plan

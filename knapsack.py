from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


ProductName = str


@dataclass(frozen=True)
class KnapsackResult:
    counts: Dict[ProductName, int]
    profit: float
    weight: float
    total_units: int


def aggregate_inventory(
    inventory: Dict[str, Dict[ProductName, int]],
) -> Dict[ProductName, int]:
    totals: Dict[ProductName, int] = {}
    for node_inventory in inventory.values():
        for product, amount in node_inventory.items():
            totals[product] = totals.get(product, 0) + amount
    return totals


def solve_knapsack(
    products: Dict[ProductName, Dict[str, float]],
    inventory: Dict[str, Dict[ProductName, int]],
    constraints: Dict[str, float],
) -> KnapsackResult:
    """Determine the profit-maximising aggregate product mix."""

    # Aggregate global upper bounds for each product across all locations.
    totals = aggregate_inventory(inventory)
    max_gems = totals.get("gemstones", 0)
    max_epoxy = totals.get("epoxy", 0)
    max_copper = totals.get("copper", 0)

    profit_per_unit = {
        product: products[product]["profit_per_unit"] for product in products
    }
    weight_per_unit = {
        product: products[product]["weight_per_unit"] for product in products
    }

    weight_limit = constraints["warehouse_capacity_tons"]
    unit_limit = constraints["truck_capacity_units"]
    copper_ratio = constraints["copper_to_gemstone_ratio"]

    best: KnapsackResult | None = None

    for gems in range(max_gems + 1):
        # Copper upper bound comes from availability AND coupling copper ≤ ratio * gemstones.
        max_copper_allowed = min(max_copper, math.floor(copper_ratio * gems))
        for epoxy in range(max_epoxy + 1):
            total_units_partial = gems + epoxy
            weight_partial = (
                gems * weight_per_unit["gemstones"]
                + epoxy * weight_per_unit["epoxy"]
            )
            # Early prune partial choices that already violate unit or warehouse capacity.
            if total_units_partial > unit_limit or weight_partial > weight_limit:
                continue

            for copper in range(max_copper_allowed + 1):
                total_units = total_units_partial + copper
                if total_units > unit_limit:
                    # copper increases units monotonically within loop → break.
                    break

                total_weight = weight_partial + copper * weight_per_unit["copper"]
                if total_weight > weight_limit:
                    # additional copper only increases weight → break.
                    break

                profit = (
                    gems * profit_per_unit["gemstones"]
                    + epoxy * profit_per_unit["epoxy"]
                    + copper * profit_per_unit["copper"]
                )

                counts = {
                    "gemstones": gems,
                    "epoxy": epoxy,
                    "copper": copper,
                }

                candidate = KnapsackResult(
                    counts=counts,
                    profit=profit,
                    weight=total_weight,
                    total_units=total_units,
                )

                if best is None or profit > best.profit:
                    best = candidate

    if best is None:
        raise RuntimeError("No feasible knapsack solution found given the constraints.")

    return best

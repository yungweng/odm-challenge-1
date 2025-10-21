from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

import yaml

from graph import Graph
from knapsack import KnapsackResult, solve_knapsack
from routing import RoutePlan, plan_route


def load_config(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def summarise_goods(counts: Dict[str, int]) -> str:
    parts = [f"{product}: {amount}" for product, amount in counts.items()]
    return ", ".join(parts)


def print_plan(result: KnapsackResult, plan: RoutePlan) -> None:
    print("=== Knapsack Target (Profit Maximisation) ===")
    print(f"Target mix: {summarise_goods(result.counts)}")
    print(f"Total profit (without travel costs): {result.profit:.2f} €")
    print()

    print("=== Route Planning (Cost Minimisation) ===")
    print(f"Base path: {' -> '.join(plan.base_path)} (cost {plan.base_cost:.2f})")
    if plan.detours:
        print("Detours:")
        for detour in plan.detours:
            candidate = detour.candidate
            goods_summary = summarise_goods(detour.goods_picked)
            forward = " -> ".join(candidate.path_to_candidate)
            print(
                f"  - {candidate.anchor} detour to {candidate.node} "
                f"(path {forward}, cost {candidate.detour_cost:.2f}) "
                f"goods [{goods_summary}]"
            )
    else:
        print("No detours required.")

    if plan.verification_cost is not None:
        print(
            f"Verification: brute-force search confirmed detour cost "
            f"{plan.detour_cost:.2f} (best possible {plan.verification_cost:.2f})."
        )

    print()
    print(f"Final route: {' -> '.join(plan.final_route)}")
    print(f"Total travel cost: {plan.total_cost:.2f}")
    net_profit = result.profit - plan.total_cost
    print(f"Net profit (profit - travel cost): {net_profit:.2f} €")
    print()
    print("Goods picked per location:")
    for node, goods in sorted(plan.goods_picked.items()):
        print(f"  {node}: {summarise_goods(goods)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Solve the ODM Challenge 1 routing and knapsack task."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("problem_instance.yaml"),
        help="Path to the YAML instance configuration.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    graph_config = config["graph"]
    graph = Graph(graph_config["nodes"], graph_config["edges"])

    # Phase 1: profit maximisation on aggregated goods (lexicographic primary objective).
    knapsack_result = solve_knapsack(
        products=config["products"],
        inventory=config["inventory"],
        constraints=config["constraints"],
    )

    routing_config = config["routing"]
    # Phase 2: cost minimisation subject to the fixed product mix.
    plan = plan_route(
        graph=graph,
        inventory=config["inventory"],
        target_counts=knapsack_result.counts,
        start=routing_config["start_node"],
        end=routing_config["end_node"],
    )

    print_plan(knapsack_result, plan)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote
import webbrowser
import tempfile
from typing import Dict, List

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


def print_plans(result: KnapsackResult, plans: List[RoutePlan]) -> None:
    print("=== Knapsack Target (Profit Maximisation) ===")
    print(f"Target mix: {summarise_goods(result.counts)}")
    print(f"Total profit (without travel costs): {result.profit:.2f} €")
    print()

    print("=== Route Planning (Cost Minimisation) ===")
    if not plans:
        print("No feasible minimal routes found.")
        return

    minimal_total_cost = min(plan.total_cost for plan in plans)
    route_word = "route" if len(plans) == 1 else "routes"
    unique_routes: Dict[Tuple[str, ...], List[RoutePlan]] = {}
    for plan in plans:
        unique_routes.setdefault(tuple(plan.final_route), []).append(plan)

    print(
        f"Found {len(plans)} optimal {route_word} across "
        f"{len(unique_routes)} distinct final routes (travel cost {minimal_total_cost:.2f})."
    )
    print()

    for idx, (route, variants) in enumerate(unique_routes.items(), start=1):
        primary = variants[0]
        net_profit = result.profit - primary.total_cost
        base_path = " -> ".join(primary.base_path)
        print(f"[Route {idx}] {' -> '.join(route)}")
        print(
            f"  Travel cost {primary.total_cost:.2f} (base {base_path}, cost {primary.base_cost:.2f})"
        )
        print(f"  Net profit {net_profit:.2f} €")
        if primary.verification_cost is not None:
            print(
                f"  Verified detour lower bound {primary.verification_cost:.2f}"
            )

        if not primary.detours:
            print("  Detours: none required")
        else:
            variant_label = "variant" if len(variants) == 1 else "variants"
            print(f"  Detour {variant_label}: {len(variants)} option(s)")
            for option_idx, variant in enumerate(variants, start=1):
                print(
                    f"    ({option_idx}) detour cost {variant.detour_cost:.2f}"
                )
                for detour in variant.detours:
                    candidate = detour.candidate
                    goods_summary = summarise_goods(detour.goods_picked)
                    path = " -> ".join(candidate.path_anchor_to_rejoin)
                    rejoin_note = (
                        ""
                        if candidate.rejoin == candidate.anchor
                        else f" (rejoin {candidate.rejoin})"
                    )
                    print(
                        f"       {path}{rejoin_note}  goods [{goods_summary}]"
                    )
                pickup_summary = "; ".join(
                    f"{node}[{summarise_goods(goods)}]"
                    for node, goods in sorted(variant.goods_picked.items())
                )
                print(f"       pickups: {pickup_summary}")

        print()


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
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Open an interactive browser visualisation of the solution.",
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
    plans = plan_route(
        graph=graph,
        inventory=config["inventory"],
        target_counts=knapsack_result.counts,
        start=routing_config["start_node"],
        end=routing_config["end_node"],
    )

    print_plans(knapsack_result, plans)

    if args.visualize:
        from visualize_html import compute_layout, render_html

        if not plans:
            raise RuntimeError(
                "Visualisation requested but no route plans were produced."
            )
        primary_plan = plans[0]
        if len(plans) > 1:
            print(
                f"Visualising Route Option 1 out of {len(plans)} optimal choices in the browser."
            )

        layout = compute_layout(config["graph"]["nodes"])
        html = render_html(
            plan=primary_plan,
            knapsack_result=knapsack_result,
            config=config,
            layout=layout,
        )
        data_uri = "data:text/html;charset=utf-8," + quote(html, safe="~()*!.'")
        opened = False
        use_data_uri = sys.platform != "darwin"
        if use_data_uri:
            try:
                opened = webbrowser.open_new_tab(data_uri)
            except Exception as exc:  # pragma: no cover - platform dependent
                print(f"Warning: unable to launch browser for visualisation ({exc}).")
        if not opened:
            temp = tempfile.NamedTemporaryFile(
                "w", suffix=".html", delete=False, encoding="utf-8"
            )
            with temp:
                temp.write(html)
            tmp_path = Path(temp.name)
            webbrowser.open_new_tab(tmp_path.as_uri())
            print(f"Visualisation stored at: {tmp_path}")


if __name__ == "__main__":
    main()

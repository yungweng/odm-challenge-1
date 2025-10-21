from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib.pyplot as plt
from matplotlib import animation
import networkx as nx
import yaml

from graph import Graph
from knapsack import solve_knapsack
from routing import RoutePlan, plan_route


ProductName = str


def load_config(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_networkx_graph(graph_config: Dict) -> nx.Graph:
    g = nx.Graph()
    g.add_nodes_from(graph_config["nodes"])
    for origin, target, cost in graph_config["edges"]:
        g.add_edge(origin, target, cost=cost)
    return g


def compute_layout(graph: nx.Graph) -> Dict[str, Tuple[float, float]]:
    return nx.spring_layout(graph, seed=42)


def inventory_value(node_inventory: Dict[ProductName, int], products: Dict) -> float:
    value = 0.0
    for product, amount in node_inventory.items():
        if product in products:
            value += amount * products[product]["profit_per_unit"]
    return value


def node_labels(inventory: Dict[str, Dict[ProductName, int]]) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for node, goods in inventory.items():
        labels[node] = (
            f"{node}\nG:{goods.get('gemstones', 0)} "
            f"E:{goods.get('epoxy', 0)} "
            f"C:{goods.get('copper', 0)}"
        )
    return labels


def route_edges(path: Sequence[str]) -> List[Tuple[str, str]]:
    return list(zip(path[:-1], path[1:]))


def draw_static_figure(
    graph_nx: nx.Graph,
    layout: Dict[str, Tuple[float, float]],
    plan: RoutePlan,
    knapsack_result,
    config: Dict,
    output: Path | None,
    show: bool,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 8))

    inventory = config["inventory"]
    products = config["products"]

    node_values = [
        inventory_value(inventory[node], products) for node in graph_nx.nodes
    ]

    nx.draw_networkx_edges(graph_nx, layout, ax=ax, edge_color="lightgray", width=1.0)

    final_route_edges = route_edges(plan.final_route)
    if final_route_edges:
        nx.draw_networkx_edges(
            graph_nx,
            layout,
            edgelist=final_route_edges,
            edge_color="#d62728",
            width=2.5,
            ax=ax,
        )

    nx.draw_networkx_nodes(
        graph_nx,
        layout,
        node_color=node_values,
        cmap=plt.cm.YlGn,
        node_size=600,
        ax=ax,
    )

    labels = node_labels(inventory)
    nx.draw_networkx_labels(graph_nx, layout, labels=labels, font_size=9, ax=ax)

    edge_labels = {(u, v): data["cost"] for u, v, data in graph_nx.edges(data=True)}
    nx.draw_networkx_edge_labels(graph_nx, layout, edge_labels=edge_labels, font_size=8)

    total_cost = plan.total_cost
    net_profit = knapsack_result.profit - total_cost

    summary_lines = [
        f"Profit target: {knapsack_result.profit:.0f} €",
        f"Travel cost: {total_cost:.0f}",
        f"Net profit: {net_profit:.0f} €",
        f"Final route length: {len(plan.final_route)} steps",
    ]
    summary_lines.append(
        "Detours: "
        + ", ".join(
            f"{detour.candidate.anchor}->{detour.candidate.node}"
            for detour in plan.detours
        )
        if plan.detours
        else "Detours: none"
    )
    text = "\n".join(summary_lines)
    ax.text(
        1.02,
        0.5,
        text,
        transform=ax.transAxes,
        va="center",
        fontsize=10,
        bbox=dict(facecolor="white", alpha=0.8, boxstyle="round"),
    )

    ax.set_axis_off()
    ax.set_title("ODM Route Plan – Static Overview")

    if output:
        fig.savefig(output, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)


def animate_route(
    graph_nx: nx.Graph,
    layout: Dict[str, Tuple[float, float]],
    plan: RoutePlan,
    knapsack_result,
    config: Dict,
    output: Path | None,
    show: bool,
) -> None:
    final_route = plan.final_route
    if not final_route:
        return

    inventory = config["inventory"]
    products = config["products"]
    constraints = config["constraints"]

    fig, ax = plt.subplots(figsize=(10, 8))

    node_values = [
        inventory_value(inventory[node], products) for node in graph_nx.nodes
    ]

    nx.draw_networkx_edges(graph_nx, layout, ax=ax, edge_color="lightgray", width=1.0)
    nx.draw_networkx_nodes(
        graph_nx,
        layout,
        node_color=node_values,
        cmap=plt.cm.YlGn,
        node_size=500,
        ax=ax,
    )
    nx.draw_networkx_labels(
        graph_nx, layout, labels=node_labels(inventory), font_size=9, ax=ax
    )

    path_line, = ax.plot([], [], color="#d62728", linewidth=2.0, zorder=2)
    current_edge_line, = ax.plot([], [], color="#ff7f0e", linewidth=3.0, zorder=3)
    truck_marker = ax.scatter([], [], s=160, c="#1f77b4", zorder=4)
    status_text = ax.text(
        0.02,
        0.98,
        "",
        transform=ax.transAxes,
        va="top",
        fontsize=10,
        bbox=dict(facecolor="white", alpha=0.8, boxstyle="round"),
    )

    ax.set_axis_off()
    ax.set_title("ODM Route Plan – Animated Tour")

    target_counts = knapsack_result.counts
    collected = {product: 0 for product in target_counts}
    collected_nodes: set[str] = set()

    weight_per_unit = {
        product: products[product]["weight_per_unit"] for product in products
    }
    weight_limit = constraints["warehouse_capacity_tons"]
    unit_limit = constraints["truck_capacity_units"]

    def init():
        path_line.set_data([], [])
        current_edge_line.set_data([], [])
        truck_marker.set_offsets([[float("nan"), float("nan")]])
        status_text.set_text("")
        return path_line, current_edge_line, truck_marker, status_text

    def update(frame: int):
        node = final_route[frame]
        x, y = layout[node]
        route_prefix = final_route[: frame + 1]
        xs = [layout[n][0] for n in route_prefix]
        ys = [layout[n][1] for n in route_prefix]
        path_line.set_data(xs, ys)
        truck_marker.set_offsets([[x, y]])

        if frame > 0:
            prev = final_route[frame - 1]
            x_prev, y_prev = layout[prev]
            current_edge_line.set_data([x_prev, x], [y_prev, y])
        else:
            current_edge_line.set_data([], [])

        if node in plan.goods_picked and node not in collected_nodes:
            for product, amount in plan.goods_picked[node].items():
                if product in collected:
                    collected[product] += amount
            collected_nodes.add(node)

        collected_units = sum(collected.values())
        collected_weight = sum(
            collected[product] * weight_per_unit.get(product, 0)
            for product in collected
        )
        collected_str = ", ".join(
            f"{product}: {collected[product]}/{target_counts[product]}"
            for product in target_counts
        )

        text = "\n".join(
            [
                f"Step {frame + 1}/{len(final_route)}",
                f"At node: {node}",
                f"Collected: {collected_str}",
                f"Weight: {collected_weight:.1f}/{weight_limit} t",
                f"Units: {collected_units}/{unit_limit}",
            ]
        )
        status_text.set_text(text)

        return path_line, current_edge_line, truck_marker, status_text

    anim = animation.FuncAnimation(
        fig,
        update,
        frames=len(final_route),
        init_func=init,
        interval=800,
        blit=False,
    )

    if output:
        output_path = Path(output)
        suffix = output_path.suffix.lower()
        if suffix == ".gif":
            writer = animation.PillowWriter(fps=1)
            anim.save(output_path, writer=writer)
        elif suffix in {".mp4", ".m4v"}:
            writer = animation.FFMpegWriter(fps=1)
            anim.save(output_path, writer=writer)
        else:
            anim.save(output_path)

    if show:
        plt.show()
    else:
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualise ODM Challenge 1 route, pickups, and capacities."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("problem_instance.yaml"),
        help="Path to the YAML instance configuration.",
    )
    parser.add_argument(
        "--static-out",
        type=Path,
        help="Optional path to save a static PNG of the graph and route.",
    )
    parser.add_argument(
        "--animation-out",
        type=Path,
        help="Optional path to save an animation (GIF/MP4) of the tour.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not display figures interactively.",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    graph_nx = build_networkx_graph(config["graph"])
    layout = compute_layout(graph_nx)

    graph_solver = Graph(config["graph"]["nodes"], config["graph"]["edges"])
    knapsack_result = solve_knapsack(
        products=config["products"],
        inventory=config["inventory"],
        constraints=config["constraints"],
    )
    routing_config = config["routing"]
    plan = plan_route(
        graph=graph_solver,
        inventory=config["inventory"],
        target_counts=knapsack_result.counts,
        start=routing_config["start_node"],
        end=routing_config["end_node"],
    )

    show = not args.no_show

    draw_static_figure(
        graph_nx=graph_nx,
        layout=layout,
        plan=plan,
        knapsack_result=knapsack_result,
        config=config,
        output=args.static_out,
        show=show,
    )

    animate_route(
        graph_nx=graph_nx,
        layout=layout,
        plan=plan,
        knapsack_result=knapsack_result,
        config=config,
        output=args.animation_out,
        show=show,
    )


if __name__ == "__main__":
    main()

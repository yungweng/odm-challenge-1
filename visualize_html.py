from __future__ import annotations

import json
import math
from string import Template
from typing import Dict, Iterable, List, Sequence, Tuple

from routing import RoutePlan


ProductName = str


def compute_layout(
    nodes: Sequence[str], width: float = 800.0, height: float = 600.0
) -> Dict[str, Tuple[float, float]]:
    """Place nodes on a circle for a simple, dependency-free layout."""
    centre_x = width / 2.0
    centre_y = height / 2.0
    radius = min(width, height) * 0.38 if nodes else 0.0
    positions: Dict[str, Tuple[float, float]] = {}
    total = len(nodes)
    for index, node in enumerate(nodes):
        angle = 2.0 * math.pi * (index / total) if total else 0.0
        x = centre_x + radius * math.cos(angle)
        y = centre_y + radius * math.sin(angle)
        positions[node] = (x, y)
    return positions


def _route_edges(path: Sequence[str]) -> List[Tuple[str, str]]:
    return list(zip(path[:-1], path[1:]))


def render_html(
    plan: RoutePlan,
    knapsack_result,
    config: Dict,
    layout: Dict[str, Tuple[float, float]] | None = None,
) -> str:
    graph_config = config["graph"]
    inventory = config["inventory"]
    products = config["products"]
    constraints = config["constraints"]

    nodes = graph_config["nodes"]
    if layout is None:
        layout = compute_layout(nodes)

    width = 900
    height = 640

    def node_value(node: str) -> float:
        value = 0.0
        stock = inventory.get(node, {})
        for product, props in products.items():
            value += stock.get(product, 0) * props["profit_per_unit"]
        return value

    route_edge_set = {
        tuple(sorted(edge)) for edge in _route_edges(plan.final_route)
    }

    edge_data = []
    for origin, target, cost in graph_config["edges"]:
        key = tuple(sorted((origin, target)))
        edge_data.append(
            {
                "source": origin,
                "target": target,
                "cost": cost,
                "in_route": key in route_edge_set,
            }
        )

    node_data = []
    for node in nodes:
        x, y = layout[node]
        stock = inventory.get(node, {})
        node_data.append(
            {
                "id": node,
                "x": x,
                "y": y,
                "inventory": {
                    product: stock.get(product, 0) for product in products.keys()
                },
                "value": node_value(node),
            }
        )

    detours = [
        {
            "anchor": detour.candidate.anchor,
            "node": detour.candidate.node,
            "cost": detour.candidate.detour_cost,
            "goods": detour.goods_picked,
        }
        for detour in plan.detours
    ]

    data = {
        "canvas": {"width": width, "height": height},
        "nodes": node_data,
        "edges": edge_data,
        "final_route": plan.final_route,
        "goods_picked": plan.goods_picked,
        "target_counts": knapsack_result.counts,
        "constraints": constraints,
        "detours": detours,
        "base_cost": plan.base_cost,
        "detour_cost": plan.detour_cost,
        "total_cost": plan.total_cost,
        "profit": knapsack_result.profit,
        "net_profit": knapsack_result.profit - plan.total_cost,
        "verification_cost": plan.verification_cost,
    }

    json_payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    template = Template("""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>ODM Route Visualisation</title>
    <style>
      :root {
        color-scheme: light dark;
        font-family: "Segoe UI", Roboto, sans-serif;
      }
      body {
        margin: 0;
        background: #111827;
        color: #f9fafb;
        display: flex;
        flex-direction: column;
        min-height: 100vh;
      }
      header {
        padding: 1rem 2rem;
        background: #1f2937;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3);
      }
      h1 {
        margin: 0;
        font-size: 1.4rem;
        letter-spacing: 0.02em;
      }
      main {
        flex: 1;
        display: flex;
        gap: 1.5rem;
        padding: 1.5rem;
        box-sizing: border-box;
      }
      #graph-container {
        flex: 1;
        background: #0f172a;
        border-radius: 14px;
        box-shadow: inset 0 0 30px rgba(15,23,42,0.6);
        position: relative;
        overflow: hidden;
      }
      svg {
        width: 100%;
        height: 100%;
      }
      .edge {
        stroke: #4b5563;
        stroke-width: 1.5;
        opacity: 0.7;
      }
      .edge-route {
        stroke: #f97316;
        stroke-width: 3;
        opacity: 0.95;
      }
      .edge-cost {
        fill: #9ca3af;
        font-size: 11px;
        pointer-events: none;
      }
      .node {
        stroke: #f9fafb;
        stroke-width: 2;
      }
      .node-label {
        fill: #f3f4f6;
        font-size: 12px;
        font-weight: 600;
        text-anchor: middle;
        alignment-baseline: middle;
        pointer-events: none;
      }
      .truck {
        fill: #38bdf8;
        stroke: #0ea5e9;
        stroke-width: 2;
        filter: drop-shadow(0 0 6px rgba(56,189,248,0.7));
      }
      .sidebar {
        width: 320px;
        display: flex;
        flex-direction: column;
        gap: 1rem;
      }
      .panel {
        background: #1f2937;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        box-shadow: 0 10px 25px rgba(15,23,42,0.4);
      }
      .panel h2 {
        margin: 0 0 0.5rem;
        font-size: 1.1rem;
        color: #fbbf24;
        letter-spacing: 0.02em;
      }
      .stats {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.4rem 0.9rem;
        font-size: 0.95rem;
      }
      .stats span {
        color: #d1d5db;
      }
      #pickups {
        font-size: 0.95rem;
        line-height: 1.4;
      }
      button {
        padding: 0.6rem;
        border-radius: 8px;
        border: none;
        background: #2563eb;
        color: white;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.2s, background 0.2s;
      }
      button:hover {
        transform: translateY(-1px);
        background: #1d4ed8;
      }
      footer {
        padding: 0.8rem 1.5rem;
        text-align: center;
        font-size: 0.9rem;
        color: #9ca3af;
      }
      .legend {
        display: flex;
        gap: 1rem;
        font-size: 0.85rem;
        color: #d1d5db;
      }
      .legend span {
        display: flex;
        align-items: center;
        gap: 0.3rem;
      }
      .legend div {
        width: 14px;
        height: 14px;
        border-radius: 4px;
      }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
  </head>
  <body>
    <header>
      <h1>ODM Route Visualisation</h1>
    </header>
    <main>
      <div id="graph-container">
        <svg id="graph" viewBox="0 0 $width $height"></svg>
      </div>
      <aside class="sidebar">
        <section class="panel">
          <h2>Summary</h2>
          <div class="stats">
            <span>Profit target</span><span>$profit €</span>
            <span>Travel cost</span><span>$total_cost</span>
            <span>Net profit</span><span>$net_profit €</span>
            <span>Base path cost</span><span>$base_cost</span>
            <span>Detour cost</span><span>$detour_cost</span>
            <span>Verification</span><span>$verification_cost</span>
          </div>
        </section>
        <section class="panel">
          <h2>Progress</h2>
          <div id="status">Starting...</div>
          <div id="pickups"></div>
          <button id="replay">Replay animation</button>
        </section>
        <section class="panel">
          <h2>Constraints</h2>
          <div class="stats">
            <span>Warehouse (t)</span><span>$warehouse_capacity</span>
            <span>Truck units</span><span>$truck_capacity</span>
            <span>Copper ≤</span><span>$ratio × gemstones</span>
          </div>
        </section>
        <section class="panel">
          <h2>Detours</h2>
          <div id="detours"></div>
        </section>
      </aside>
    </main>
    <footer>
      <div class="legend">
        <span><div style="background:#f97316;"></div> Route edges</span>
        <span><div style="background:#38bdf8;"></div> Truck position</span>
        <span>Node colour = profit potential</span>
      </div>
    </footer>
    <script type="application/json" id="visualisation-data">$json_payload</script>
    <script>
      const data = JSON.parse(document.getElementById("visualisation-data").textContent);
      const svg = d3.select("#graph");
      const nodeById = new Map(data.nodes.map(node => [node.id, node]));

      // Colour scale for node value
      const valueExtent = d3.extent(data.nodes, node => node.value);
      const colour = d3.scaleSequential(d3.interpolateYlGn).domain(valueExtent);

      // Draw edges
      svg.append("g")
        .selectAll("line")
        .data(data.edges)
        .join("line")
        .attr("class", edge => edge.in_route ? "edge edge-route" : "edge")
        .attr("x1", edge => nodeById.get(edge.source).x)
        .attr("y1", edge => nodeById.get(edge.source).y)
        .attr("x2", edge => nodeById.get(edge.target).x)
        .attr("y2", edge => nodeById.get(edge.target).y);

      // Edge cost labels
      svg.append("g")
        .selectAll("text")
        .data(data.edges)
        .join("text")
        .attr("class", "edge-cost")
        .attr("x", edge => (nodeById.get(edge.source).x + nodeById.get(edge.target).x) / 2)
        .attr("y", edge => (nodeById.get(edge.source).y + nodeById.get(edge.target).y) / 2 - 6)
        .text(edge => edge.cost);

      // Draw nodes
      svg.append("g")
        .selectAll("circle")
        .data(data.nodes)
        .join("circle")
        .attr("class", "node")
        .attr("r", 20)
        .attr("cx", node => node.x)
        .attr("cy", node => node.y)
        .attr("fill", node => colour(node.value || 0));

      // Node labels
      svg.append("g")
        .selectAll("text")
        .data(data.nodes)
        .join("text")
        .attr("class", "node-label")
        .attr("x", node => node.x)
        .attr("y", node => node.y)
        .text(node => node.id);

      // Truck marker
      const truck = svg.append("circle")
        .attr("class", "truck")
        .attr("r", 10)
        .attr("cx", data.nodes[0]?.x || 0)
        .attr("cy", data.nodes[0]?.y || 0);

      const statusEl = document.getElementById("status");
      const pickupsEl = document.getElementById("pickups");
      const detourEl = document.getElementById("detours");

      if (data.detours.length === 0) {
        detourEl.textContent = "No detours required.";
      } else {
        detourEl.innerHTML = data.detours
          .map(d => '• ' + d.anchor + ' ➝ ' + d.node + ' (cost ' + d.cost.toFixed(1) + ') – pick ' +
            Object.entries(d.goods).map(([p, a]) => p + ': ' + a).join(", "))
          .join("<br/>");
      }

      let collected = {};
      Object.keys(data.target_counts).forEach(key => { collected[key] = 0; });
      const visitedPickups = new Set();

      function formatCollected() {
        return Object.entries(data.target_counts)
          .map(([product, required]) => product + ': ' + collected[product] + '/' + required)
          .join("<br/>");
      }

      function updateSidebar(stepIndex) {
        const nodeId = data.final_route[stepIndex];
        const node = nodeById.get(nodeId);
        const goodsHere = data.goods_picked[nodeId];
        if (goodsHere && !visitedPickups.has(nodeId)) {
          Object.entries(goodsHere).forEach(([product, amount]) => {
            if (collected[product] !== undefined) {
              collected[product] += amount;
            }
          });
          visitedPickups.add(nodeId);
        }
        statusEl.innerHTML =
          '<strong>Step ' + (stepIndex + 1) + '/' + data.final_route.length + '</strong><br/>' +
          'At node <strong>' + nodeId + '</strong>';
        pickupsEl.innerHTML = formatCollected();
      }

      function animateRoute() {
        collected = {};
        Object.keys(data.target_counts).forEach(key => { collected[key] = 0; });
        visitedPickups.clear();

        let step = 0;
        updateSidebar(step);
        truck.attr("cx", nodeById.get(data.final_route[0]).x)
             .attr("cy", nodeById.get(data.final_route[0]).y);

        const interval = setInterval(() => {
          step += 1;
          if (step >= data.final_route.length) {
            clearInterval(interval);
            return;
          }
          const nodeId = data.final_route[step];
          const node = nodeById.get(nodeId);
          const prevNode = nodeById.get(data.final_route[step - 1]);

          truck
            .transition()
            .duration(400)
            .attr("cx", node.x)
            .attr("cy", node.y);

          svg.append("line")
            .attr("class", "edge edge-route")
            .attr("x1", prevNode.x)
            .attr("y1", prevNode.y)
            .attr("x2", prevNode.x)
            .attr("y2", prevNode.y)
            .transition()
            .duration(400)
            .attr("x2", node.x)
            .attr("y2", node.y)
            .attr("opacity", 0.9);

          updateSidebar(step);
        }, 900);

        return interval;
      }

      let currentInterval = animateRoute();

      document.getElementById("replay").addEventListener("click", () => {
        if (currentInterval) {
          clearInterval(currentInterval);
        }
        svg.selectAll(".edge.edge-route")
          .attr("opacity", 0.4);
        currentInterval = animateRoute();
      });
    </script>
  </body>
</html>
""")

    verification = plan.verification_cost if plan.verification_cost is not None else 0.0

    html = template.substitute(
        width=width,
        height=height,
        profit=f"{knapsack_result.profit:.0f}",
        total_cost=f"{plan.total_cost:.0f}",
        net_profit=f"{knapsack_result.profit - plan.total_cost:.0f}",
        base_cost=f"{plan.base_cost:.0f}",
        detour_cost=f"{plan.detour_cost:.0f}",
        verification_cost=f"{verification:.0f}",
        warehouse_capacity=constraints["warehouse_capacity_tons"],
        truck_capacity=constraints["truck_capacity_units"],
        ratio=constraints["copper_to_gemstone_ratio"],
        json_payload=json_payload,
    )
    return html

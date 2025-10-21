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
    """
    Compute a simple force-directed layout using graph structure.
    This is a basic implementation that will be refined by D3.js in the browser.
    """
    # Return None to signal that D3.js should compute the layout
    # This allows for a proper force-directed graph layout
    return None


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

    width = 1200
    height = 800

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
        stock = inventory.get(node, {})
        node_info = {
            "id": node,
            "inventory": {
                product: stock.get(product, 0) for product in products.keys()
            },
            "value": node_value(node),
        }
        # Only add x, y if layout is provided
        if layout is not None:
            x, y = layout[node]
            node_info["x"] = x
            node_info["y"] = y
        node_data.append(node_info)

    detours = [
        {
            "anchor": detour.candidate.anchor,
            "node": detour.candidate.node,
            "cost": detour.candidate.detour_cost,
            "goods": detour.goods_picked,
        }
        for detour in plan.detours
    ]

    def format_factor(value: float) -> str:
        return f"{value:g}"

    ratio_lines: List[str] = []
    if "copper_to_gemstone_ratio" in constraints:
        ratio_lines.append(
            f"copper ≤ {format_factor(constraints['copper_to_gemstone_ratio'])} × gemstones"
        )
    for rule in constraints.get("ratio_constraints", []):
        ratio_lines.append(
            f"{rule['numerator']} ≤ {format_factor(rule['factor'])} × {rule['denominator']}"
        )
    ratio_summary = "<br/>".join(ratio_lines) if ratio_lines else "—"

    data = {
        "canvas": {"width": width, "height": height},
        "nodes": node_data,
        "edges": edge_data,
        "final_route": plan.final_route,
        "goods_picked": plan.goods_picked,
        "target_counts": knapsack_result.counts,
        "constraints": constraints,
        "detours": detours,
        "ratio_constraints": ratio_lines,
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
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", sans-serif;
      }
      body {
        margin: 0;
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        color: #f9fafb;
        display: flex;
        flex-direction: column;
        min-height: 100vh;
      }
      header {
        padding: 1.2rem 2rem;
        background: rgba(31, 41, 55, 0.8);
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        border-bottom: 1px solid rgba(99, 102, 241, 0.2);
      }
      h1 {
        margin: 0;
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
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
        background: rgba(15, 23, 42, 0.6);
        border-radius: 16px;
        box-shadow:
          inset 0 0 60px rgba(15,23,42,0.8),
          0 10px 40px rgba(0,0,0,0.5);
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(99, 102, 241, 0.1);
      }
      svg {
        width: 100%;
        height: 100%;
        cursor: grab;
      }
      svg:active {
        cursor: grabbing;
      }
      .zoom-controls {
        position: absolute;
        top: 1rem;
        right: 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        z-index: 10;
      }
      .zoom-btn {
        width: 40px;
        height: 40px;
        border-radius: 8px;
        border: none;
        background: rgba(31, 41, 55, 0.9);
        backdrop-filter: blur(10px);
        color: #fbbf24;
        font-size: 20px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.3s;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(99, 102, 241, 0.2);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
      }
      .zoom-btn:hover {
        background: rgba(31, 41, 55, 1);
        transform: scale(1.1);
        box-shadow: 0 6px 16px rgba(251, 191, 36, 0.4);
      }
      .zoom-btn:active {
        transform: scale(0.95);
      }
      .edge {
        stroke: #475569;
        stroke-width: 2;
        opacity: 0.5;
        transition: opacity 0.3s, stroke-width 0.3s;
      }
      .edge:hover {
        opacity: 0.9;
        stroke-width: 3;
      }
      .edge-route {
        stroke: #f97316;
        stroke-width: 4;
        opacity: 0.95;
        filter: drop-shadow(0 0 4px rgba(249, 115, 22, 0.6));
      }
      .edge-cost {
        fill: #cbd5e1;
        font-size: 12px;
        font-weight: 600;
        pointer-events: none;
        text-shadow: 0 0 8px rgba(0,0,0,0.8);
      }
      .node {
        stroke: #f9fafb;
        stroke-width: 3;
        cursor: pointer;
        transition: all 0.3s;
        filter: drop-shadow(0 0 8px rgba(0,0,0,0.5));
      }
      .node:hover {
        stroke-width: 5;
        stroke: #fbbf24;
        filter: drop-shadow(0 0 16px rgba(251, 191, 36, 0.8));
      }
      .node-label {
        fill: #f3f4f6;
        font-size: 14px;
        font-weight: 700;
        text-anchor: middle;
        alignment-baseline: middle;
        pointer-events: none;
        text-shadow: 0 0 8px rgba(0,0,0,0.9);
      }
      .truck {
        fill: #38bdf8;
        stroke: #0ea5e9;
        stroke-width: 3;
        filter: drop-shadow(0 0 12px rgba(56,189,248,0.9));
        animation: pulse 2s ease-in-out infinite;
      }
      @keyframes pulse {
        0%, 100% { filter: drop-shadow(0 0 12px rgba(56,189,248,0.9)); }
        50% { filter: drop-shadow(0 0 20px rgba(56,189,248,1)); }
      }
      .sidebar {
        width: 360px;
        display: flex;
        flex-direction: column;
        gap: 1rem;
      }
      .panel {
        background: rgba(31, 41, 55, 0.8);
        backdrop-filter: blur(10px);
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        box-shadow: 0 10px 30px rgba(15,23,42,0.5);
        border: 1px solid rgba(99, 102, 241, 0.15);
      }
      .panel h2 {
        margin: 0 0 0.8rem;
        font-size: 1.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: 0.02em;
      }
      .stats {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.6rem 1rem;
        font-size: 0.95rem;
      }
      .stats span {
        color: #e5e7eb;
      }
      .stats span:nth-child(even) {
        font-weight: 700;
        color: #fbbf24;
      }
      #pickups {
        font-size: 0.95rem;
        line-height: 1.6;
        color: #e5e7eb;
      }
      button {
        padding: 0.8rem;
        border-radius: 10px;
        border: none;
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.3s;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
      }
      button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.6);
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
      }
      button:active {
        transform: translateY(0);
      }
      footer {
        padding: 1rem 1.5rem;
        text-align: center;
        font-size: 0.9rem;
        color: #9ca3af;
        background: rgba(31, 41, 55, 0.5);
        backdrop-filter: blur(10px);
        border-top: 1px solid rgba(99, 102, 241, 0.1);
      }
      .legend {
        display: flex;
        gap: 1.5rem;
        justify-content: center;
        font-size: 0.9rem;
        color: #e5e7eb;
        flex-wrap: wrap;
      }
      .legend span {
        display: flex;
        align-items: center;
        gap: 0.4rem;
      }
      .legend div {
        width: 16px;
        height: 16px;
        border-radius: 4px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
      }
      #detours {
        font-size: 0.9rem;
        line-height: 1.6;
        color: #e5e7eb;
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
        <div class="zoom-controls">
          <button class="zoom-btn" id="zoom-in" title="Zoom In">+</button>
          <button class="zoom-btn" id="zoom-out" title="Zoom Out">−</button>
          <button class="zoom-btn" id="zoom-reset" title="Reset View">⟲</button>
        </div>
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
            <span>Ratios</span><span>$ratio_summary</span>
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
      const width = data.canvas.width;
      const height = data.canvas.height;

      // Create a group for all graph elements that will be zoomed/panned
      const g = svg.append("g");

      // Colour scale for node value
      const valueExtent = d3.extent(data.nodes, node => node.value);
      const colour = d3.scaleSequential(d3.interpolatePlasma).domain(valueExtent);

      // Set up zoom behavior
      const zoom = d3.zoom()
        .scaleExtent([0.1, 10])
        .on("zoom", (event) => {
          g.attr("transform", event.transform);
        });

      svg.call(zoom);

      // Zoom control buttons
      d3.select("#zoom-in").on("click", () => {
        svg.transition().duration(300).call(zoom.scaleBy, 1.3);
      });

      d3.select("#zoom-out").on("click", () => {
        svg.transition().duration(300).call(zoom.scaleBy, 0.7);
      });

      d3.select("#zoom-reset").on("click", () => {
        svg.transition().duration(500).call(
          zoom.transform,
          d3.zoomIdentity
        );
      });

      // Create force simulation for graph layout
      const simulation = d3.forceSimulation(data.nodes)
        .force("link", d3.forceLink(data.edges)
          .id(d => d.id)
          .distance(edge => edge.cost * 15 + 80)
          .strength(0.3))
        .force("charge", d3.forceManyBody().strength(-800))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide().radius(35));

      // Create edge elements
      const edgeGroup = g.append("g");
      const edges = edgeGroup
        .selectAll("line")
        .data(data.edges)
        .join("line")
        .attr("class", edge => edge.in_route ? "edge edge-route" : "edge");

      // Edge cost labels
      const edgeLabelGroup = g.append("g");
      const edgeLabels = edgeLabelGroup
        .selectAll("text")
        .data(data.edges)
        .join("text")
        .attr("class", "edge-cost")
        .text(edge => edge.cost);

      // Create node group for nodes
      const nodeGroup = g.append("g");
      const nodes = nodeGroup
        .selectAll("circle")
        .data(data.nodes)
        .join("circle")
        .attr("class", "node")
        .attr("r", 25)
        .attr("fill", node => colour(node.value || 0))
        .call(d3.drag()
          .on("start", dragstarted)
          .on("drag", dragged)
          .on("end", dragended));

      // Add tooltip on hover
      nodes.append("title")
        .text(node => {
          const inv = Object.entries(node.inventory)
            .filter(([_, count]) => count > 0)
            .map(([product, count]) => product + ': ' + count)
            .join(', ');
          return node.id + '\\nValue: ' + (node.value || 0).toFixed(0) + '€\\n' +
                 (inv || 'No inventory');
        });

      // Node labels
      const labelGroup = g.append("g");
      const labels = labelGroup
        .selectAll("text")
        .data(data.nodes)
        .join("text")
        .attr("class", "node-label")
        .text(node => node.id);

      // Truck marker
      const truck = g.append("circle")
        .attr("class", "truck")
        .attr("r", 12);

      const nodeById = new Map(data.nodes.map(node => [node.id, node]));

      // Update positions on simulation tick
      simulation.on("tick", () => {
        edges
          .attr("x1", edge => edge.source.x)
          .attr("y1", edge => edge.source.y)
          .attr("x2", edge => edge.target.x)
          .attr("y2", edge => edge.target.y);

        edgeLabels
          .attr("x", edge => (edge.source.x + edge.target.x) / 2)
          .attr("y", edge => (edge.source.y + edge.target.y) / 2 - 8);

        nodes
          .attr("cx", node => node.x)
          .attr("cy", node => node.y);

        labels
          .attr("x", node => node.x)
          .attr("y", node => node.y);
      });

      // Drag functions
      function dragstarted(event) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
      }

      function dragged(event) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
      }

      function dragended(event) {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
      }

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
          .map(([product, required]) => {
            const progress = collected[product] >= required ? '✓' : '';
            return '<div>' + product + ': <strong>' + collected[product] + '/' + required + '</strong> ' + progress + '</div>';
          })
          .join("");
      }

      function updateSidebar(stepIndex) {
        const nodeId = data.final_route[stepIndex];
        const node = data.nodes.find(n => n.id === nodeId);
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

        // Wait for simulation to stabilize before starting animation
        simulation.alpha(0.3).restart();
        setTimeout(() => {
          simulation.stop();

          let step = 0;
          updateSidebar(step);
          const startNode = data.nodes.find(n => n.id === data.final_route[0]);
          truck.attr("cx", startNode.x).attr("cy", startNode.y);

          const interval = setInterval(() => {
            step += 1;
            if (step >= data.final_route.length) {
              clearInterval(interval);
              return;
            }
            const nodeId = data.final_route[step];
            const node = data.nodes.find(n => n.id === nodeId);
            const prevNode = data.nodes.find(n => n.id === data.final_route[step - 1]);

            truck
              .transition()
              .duration(600)
              .attr("cx", node.x)
              .attr("cy", node.y);

            // Animate route path
            g.append("line")
              .attr("class", "edge edge-route")
              .attr("x1", prevNode.x)
              .attr("y1", prevNode.y)
              .attr("x2", prevNode.x)
              .attr("y2", prevNode.y)
              .transition()
              .duration(600)
              .attr("x2", node.x)
              .attr("y2", node.y);

            updateSidebar(step);
          }, 1200);

          return interval;
        }, 3000);
      }

      // Start animation after layout stabilizes
      setTimeout(() => {
        animateRoute();
      }, 3000);

      document.getElementById("replay").addEventListener("click", () => {
        // Clear animated routes
        g.selectAll(".edge.edge-route").remove();

        // Re-add static route edges
        data.edges.forEach(edge => {
          if (edge.in_route) {
            g.insert("line", ":first-child")
              .attr("class", "edge edge-route")
              .attr("x1", edge.source.x)
              .attr("y1", edge.source.y)
              .attr("x2", edge.target.x)
              .attr("y2", edge.target.y);
          }
        });

        animateRoute();
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
        ratio_summary=ratio_summary,
        json_payload=json_payload,
    )
    return html

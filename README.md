# Optimization and Decision Making – Challenge 1

This repo implements a deterministic, exact workflow for Exercise 1.1 of the ODM course.  
It follows the lexicographic objective specified in the sheet:

1. **Maximise profit** under warehouse, truck, and coupling constraints.
2. **Minimise travel cost** among A→N tours that realise that profit.

The solution keeps all instance data in YAML (`problem_instance.yaml`) so larger or alternate problems can be swapped in without code changes.

## Project structure

| File | Purpose |
| --- | --- |
| `problem_instance.yaml` | Graph, product definitions, inventory per node, and global constraints. |
| `graph.py` | Lightweight undirected graph wrapper with Dijkstra and path reconstruction. |
| `knapsack.py` | Exhaustive integer search for the profit-maximising product mix subject to constraints. |
| `routing.py` | Backbone shortest path, detour selection via DP, and brute-force verification of detour optimality. |
| `main.py` | Orchestrates the two phases and prints a detailed summary. |

## Dependencies

- Python 3.11+
- `pyyaml` (install with `pip install pyyaml`)

No external solvers or randomness are used.

## Running the solver

```bash
python main.py
```

By default the program reads `problem_instance.yaml` in the current directory.  
Use `--config /path/to/other.yaml` to target a different instance.

### Output overview

The script prints:

- The profit-maximising product mix (from the knapsack phase).
- The backbone shortest path A→N, any detours taken, and their pickup bundles.
- A verification line where a brute-force search certifies the detour cost is minimal for the required pickups.
- The final route, total travel cost, net profit, and per-location pickups.

Example snippet:

```
Detours:
  - A detour to C … goods [gemstones: 1]
  - F detour to K … goods [gemstones: 1, copper: 3]
Verification: brute-force search confirmed detour cost 4.00 (best possible 4.00).
```

## Extending or adapting

- **New instances:** copy `problem_instance.yaml`, adjust nodes/edges/inventory/constraints, and pass the new file via `--config`.
- **Alternate objectives:** the code is structured so you can plug in different routing heuristics or add fallback logic if the lexicographic target mix proves infeasible.
- **Debugging:** enable prints in `routing.verify_detour_optimality` or add logging to inspect the brute-force search.

For coursework write-ups, the combination of the deterministic knapsack search, the DP detour planner, and the brute-force certification provides a complete proof that the emitted solution is lexicographically optimal under the model encoded in YAML.

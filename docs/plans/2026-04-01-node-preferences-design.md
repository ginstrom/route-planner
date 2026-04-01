# Node Preferences Design

## Goal

Allow planner queries to express soft node-avoidance preferences such as "don't visit B unless there is no other way" and have the planner choose the best feasible solver candidate that satisfies those preferences when possible.

## Scope

- Support node-level soft preferences only.
- First release supports avoid-node language and deterministic selection behavior.
- Do not change graph editing, hard feasibility rules, or candidate enumeration semantics.
- Do not rely on the LLM to make the final route choice.

## Architecture

- Parsing: extend the planner request parser to capture soft node preferences in the formal request model.
- Solving: keep candidate generation unchanged so the solver still enumerates feasible routes from the graph.
- Selection: add a deterministic preference-ranking layer that evaluates accepted candidates before choosing the final route.
- Explanation: include preference-evaluation facts in planner trace payloads so route explanations can justify why a more expensive route was selected.

## Data Model

Extend the direct solve request contract with an `avoid_nodes: list[str]` field.

Semantics:

- Nodes in `required_visits` remain hard requirements.
- Nodes in `avoid_nodes` are soft constraints.
- If a node appears in both lists, the hard requirement wins and the route may include that node.
- Empty `avoid_nodes` preserves current behavior.

## Candidate Ranking

Use lexicographic ranking over accepted candidates:

1. Fewest visited avoid nodes.
2. Lowest total cost.
3. Existing route ordering tie-breaker.

This means a route that avoids every avoided node beats any cheaper route that includes one of them. Only when every feasible candidate includes an avoided node does the planner select the cheapest route among those preference-violating candidates.

## Parsing Behavior

The parser should recognize simple avoid-node phrasing from natural-language queries, including patterns equivalent to:

- "don't visit B unless there is no other way"
- "avoid B"
- "prefer not to go through B"

The first pass should remain conservative:

- extract only node IDs that exist in the graph,
- store them in `avoid_nodes`,
- avoid over-parsing more general language until there are tests for it.

## Trace and Explanation

The solve trace payload should include preference facts for each accepted candidate and the selected route, including:

- which avoid nodes were visited,
- how many avoid-node violations each candidate has,
- the selection basis for the chosen route.

This allows explanation responses to say that a route was selected because it avoided `B`, even when another feasible route was cheaper.

## Error Handling

- Missing or unknown node references in avoid-language should not create invalid preferences.
- If parsing finds no avoid nodes, planner behavior falls back to current cheapest-route selection.
- If no feasible route exists at all, the result remains `INFEASIBLE`.
- If all feasible routes include an avoided node, return `SUCCESS` with the best available route and explain that avoiding the node was impossible.

## Testing Strategy

- Parser tests for extracting `avoid_nodes` from planner queries.
- Direct solver tests verifying preference-based route selection.
- Planner API tests verifying end-to-end NL query behavior, candidate traces, and explanation prompts.
- Regression tests proving old requests without preferences still return the same route as before.

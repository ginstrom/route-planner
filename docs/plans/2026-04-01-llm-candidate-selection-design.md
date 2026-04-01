# LLM Candidate Selection Design

## Goal

Allow the planner to generate solver candidates deterministically and then let the LLM choose the best candidate for the user's natural-language request, while persisting that choice in the trace for later explanation.

## Scope

- Planner mode only.
- Direct solve remains deterministic and solver-owned.
- The solver still owns feasibility and candidate generation.
- The LLM chooses only among solver-produced candidates.
- Candidate selection inputs and outputs are stored in the trace.

## Architecture

Planner runs should follow this sequence:

1. Parse the user query into the hard route requirements needed for solving.
2. Call the solver to generate accepted and rejected candidates.
3. Extract the accepted candidates and provide all of them to the LLM alongside the original query.
4. Require the LLM to choose exactly one candidate from that list.
5. Verify the returned choice matches a real solver candidate.
6. Return the verified chosen candidate as the planner result.

This keeps solver guarantees intact while shifting preference interpretation to the LLM. The LLM does not invent routes or alter graph facts; it only selects from a bounded set of solver-evaluated options.

## Candidate Selection Contract

The LLM input should include:

- the original planner query,
- the parsed hard solve request,
- the candidate list,
- a strict instruction to return one exact candidate choice from the provided list.

Each candidate should include at least:

- stable candidate identifier,
- route as a node list,
- total cost,
- acceptance status.

The backend should accept only a choice that maps exactly to one of the accepted candidates. If the LLM response is malformed or names a route outside the candidate set, planner behavior should follow the configured planner mode:

- `anthropic`: fail the run,
- `anthropic_with_fallback`: log the error and fall back to the deterministic cheapest accepted candidate,
- `local`: use the local deterministic fallback path.

## Trace Design

The trace should record the candidate-selection phase explicitly after `planner.get_candidates`.

Add a new trace step such as `planner.choose_candidate` that stores:

- the original user query,
- the accepted candidate list presented to the LLM,
- the chosen candidate,
- the raw or normalized LLM decision payload,
- a short LLM rationale or summary,
- backend verification result,
- whether a fallback was used.

The solve trace should continue to store the full candidate summary from the solver so later explanations can distinguish:

- what the solver generated,
- what the LLM saw,
- what the LLM selected,
- whether backend verification or fallback logic altered the outcome.

## Error Handling

- If there are no accepted candidates, keep existing infeasibility behavior and skip candidate choice.
- If there is one accepted candidate, still send it to the LLM for a uniform trace shape.
- If the LLM returns a candidate not present in the accepted list, reject it and follow planner-mode fallback rules.
- If the LLM returns ambiguous output, treat it as a selection failure.

## Explainability

Explanations should be grounded in stored trace facts:

- the original query,
- the solver candidate list,
- the recorded LLM choice,
- the recorded rationale,
- fallback or verification outcomes when applicable.

This allows later explanation responses to say that the solver produced a bounded list of routes and the LLM selected one of them in response to the user’s instructions.

## Testing Strategy

- Planner tests for successful LLM candidate choice when multiple accepted candidates exist.
- Planner tests ensuring the LLM sees all accepted candidates.
- Planner tests for malformed or invalid LLM choices and planner-mode fallback behavior.
- Regression tests proving direct solve behavior does not change.

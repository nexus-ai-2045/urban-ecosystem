# Model Change Proposal

## Decision Required

`true`

## Topic

Short name of the proposed geography, environment, physics, policy, or infrastructure model change.

## Requesting Role

`geography-modeler` / `environment-modeler` / `physics-modeler` / `policy-infra-modeler` / other

## Current Model

Describe the current implementation and where it lives.

Relevant files:

- `path/to/file.py`
- `scenarios/name/scenario.yaml`

## Proposed Change

Describe the proposed model change.

## Rationale

Explain why this change is needed for the experiment.

## Research or Scenario Basis

List the memo, roadmap, or public source used as basis. Do not encode unstable mission dates directly into implementation unless separately approved.

## Implementation Scope

Allowed write paths:

- `path/to/file.py`

Out of scope:

- `core/` changes unless approved
- `materials/` changes

## Parameterization

Prefer abstract parameters over hard-coded institutional or mission-specific assumptions.

```yaml
example_parameter: value
```

## Metrics Impact

List new or changed metrics.

## Compatibility Impact

Explain expected impact on:

- `water_exploration`
- `south_pole_survival_survey`
- existing tests
- JSONL logs
- `summary.json`

## Alternatives

1. Minimal alternative.
2. More complete alternative.
3. Defer.

## Risks

- Risk 1
- Risk 2

## Human Decision Needed

- Approve / reject / revise the model assumption.
- Approve metric changes.
- Approve experiment budget if validation requires long run.

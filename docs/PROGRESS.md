# PROGRESS

Living status of the build. Claude reads this at the start of every session and updates it at the end of every build step. Keep entries short. Newest first in every log.

## Current status
- Phase: v0.1 Core
- Current step: 1. Synthetic source extracts
- State: not started
- Last verified green: never (`make build && make test` not yet runnable)

## Build checklist (v0.1)
Tick a step only when it runs end to end and its checks pass.

- [ ] 1. Synthetic source extracts (`example/generate.py`)
- [ ] 2. dbt staging + marts + data tests
- [ ] 3. Verify MetricFlow on DuckDB, then semantic models and metrics
- [ ] 4. Decision records (DR-001 to DR-005 + TEMPLATE)
- [ ] 5. Reference computations + golden questions + runner
- [ ] 6. Governance lint, registry, CODEOWNERS, PR template
- [ ] 7. Demos (`make demo-conflict`, `make demo-drift`)
- [ ] 8. Playbook + adoption guide
- [ ] 9. README + CHANGELOG
- [ ] 10. CI

## Definition of done (v0.1)
Copied from SPEC section 19. Tick when verified on a fresh clone.

- [ ] `make setup && make data && make build && make test` passes in under 10 minutes
- [ ] `make demo-conflict` prints four different net revenue numbers and names the DR
- [ ] `make demo-drift` fails golden questions for the right reason, then restores everything
- [ ] `make lint` fails clearly on: removed owner, broken DR link, certified metric with no golden question
- [ ] Warehouse switch documented, needs no model changes
- [ ] No real company names or rules, no em dash character anywhere

## Later phases (locked until the owner says go)
- [ ] v0.2 Agent-ready: MCP server + agent eval harness
- [ ] v0.3 Actions: action contract, shadow table, approval, write-back, audit log

## Implementation decisions
Technical choices made during the build that are not already in SPEC.md. One line each: date, decision, why. If a decision changes the spec, say so and ask the owner first.

| Date | Decision | Why |
| --- | --- | --- |

## Open questions and blockers
Things that need the owner's input. Remove an item once it is answered, and record the answer under Implementation decisions.

- Repo name not final yet. Use the current folder name until the owner confirms.

## Session log
One entry per working session. Format:

```
### YYYY-MM-DD
- Done: what was built or changed
- Verified: which commands ran green
- Next: the very next action
- Notes: anything surprising, worked around, or worth knowing next time
```

(no sessions yet)
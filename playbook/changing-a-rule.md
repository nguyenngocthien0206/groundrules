# Changing a rule

Rules change. Stores open, a new tax applies, someone finds a case nobody
thought of. The goal is not to stop change but to make every change
deliberate, reviewed by the right people, and visible to everyone who uses
the number. This page walks through one real change in this repo: the
sell-through fix in pull request #9, which created DR-011.

## 1. Someone notices a wrong number
The first Power BI export asked for sell-through by store and month for
every store, something no golden question had done. NW030, a store that
opened on 1 September 2026, came back at **-20.43** for September: it had
received 590 units and sent 1,012 to other stores, so the "net received"
denominator was -422. For August it read **0**: its opening stock arrived
the day before it opened and it sold nothing.

The golden questions had all passed. They covered NW014, the chain and one
category, all trading for months. A green test suite says the cases you
wrote down work; it says nothing about the ones you did not.

The person who noticed did not fix the formula on the spot. A wrong number
is a question for the metric's owner, not for whoever has the editor open.

## 2. The owner decides, and a new record says why
Sell-through belongs to supply chain (`group: supply_chain_ops`), so the
Head of Supply Chain decided. Options went on the table: hide new stores on
the dashboard only, leave opening stock out of "received", clamp at zero,
or return no value plus a warning. They chose the last one, because the
dashboard-only fix would leave an agent answering "0" with no warning.

That decision went into a **new** record, [DR-011](../decisions/DR-011.md),
with `supersedes: DR-009`. The old record [DR-009](../decisions/DR-009.md)
was not edited except for two front matter fields, `status: superseded` and
`superseded_by: DR-011`. Anyone reading the history can see the old rule,
the new rule and why it changed. The lint checks that the two records point
at each other and that no metric still links a superseded record.

## 3. The metric changes version
In `dbt/models/semantic/metrics_supply_chain.yml`:
- the expression returns no value when net received is zero or negative
- `version: 1` became `version: 2`
- `certified_on` moved to the day the owner approved
- `decision` now points to DR-011
- `agent_notes` tell an agent to say "no value", never 0

The independent reference SQL changed the same way, written from DR-011's
text. Two paths, same rule, written separately: that is what lets the
golden questions catch a mistake in either.

## 4. Golden questions record the new behavior
Two new questions pin the cases that started it: `GQ-SELL-04` (NW030
September, no value) and `GQ-SELL-05` (NW030 August, 0 with a `new_store`
caveat). `make golden-freeze` recomputed expected values, and the diff
showed one more thing: `GQ-SELL-02` and `GQ-SELL-03`, chain-level
questions, now expect `new_store:NW029, new_store:NW030` caveats. Their
numbers did not move; the chain total includes both new stores' opening
stock, and the answer now says so.

That diff is the part reviewers must read. A moved expected value is a
moved number on someone's dashboard. CODEOWNERS sent
`golden/expected/sell_through.yml` to supply chain, and the pull request
listed both questions under "needs sign-off".

## 5. The lint blocks until everything agrees
With the metric at v2, `make lint` failed on two files nobody had touched:

```
ERROR   powerbi     ...Sell-through by store.tmdl: measure 'Sell-through rate by store' says sell_through_rate v1, but the certified version is v2
ERROR   registry    governance/registry.md is out of date: run `make registry`
```

The Power BI measure description and the catalog page still described the
old rule. The pull request could not go green until both were updated. This
is the safety net working: a rule cannot change in one place while a
dashboard or the catalog still describes the old one.

## 6. Review and merge
`make affected BASE=origin/main` lists the touched metrics and the
dashboards that read them, for the pull request description. The PR
template asks for exactly what happened above:

| PR template item | In PR #9 |
| --- | --- |
| Decision record | DR-011, superseding DR-009 |
| Golden questions added or updated | GQ-SELL-04, GQ-SELL-05 added; GQ-SELL-02, GQ-SELL-03 caveats moved |
| Expected values re-frozen and diff reviewed | `golden/expected/sell_through.yml` only |
| Registry regenerated | yes, v2, recertify by 2027-04-24 |
| Version bumped, `certified_on` updated | v1 to v2, 2026-10-26 |
| Business owner approved | supply chain, through CODEOWNERS |
| Exposure owners told the number moves | the Power BI report, which depends on `sell_through_rate` |

## The short version
1. A wrong number goes to the metric's owner.
2. The owner decides; a new decision record supersedes the old one.
3. Metric and reference change separately, from the record's text.
4. Golden questions pin the new cases; the freeze diff gets signed.
5. Fix whatever the lint says still describes the old rule.
6. Merge with the owner's approval and tell the people whose dashboards move.

It took one pull request. Without the records, the same fix
would have been a one-line formula change that nobody reviewed, and nobody
would know a year later why sell-through is sometimes blank.

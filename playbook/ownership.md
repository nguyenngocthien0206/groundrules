# Ownership

A number without an owner gets defined by whoever touched it last. This
page says who owns what, how that is written down, and how Git enforces it,
so ownership survives reorganizations and people leaving.

## Two kinds of owner
| | Business owner | Data owner |
| --- | --- | --- |
| Owns | what the number means | that the data behind it is right |
| Example | Head of Supply Chain for `available_stock` | Data platform for `fct_inventory_batch` |
| Decides | thresholds, exclusions, which reading of "received" counts | how data is loaded, typed, deduplicated, joined |
| Signs | decision records, golden questions, recertification | contracts, source freshness, data tests |
| Gets paged when | a golden question fails on meaning | a build, contract or freshness check fails |

The split matters because the two fail differently. A wrong threshold is a
business decision made badly or silently; a duplicated POS upload is a data
problem. Mixing them up sends the problem to someone who cannot fix it.

Owners are teams and roles, never a person's name. People move; the role
"Head of Supply Chain" stays.

## Where ownership is written
dbt already has the field for it, so this repo uses that rather than a
custom one:

- **Business owner** = the metric's dbt `group`. Every governed metric has
  one, and the lint fails without it.
- **Data owner** = the `group` of the mart behind the semantic model,
  usually `data_platform`.
- **The GitHub team** for each group lives in one place:
  `config.meta.github_team` in `dbt/models/groups.yml`.

`.github/CODEOWNERS` maps files to those teams, and the lint checks that the
two agree. Change a team handle in `groups.yml` without changing CODEOWNERS
and CI fails.

## How Git enforces it
CODEOWNERS only works with "Require review from Code Owners" turned on in
branch protection. With it on, a pull request that touches a rule file
cannot merge until the owning team approves.

One GitHub behavior shapes the whole setup: when a CODEOWNERS line lists
several teams, an approval from **any one** of them is enough. So if finance
and supply chain shared one rule file, finance could approve a change to a
supply chain rule alone. That is why this repo:

- keeps one owning team per rule file (`metrics_finance.yml`,
  `metrics_supply_chain.yml`, one expected-values file per domain), and
- has the lint require that a rule file's owners are **exactly** the teams
  of the metrics whose rules it holds, no more.

The one shared rule file, `fct_sales.yml`, holds finance's revenue building
blocks and supply chain's units sold, so it lists both, and either can
approve. That is a trade-off written down in CODEOWNERS, not an accident.
Where every listed team must approve, use a GitHub ruleset that requires
each team instead.

Decision records and golden question files must reach every team they
cover, so a record that settles a dispute between three teams lists all
three.

## RACI template
Copy this into your team wiki and fill in your roles. One row per
recurring activity, not per metric.

| Activity | Business owner | Data owner | Analyst | Data lead |
| --- | --- | --- | --- | --- |
| Decide what a metric means | A | C | C | R |
| Write the decision record | A | C | C | R |
| Encode the metric | I | C | C | R (analytics engineer) |
| Write golden questions | A (signs) | I | R | C |
| Keep the data behind it right | I | A, R | I | C |
| Recertify | A, R | C | C | I |
| Respond to a failed golden question | A | R if data, C if meaning | C | R (triage) |

R = does the work, A = accountable, signs off, C = consulted, I = informed.

If a cell has nobody to put in it, that is the finding: a metric whose
business owner is "nobody" should not be certified yet.

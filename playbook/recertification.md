# Recertification

A certified metric is a promise: the owner looked at this definition and it
still matches how the business works. Businesses change, so the promise has
an expiry date. Recertification is the owner looking again, on a schedule,
before the definition quietly drifts away from reality.

## How often
Each certified metric carries `certified_on` and `recertify_every_days` in
its `meta`. In this repo finance's metrics recertify every 90 days and
supply chain's every 180. A good default is to tie it to a review the
business already holds:

- **Quarterly business review** for numbers leadership looks at every month
  (revenue, margin). Recertify every second review, or every review if the
  business is changing fast.
- **Twice a year** for operational numbers with stable rules (stock, cover).
- **Right away** after a reorganization, a new system, or an acquisition.

Riding on an existing meeting matters more than the exact number of days.
A separate "metric review meeting" is the first one people skip.

## What the owner checks
Ten minutes per metric, with the data lead:

1. Read the metric's description and the linked decision record. Is the
   rule still true? Did anything in the business change: new store
   formats, new tax rules, a new channel?
2. Read the golden questions. Do the answers still look right to someone
   who runs the business?
3. Look at `make affected` for anything new that reads the metric. A
   dashboard nobody knew about is worth knowing about.

If all three hold, bump `certified_on` to today in a small pull request.
The owner approves it like any other change. If not, the metric needs a
[rule change](changing-a-rule.md), not a recertification.

## Where to see what is due
`governance/registry.md` lists every governed metric with its owner,
version, status, decision record and a **recertify by** date. Generate it
with `make registry`; the lint fails if it is out of date, so it always
matches the definitions. It is the page to put in front of business owners
before the review.

## What the lint does with stale metrics
`make lint` takes a `--today` date. By default it is the snapshot date of
this demo, so results do not change with the calendar. In a real setup, CI
passes the real date:

```
make lint LINT_ARGS="--today 2027-01-04"
```

A metric past its recertify-by date is a **warning**:

```
WARNING staleness   metric net_revenue was due for recertification on 2026-12-09 (owner: finance)
```

Add `--fail-on-stale` to turn the warning into an error once the routine
is settled. Start with warnings: failing every pull request in the repo
because one finance metric is a week late punishes the wrong people.

## A stale metric is not a deleted metric
A stale metric still answers, and its number is still the best one the
company has. Stale means "nobody has confirmed this lately", and that is
what the warning says to anyone reading the registry. Retiring a metric is
a separate decision: set `status: deprecated` with `replaced_by` pointing
at its successor, so people and agents asking for it are sent to the right
place (see `revenue_v1` and [DR-005](../decisions/DR-005.md)).

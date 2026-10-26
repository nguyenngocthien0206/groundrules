# Adopt in 30 days

Thirty days is enough to put ten numbers under governance: owned, written
down, tested and protected in Git. Not every number; ten. The point of the
first month is to prove the routine works on the numbers that matter, so
the rest can follow at the team's own pace.

Each week names its deliverable and whose hours it costs. The calendar is a
plan, not a promise: if week 2 runs long because finance and operations
genuinely disagree about revenue, that disagreement was the reason to start.

## Week 1: pick ten numbers and find their owners
**Deliverable:** a list of ten metrics, each with a business owner who has
said yes.

- Take the numbers leadership actually looks at: the monthly business
  review deck, the CEO's dashboard, the bonus scorecard. Count how often
  each is looked at, not how important it sounds.
- For each, find every place it is computed today (dashboards, spreadsheets,
  SQL in a notebook) and write down the answers side by side, the way
  `make demo-conflict` does for revenue. The gaps are your agenda for
  week 2.
- Name the business owner by role and ask them. A metric whose owner will
  not commit an hour drops off the list; replace it with the next one.
- Create the dbt `groups` and GitHub teams for those owners (see
  [Ownership](../playbook/ownership.md)).

**Hours:** mostly the data lead and one analyst. Owners: a 15-minute
conversation each.

## Week 2: decide, and write it down
**Deliverable:** one decision record per metric, approved by its owner.

- Run [definition sessions](../playbook/running-a-definition-session.md),
  grouped by owner so the CFO sits through one session for three finance
  numbers, not three sessions.
- Draft the records within two days of each session, from the
  [template](../decisions/TEMPLATE.md), each with a worked example built
  from real rows.
- In parallel, harvest last quarter's analyst questions for these metrics
  (see [From analyst answers to golden questions](../playbook/from-analyst-answers-to-golden-questions.md)).

**Hours:** this is the expensive week for business owners: about an hour
each in a session and half an hour reviewing records.

## Week 3: encode the metrics and the proof
**Deliverable:** ten metrics in the semantic layer, and golden questions
that pass.

- Write each metric in `dbt/models/semantic/` with its rule as a filter or
  expression, its group, and the governance `meta` (version, status,
  certified_on, recertify_every_days, decision, agent_notes).
- Write the independent reference SQL in `golden/reference/`, from the
  decision records and not from the dbt models. Ideally a different person
  writes it than the one who encoded the metric.
- Write two or three golden questions per metric, get them signed, run
  `make golden-freeze`, then `make golden` until both paths agree. Every
  disagreement is either a bug or a rule that the record left ambiguous;
  the second kind goes back to the owner.

**Hours:** analytics engineers and analysts. Owners: signing the questions,
about 15 minutes per metric.

## Week 4: let Git enforce it
**Deliverable:** a pull request that changes a governed number cannot merge
without its owner.

- Fill in `.github/CODEOWNERS` from your groups, then run `make lint` until
  it passes. It checks that every metric has an owner and a record, that
  every certified metric has a golden question, and that CODEOWNERS matches
  the groups.
- Turn on branch protection: required status checks (lint, golden, tests)
  and "Require review from Code Owners".
- Add the pull request template, so every change says which records and
  questions it touches and pastes `make affected`.
- Generate `governance/registry.md` with `make registry` and send it to the
  owners. It is the one page that says what exists, who owns it and when
  it is due for review.
- Rehearse once: make a deliberate small rule change through
  [Changing a rule](../playbook/changing-a-rule.md) and watch every check
  fire.

**Hours:** the data lead and a platform engineer for a day or two.

## At the end of the month
- Ten numbers with one definition each, an owner, a written reason and
  tests that fail when someone changes the rule silently.
- A routine people have done once, not a document they have read.
- A list of the next ten, and a calendar entry for the first
  [recertification](../playbook/recertification.md).

What you do not have yet: the long tail of metrics, or every dashboard
pointed at certified numbers. That is fine. The routine is what scales; the
first ten numbers are how you earn the trust to run it on the next fifty.

# Cost and roles

The tooling here is free and mostly already in place: dbt, MetricFlow, Git,
a CI runner. The real cost is people's hours, and most of those are hours
of business experts who have other jobs. Budget for them explicitly, or the
work stalls in week 2 waiting for a meeting that never gets scheduled.

## Where the hours go, per metric
These are starting assumptions for a metric with one real disagreement
behind it. Calibrate them after your first five metrics; a number nobody
argues about takes half of this, and a number with three competing
definitions can take twice as much.

| Activity | Who | Hours |
| --- | --- | --- |
| Prep: find every current answer, put them side by side | analyst | 2 |
| Definition session | business owner, data owner, analyst, one person per dissenting team, facilitator | 1 each, about 5 in total |
| Draft the decision record | facilitator (data lead or analyst) | 1.5 |
| Review and approve the record | business owner | 0.5 |
| Encode the metric in the semantic layer | analytics engineer | 2 to 4 |
| Write the reference SQL | a second analyst or engineer | 1 to 2 |
| Write two or three golden questions | analyst | 1 |
| Sign the golden questions | business owner | 0.25 |
| Pull request review | owner team, data platform | 0.5 |

That is roughly **14 to 17 hours per metric**, of which the business owner
spends about **2**. For the first ten metrics: around 150 hours in total,
about 20 of them business owners' time, spread across a month. After
that, recertification costs each owner about ten minutes per metric per
cycle.

Put the 20 owner hours in front of leadership as the cost. It is the number
that decides whether this happens, and it is small next to the hours
already spent reconciling conflicting dashboards.

## Who to involve
- **Business owners** of the first ten numbers. Roles, not names: the person
  accountable for the number in the business, not the person who builds
  the report.
- **One senior analyst** per domain: the person people ask today. Their
  answers become the golden questions, and their involvement is how you
  avoid building something they quietly route around.
- **An analytics engineer** who knows the dbt project, to encode metrics and
  keep the semantic layer clean.
- **A data lead** who runs the sessions, chases sign-offs and owns the
  routine. This is the role that makes or breaks adoption.
- **Platform or DevOps**, for a day, to turn on branch protection and CI.

## Who not to involve, yet
- **Every dashboard owner.** Start with the numbers, not the dashboards.
  Dashboards move to certified numbers one at a time, once the numbers
  exist.
- **A steering committee.** Ten numbers do not need one. If the routine
  works, it will get one later for the right reasons.
- **Vendors.** Nothing in the first month needs a new tool.

## When an owner never shows up
It will happen. Three moves, in order:

1. **Shrink the ask.** Offer 20 minutes and a pre-filled record: "here are
   the two options and the rows that differ; pick one". Most owners say yes
   to a decision that is already framed.
2. **Escalate the gap, not the person.** Show leadership the conflicting
   numbers side by side and the empty "business owner" cell. A visible gap
   in a list of ten gets filled.
3. **Drop the metric from the first ten.** Do not certify a number nobody
   owns, and do not let the data team decide a business rule by default. An
   uncertified number with an honest status is better than a certified one
   with a made-up owner.

## What it saves
Harder to count, so be careful promising it. What to look for after a few
months: fewer "which number is right" threads, new analysts finding answers
in the records instead of asking, and changes that land with their reasons
attached. Count the first one before you start, so you have a baseline. The one
saving this repo can show directly is the drift demo: a silent rule change
that every formal check passes, caught by a golden question before it
reached a dashboard.

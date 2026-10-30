# A new metric

Someone asks for a dashboard, and it needs a number the company has never
defined. This is the cheapest moment there will ever be to get the number
right: nobody is used to it yet, no report depends on it, and the owner can
decide the awkward cases before they turn into habits. Skip it, and in a
year the number is one more rule that lives in one analyst's head.

The example below is hypothetical, to show the steps: operations asks for a
dashboard of stockout rate by store. Nothing in this repo defines that
metric.

## 1. Take the request, not the spec
Before anyone writes YAML, ask the person who wants the dashboard three
things:

- **What decision does it serve?** "Which stores to restock first" and
  "which store managers to talk to" need different numbers.
- **Who will read it, and how often?** That sets who owns the number and
  how much its edge cases matter.
- **What do they call the numbers?** Write down their words. "Stockout
  rate" may mean the share of SKUs at zero, the share of days with a zero,
  or lost sales; each is a different metric.

## 2. Check the registry first
Open [`governance/registry.md`](../governance/registry.md): every governed
metric, its owner, version and status. One of three things is true.

- **The number already exists as a certified metric.** The dashboard needs
  a slice of it, not a new definition: add a saved query in the owner's
  `saved_queries_<owner>.yml` and follow [BI tools](../adoption/bi-tools.md).
  This is how a company avoids two "revenue" metrics that differ by a
  filter.
- **It is close to an existing metric, but would change what that metric
  means.** That is a rule change, with a new decision record and a version
  bump: follow [Changing a rule](changing-a-rule.md).
- **It is really new.** Carry on.

## 3. Find the owner and settle the edge cases
The owner is the team that decides what the number means and answers for
it, not the team that builds it ([Ownership](ownership.md)). For a stockout
rate that is probably supply chain.

Then settle the cases nobody thinks of until a dashboard shows them. For
almost any retail number, ask:

- returns, VAT and refunds: in or out, and in which period?
- stores that opened recently, or whose data arrives late: in, out, or
  flagged with a caveat?
- units: base units, boxes or both?
- no data against zero: is "nothing sold" 0 or no value?
- stock that exists but cannot be sold (short-dated, in transit): does it
  count?

If two teams care about the answer, run a
[definition session](running-a-definition-session.md) instead of letting
the first person to open the editor decide.

## 4. Write the decision record
Copy [`decisions/TEMPLATE.md`](../decisions/TEMPLATE.md) to the next free
number. The record says what was decided, who decided, what else was
considered, and works one real case by hand. That case becomes the first
golden question.

## 5. Add it as a draft
Write the metric in the owner's `dbt/models/semantic/metrics_<owner>.yml`
with `status: draft` and every governance field present
(`version`, `status`, `certified_on`, `recertify_every_days`, `decision`,
`replaced_by`, `agent_notes`). Leave `decision` and `certified_on` empty
until the record is accepted: the lint fails a metric that links a record
still marked proposed.

A draft is useful and safe at the same time:

- it is listed in the registry, so everyone can see it is coming;
- a prototype dashboard can read it while the owner reviews the numbers;
- the MCP server refuses it ("not a certified metric"), so no agent quotes
  a number nobody has signed.

The lint already holds a draft to two things: the file has its owner in
CODEOWNERS, and CHANGELOG has an entry for its first version.

Alongside it:

- **Golden questions.** Turn the worked example and two or three questions
  the dashboard's readers will really ask into golden questions, with `why`
  and the owner's sign-off, then run `make golden-freeze` so the expected
  answers come from the independent reference, not from the metric itself
  ([From analyst answers to golden questions](from-analyst-answers-to-golden-questions.md)).
- **Agent notes.** Write what an agent must say with this number. Review
  them like the rule itself: in this repo, one line in `gross_margin`'s
  notes made an agent answer a rate when it was asked for an amount.

## 6. Certify it in one pull request
The pull request that makes the number official holds:

- the metric with `status: certified`, `version: 1`, `certified_on` and
  `recertify_every_days`, and its decision record as `accepted`;
- the golden questions and their frozen answers;
- CODEOWNERS for any new rule file, so the owner reviews every later change;
- a CHANGELOG entry under Definitions;
- the regenerated registry (`make registry`);
- the dashboard declared as an exposure in `dbt/models/exposures.yml`, so
  `make affected` names it when the metric changes later;
- a saved query for every slice the dashboard shows.

The owner approves it through CODEOWNERS. `make lint` and `make golden`
must pass; the lint fails a certified metric with no owner or no golden
question, and one that links a decision record that does not exist or is
not accepted.

## 7. After the merge
- The dashboard shows only exported certified values. In Power BI, the lint
  rejects a measure that computes anything itself
  ([BI tools](../adoption/bi-tools.md)).
- Agents can now answer with the metric over MCP, with its caveats.
- The number is due for review on the date the registry shows
  ([Recertification](recertification.md)).

## A metric is done when
- [ ] it has an owner: a dbt group with a GitHub team, and CODEOWNERS sends
      its file to that team;
- [ ] it is in the semantic layer, `certified`, with a version;
- [ ] its decision record is accepted and works a real case by hand;
- [ ] golden questions with the owner's sign-off pass in CI;
- [ ] CHANGELOG and the registry show it;
- [ ] every dashboard that reads it is an exposure and reads it through a
      saved query.

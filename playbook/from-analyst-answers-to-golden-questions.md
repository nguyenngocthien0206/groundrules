# From analyst answers to golden questions

A golden question is a real business question with a signed-off answer,
run against the semantic layer in CI. It is how an analyst's judgment
becomes a test: when someone changes a rule without meaning to, a golden
question fails and says why.

## Do not ask analysts to list their rules
Ask a senior analyst "what are the rules for available stock?" and you get
three of the ten that matter. The rest are so familiar they do not feel like
rules. Ask instead what people asked them last week, and how they answered.
Every answer carries the rules inside it.

Good places to harvest from:
- the analytics channel in Slack or Teams, last three months
- the ticket queue for "can you pull this number"
- the questions leadership asks in the monthly business review
- the corrections: every "no, that number is wrong because..." is a rule

An afternoon of reading gives you more than a week of interviews, and it
costs the analyst an hour of review instead of a week of their time.

## Turning one answer into a question
Take a real exchange: "How many bottles of the 70ml saline spray can NW001
sell today?" The analyst answered 48, not 49, because one bottle expires in
71 days and the store does not sell anything with less than 90 days left.

That becomes `GQ-STOCK-01` in `golden/questions/stock.yml`:

```yaml
- id: GQ-STOCK-01
  question: How many bottles of the 70ml saline nasal spray (100075) can NW001 sell today?
  kind: tacit_rule
  metric: available_stock
  filters: {store: NW001, sku: "100075"}
  as_of: 2026-09-15
  tolerance: 0
  why: >
    One bottle expires in 71 days and 48 in 191 days. Only batches with at
    least 90 days left count, so 48 are available; the rejected 60-day rule
    would say 49.
  decision: DR-001
  signed_off_by: Head of Supply Chain
  signed_off_on: 2026-09-12
```

The parts that matter:
- **`why`** is the analyst's explanation in their words, with the numbers.
  When the question fails, the runner prints it, so the person reading the
  CI log learns the rule without asking anyone.
- **`decision`** links the record that made the rule. A question that cannot
  name a decision is a sign the rule was never decided; run a
  [definition session](running-a-definition-session.md).
- **`signed_off_by`** is a role, and it is the business owner, not the
  analyst. The analyst writes; the owner confirms that this is the answer
  the business wants.
- **`tolerance`** is absolute, in the metric's unit. Zero for counts, 1 VND
  for most money, more only with a written reason (see
  [When a golden question fails](when-a-golden-question-fails.md)).

The expected number itself is **not** in this file. See below.

## The four kinds
| Kind | Tests that | Example |
| --- | --- | --- |
| `tacit_rule` | an unwritten rule is applied | 48 bottles, not 49 (the 90-day rule) |
| `conflict` | the agreed answer wins over the old ones | August revenue is 7,373,442,763, not any legacy dashboard's number |
| `caveat_required` | the answer carries the warning it must carry | NW029's days of cover come with `pos_sync_lag:NW029` |
| `deprecated` | a retired metric is refused with a pointer | asking for `revenue_v1` returns "use `net_revenue`" |

Aim for at least one question per certified metric (the lint fails
otherwise), and two or three for any rule people have argued about.

Include one question that must come back **without** a caveat
(`GQ-POS-04` here). Without it, a runner that warns about everything would
pass every caveat test.

## Caveats are part of the answer
A number can be right and still mislead. NW029 opened recently and its POS
data runs three days behind, so its days of cover read 38.8, longer than
they really are. The answer is only correct if it says so.

The runner derives caveats from data, and a question passes only when the
value matches **and** the caveats equal the expected ones exactly. A missing
caveat fails; so does an unneeded one.

## Where the expected answer comes from
Expected values are computed by `golden/reference/`: plain SQL over the raw
extracts, one file per metric, written from the decision records and never
from the dbt models. `make golden-freeze` writes them to
`golden/expected/<domain>.yml`.

This independence is the point. If the expected value came from the
semantic layer, a wrong rule would produce a wrong expected value, and the
test would pass. With two independent paths, a disagreement means one of
them misread the record, and someone has to find out which.

It also keeps the roles clean. People write the questions; a script never
rewrites them. A script writes the expected values; a person reviews the
diff and the domain owner approves it, because CODEOWNERS sends
`golden/expected/stock.yml` to supply chain and `golden/expected/revenue.yml`
to finance.

## Run them
`make golden` asks the semantic layer every question, prints a table, and
for each failure prints the question, expected and actual values, the `why`
and the decision record. It writes a JUnit report for CI. Thirty questions
run in about ten seconds here, so there is no reason not to run them on
every pull request.

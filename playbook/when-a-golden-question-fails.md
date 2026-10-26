# When a golden question fails

A failing golden question means the semantic layer and the independent
reference disagree about a number the business signed off. It is not a
flaky test to retry. Someone has to find out which side is wrong, and the
answer decides who fixes it.

## Who gets it
The metric's business owner is accountable (its dbt `group`; CODEOWNERS
names the team). The on-call data person does the first triage and hands
over with a finding, not just a red build. Agree on this before the first
failure, not during it.

## Read the failure first
`make golden` prints everything needed to start:

```
GQ-STOCK-01: How many bottles of the 70ml saline nasal spray (100075) can NW001 sell today?
   expected 48.0000, got 49.0000 (tolerance 0)
   Why: One bottle expires in 71 days and 48 in 191 days. Only batches with at
   least 90 days left count, so 48 are available; the rejected 60-day rule would say 49.
   Decision: decisions/DR-001.md
```

The `why` usually tells you which rule moved. Here, 49 is exactly what the
rejected 60-day rule would give.

## Three causes, three fixes

### 1. Someone changed a rule without a decision
This is what `make demo-drift` shows: the 90-day threshold in
`available_stock` quietly becomes 60. Owner, version, decision link and
golden questions are all still in place, so the lint finds nothing.
`make affected` lists three metrics and two dashboards, and CODEOWNERS asks
supply chain to review, but a reviewer would still have to notice that 60
is not 90. Four golden questions fail, each with its `why` and record.

**Fix:** revert the change. If the change was actually wanted, it goes
through [Changing a rule](changing-a-rule.md): a decision, a new record, a
version bump, new expected values. Ask the author what they meant, not
just whether they meant it.

### 2. The data changed on purpose
A new source, a backfill, a corrected extract. The rules are fine; the
facts moved, so the expected values must move with them.

**Fix:** run `make golden-freeze` and read the diff of `golden/expected/`.
Every moved number goes to its domain owner (CODEOWNERS routes each domain
file separately). The owner approves the new values in the pull request,
with a sentence on why they moved. Never re-freeze to make a red build
green without reading the diff.

### 3. One of the two paths is wrong
Sometimes the reference misread the decision record, or the semantic layer
has a bug, or the two round differently.

In this repo, the first full run showed chain gross margin off by **2.16
VND**, on a total in the billions. The cause was not a rule: the mart stores
unit cost to four decimals per base unit, and the reference does not, so
sums over hundreds of thousands of units drift by a few VND. A changed cost
rule would move the number by millions.

**Fix:** find the cause and write it down. Here, gross margin questions got
a 100 VND tolerance, with the reason in a comment next to the tolerance and
in the progress log. If the reference was wrong, fix the reference and get
the owner to confirm it now matches the record. If the semantic layer was
wrong, that is a bug fix with a test.

## Never do this
- **Edit `golden/expected/` by hand.** It is generated from the reference;
  a hand edit makes the test agree with whatever the semantic layer says,
  which is the circular test the whole setup exists to avoid.
- **Widen a tolerance to get CI green.** A tolerance is a statement about
  how precise the number can be, with a reason a business owner would
  accept. "The build was red" is not one.
- **Delete or skip the question.** If the question no longer makes sense,
  the rule changed, and that needs a decision record.

## After the fix
Add a line to your team's log: which question, which cause, what changed.
After a few months, the log tells you where your definitions are weakest,
which is where the next definition session should go.

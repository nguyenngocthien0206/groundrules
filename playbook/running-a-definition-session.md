# Running a definition session

A definition session is a short meeting with one job: turn "it depends who
you ask" into one written rule. You run one whenever two teams report
different numbers for the same question, or when a number matters enough
that nobody should have to ask a senior analyst what it means.

In this repo, `make demo-conflict` shows why. Four ways of answering "what
was our revenue in August 2026?" give 7,387,021,279 VND (finance), 7,442,338,602
(store sales), 7,855,865,056 (operations) and 7,373,442,763 (the certified
`net_revenue`). Every one of them was a reasonable choice by a reasonable
team. The session is where the company picks one on purpose.

## Who is in the room
Keep it to four or five people. More than that and it turns into a status
meeting.

- **The business owner** of the number: the role accountable for it, for
  example the Chief Financial Officer for revenue. They decide. If they
  cannot come, move the session; a decision made without them gets
  reopened later.
- **The data owner**: the person who knows how the data arrives and what it
  can and cannot support. They say what is computable.
- **One analyst who answers this question today.** They know the edge cases
  because people ask them about the edge cases every week.
- **Whoever disagrees.** If operations reports revenue with VAT, someone
  from operations is in the room, or the decision will not stick.

A facilitator from the data team runs the clock and writes things down.
They do not vote.

## Before the session
Send this a day ahead, on one page:

1. The question in one sentence: "What was revenue in August 2026?"
2. Every answer currently in use, side by side, with the gap to each other
   and the one rule that explains each gap. `make demo-conflict` prints
   exactly this; build the same table from your own dashboards.
3. Two or three real rows that land differently under each rule. In this
   repo, a refund in August for a July sale is the row that splits finance
   from the certified number.

The prep is the expensive part, and it is the data team's job, not the
business owner's. An hour of an analyst's prep saves an hour of five
people arguing from memory.

## In the session (45 to 60 minutes)
1. Restate the question and confirm everyone means the same thing by it.
   Half of all conflicts end here: "revenue" meant before VAT to one team
   and after VAT to another.
2. Walk the real rows. Ask each team what their rule does with each row and
   why. Write the options down with the role that prefers each one.
3. The business owner decides. If the room is split and the owner is
   unsure, ask what the number is used for: a number that pays bonuses and
   a number that plans stock can legitimately differ, and then you need two
   metrics with two names, not one compromise.
4. Agree on one worked example: a real case with real rows that anyone can
   check by hand.
5. Agree on who signs the golden questions and by when.

If a decision cannot be made in the hour, the output is a written list of
what is missing and a date. Do not leave with "let's think about it".

## The three outputs
Every session ends with these three, in one pull request:

1. **A decision record** in `decisions/`, copied from
   [the template](../decisions/TEMPLATE.md). Context, decision, options
   considered with who wanted each, consequences, worked example. See
   [DR-002](../decisions/DR-002.md) for the revenue one.
2. **The metric change** in `dbt/models/semantic/`: the rule written as a
   filter or expression, with `version`, `status`, `certified_on` and a
   `decision` link in the metric's `meta`.
3. **Golden questions** in `golden/questions/`, built from the worked example
   and the edge cases discussed. See
   [From analyst answers to golden questions](from-analyst-answers-to-golden-questions.md).

The facilitator drafts all three within two working days, while the
reasoning is fresh. The business owner approves the pull request, and
CODEOWNERS makes sure the right team is asked (see [Ownership](ownership.md)).

## What not to do
- Do not run a session for a number nobody uses. Start with the ten numbers
  leadership looks at most (see [adopting in 30 days](../adoption/adopt-in-30-days.md)).
- Do not let the data team decide a business rule because the business
  owner is busy. The record names who decided, by role, and it should be
  the person accountable for the number.
- Do not merge the metric without the golden questions. A rule with no test
  can be changed back by anyone, silently, as `make demo-drift` shows.

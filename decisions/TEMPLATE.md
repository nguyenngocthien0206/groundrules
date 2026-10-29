---
id: DR-000
title: One sentence that states the decision, not the topic
status: proposed            # proposed | accepted | superseded
date: YYYY-MM-DD            # the day it was decided
decided_by: Role that owns the number, never a person's name
consulted:
  - Roles that gave input
linked_metrics:
  - metric_name             # every metric whose definition this record explains
linked_golden_questions:
  - GQ-DOMAIN-01            # questions that fail if someone changes the rule silently
linked_actions: []          # optional: actions (actions/*.yml) whose rules this record sets
supersedes: null            # DR-xxx this one replaces, if any
superseded_by: null         # filled in when a later record replaces this one
---

# DR-000: Title

## Context
What question kept coming back, what the data looks like, and why the
answer depended on who you asked. Two or three short paragraphs. Write it
for someone who joins the team next year.

## Decision
The rule in one or two sentences, precise enough to compute by hand. Name
the metric and the file where it is encoded.

## Options considered
- **Option A (chosen):** what it means and why it won.
- **Option B:** what it means and why it lost. Say who wanted it, by role.

## Consequences
What changes for people and for numbers: which dashboards move, what an
agent must say, what becomes harder. Include the cost of the choice.

## Worked example
One real case from the data, with the rows and the arithmetic, so anyone
can check the number without running anything. The same case appears in
the `why` of at least one linked golden question.

# Guide by use case

The docs are filed by folder: [`adoption/`](adoption/) for bringing this
into a company, [`playbook/`](playbook/) for the routine once it runs. You
arrive with a situation instead. Find yours below and follow the steps in
order; each step names the page to read and the command to run. Every
section ends with what "done" looks like, so you know when to stop.

| You are here | Go to |
| --- | --- |
| You just joined, and the rules behind the numbers live in people's heads | [1](#1-the-rules-live-in-peoples-heads) |
| A dashboard needs a number the company has never defined | [2](#2-a-dashboard-needs-a-new-number) |
| A number has to change | [3](#3-a-number-has-to-change) |
| CI is red on `make golden` | [4](#4-ci-is-red-on-the-golden-questions) |
| A metric is due for review | [5](#5-a-metric-is-due-for-review) |
| You want an AI agent to answer questions | [6](#6-let-an-agent-answer) |
| You want an AI agent to do something | [7](#7-let-an-agent-act) |
| An agent proposed something, or the month's rejections are due | [8](#8-decide-on-what-an-agent-proposed) |
| You are moving this onto your own dbt project, warehouse or BI tool | [9](#9-move-it-onto-your-stack) |

## 1. The rules live in people's heads
You are new, the numbers disagree, and the people who know why are busy.
The goal is not to write everything down; it is to get the ten numbers that
matter most owned, defined, proven and enforced in about a month.

**Who:** you (facilitating), the analysts who answer the questions today,
one business owner per number.

**Steps**
1. Read [Adopt in 30 days](adoption/adopt-in-30-days.md) for the shape of
   the month, and [Cost and roles](adoption/cost-and-roles.md) before you
   ask anyone for time. Book the owners' hours in week 1.
2. Pick about ten numbers: the most used and the most argued about. Give
   each an owner, a business role rather than a builder
   ([Ownership](playbook/ownership.md)).
3. Find where the numbers disagree: ask every dashboard the same question,
   read the filters in the old SQL, read past corrections
   ([Where else the rules hide](playbook/from-analyst-answers-to-golden-questions.md#where-else-the-rules-hide)).
   `make demo-conflict` shows what the result looks like.
4. Collect the questions analysts were really asked and how they answered;
   do not ask them to list their rules
   ([From analyst answers to golden questions](playbook/from-analyst-answers-to-golden-questions.md)).
5. Where two teams give two answers, run a
   [definition session](playbook/running-a-definition-session.md) and write
   the decision record within two days ([`decisions/`](decisions/)).
6. Encode each number in the semantic layer, with golden questions whose
   answers come from the independent reference (`make golden-freeze`, then
   `make golden`). If you already have a dbt project, copy what
   [Existing dbt project](adoption/existing-dbt-project.md) lists.
7. Let Git enforce it: CODEOWNERS for every rule file, `make lint` and
   `make golden` in CI, `make registry` for the page managers read.

**Done when** each of the ten numbers is certified with an owner, an
accepted decision record and signed golden questions, CI runs the lint and
the golden questions on every pull request, and the registry lists them.

## 2. A dashboard needs a new number
Someone wants a dashboard and it needs a number nobody has defined. Define
it now, before anyone gets used to a version of it.

**Who:** you, the person asking, the team that will own the number.

**Steps**
1. Follow [A new metric](playbook/a-new-metric.md) from the top: take the
   request, then check [`governance/registry.md`](governance/registry.md)
   before writing anything.
2. If the number exists, add a saved query and stop
   ([BI tools](adoption/bi-tools.md)). If it would change an existing
   number, go to [3](#3-a-number-has-to-change).
3. Otherwise: owner and edge cases, a decision record, the metric as a
   `draft` (agents refuse it), golden questions, then one pull request that
   certifies it, with its CHANGELOG entry, `make registry`, the dashboard's
   exposure and its saved queries.
4. Export for the BI tool with `make dashboard-data`; the report only
   displays certified values.

**Done when** the checklist at the end of
[A new metric](playbook/a-new-metric.md#a-metric-is-done-when) is ticked.

## 3. A number has to change
A rule was wrong, the business changed, or a case nobody thought of turned
up. Change it deliberately, not quietly.

**Who:** the metric's owner (decides), whoever opens the pull request,
everyone who reads the number (told).

**Steps**
1. Follow [Changing a rule](playbook/changing-a-rule.md): the owner
   decides, a new decision record supersedes the old one, the metric's
   version goes up.
2. Run `make affected` to see which metrics, dashboards and reports the
   change reaches, and tell their owners.
3. Update the golden questions whose numbers move; the owner signs them
   again. Add the CHANGELOG entry and `make registry`.
4. If an action reads the metric, the lint stops until its owner re-checks
   the action's rules and bumps the pinned version
   ([`actions/README.md`](actions/README.md)).

**Done when** CI is green, the CHANGELOG says what moved for readers, and
the old record says which one replaced it.

## 4. CI is red on the golden questions
A golden question failed. It is a message from the owner of a rule, not a
flaky test.

**Who:** the metric's owner and whoever is on call for data.

**Steps**
1. Follow [When a golden question fails](playbook/when-a-golden-question-fails.md):
   read the failure (it names the question, its `why` and its decision
   record) and decide which of three things happened: someone changed a
   rule without a decision, the data changed on purpose, or one of the two
   paths (the reference or the semantic layer) is wrong.
2. `make demo-drift` shows a failure caused on purpose, and how it reads.

**Done when** the cause is fixed where it belongs (the rule goes back or
gets its decision record, the owner re-signs the moved answers, or the
wrong path is fixed), never by editing an expected value, widening a
tolerance or skipping the question.

## 5. A metric is due for review
Owners re-sign their numbers on a schedule, so a rule nobody looked at for a
year does not quietly drift away from the business.

**Who:** the metric's owner, the data lead.

**Steps**
1. Follow [Recertification](playbook/recertification.md). The registry
   shows each metric's "recertify by" date; `make lint` warns once it has
   passed.
2. The owner checks the rule, its golden questions and what reads it
   (`make affected`), then either re-signs it (a small pull request that
   bumps `certified_on`), changes the rule ([3](#3-a-number-has-to-change)),
   or retires it (`status: deprecated` with `replaced_by`).

**Done when** the registry shows a new recertify-by date, or the
replacement.

## 6. Let an agent answer
An AI agent should answer business questions with the certified numbers
instead of writing its own SQL.

**Who:** the data platform team, with the metrics' owners reviewing the
notes written for agents.

**Steps**
1. Read [Agents](adoption/agents.md): connect the agent to `make mcp-server`
   (list, describe, find values, query). It refuses deprecated and draft
   metrics and returns the caveats.
2. Review each metric's `agent_notes` like the rule itself; an agent acts
   on them.
3. Measure it on your own golden questions: `make agent-eval-probe`, then
   `make agent-eval` on the governed and the raw SQL arms.

**Done when** the agent answers only through the governed server and your
own eval shows how often it is right.

## 7. Let an agent act
An agent should do something, not only answer: propose a transfer, an
order, a reminder.

**Who:** the action's owner (decides the rules and who approves), the data
platform team (builds), an analyst (reference and golden questions).

**Steps**
1. Read [Actions](adoption/actions.md): start only once the metrics it
   reads are certified, pick a reversible first action, and roll out in
   stages.
2. Write the rules as a decision record and a contract in
   [`actions/`](actions/), list who may approve in `actions/approvers.yml`,
   and add golden questions for the action. The lint ties them together
   ([`actions/README.md`](actions/README.md)).
3. Connect the agent to `make mcp-server-actions`; the rules choose, the
   agent only names the target.
4. Measure what the contract adds over the rules in a prompt:
   `make agent-eval` on the `actions` and `raw_actions` arms.

**Done when** proposals reach the ERP only after a listed person approves
them, and every step is in the audit log.

## 8. Decide on what an agent proposed
Proposals are waiting, or it is time for the monthly look at what was
rejected.

**Who:** the people listed in `actions/approvers.yml`, the action's owner.

**Steps**
1. Follow [Approving proposals](playbook/approving-proposals.md):
   `make proposals`, then `make approve` or `make reject` with a reason.
2. A stale proposal means a metric, the contract or the data moved; the
   agent proposes again.
3. Once a month, read the rejection reasons with the owner. A reason that
   keeps coming back is a rule nobody wrote: go to
   [3](#3-a-number-has-to-change), for the action instead of a metric.

**Done when** nothing waits longer than a day, and the month's rejection
reasons have been read by the owner.

## 9. Move it onto your stack
You want this on your dbt project, your warehouse and your BI tool, not on
the demo's DuckDB.

**Who:** analytics engineers and the data platform team.

**Steps**
1. [Existing dbt project](adoption/existing-dbt-project.md): which folders
   to copy, what to adopt in dbt, what to delete.
2. [Warehouses](adoption/warehouses.md): what changes on Snowflake,
   BigQuery, Databricks or Postgres (profiles, sources, a few staging
   models, the reference's raw views) and what does not (marts, the
   semantic layer).
3. [BI tools](adoption/bi-tools.md): keep the BI tool from becoming a
   second place where metrics are defined.

**Done when** `make build`, `make lint`, `make golden` and `make test` pass
on your stack.

## Every page, and where it is used

| Page | Use cases |
| --- | --- |
| [Adopt in 30 days](adoption/adopt-in-30-days.md) | 1 |
| [Cost and roles](adoption/cost-and-roles.md) | 1 |
| [Existing dbt project](adoption/existing-dbt-project.md) | 1, 9 |
| [Warehouses](adoption/warehouses.md) | 9 |
| [BI tools](adoption/bi-tools.md) | 2, 9 |
| [Agents](adoption/agents.md) | 6 |
| [Actions](adoption/actions.md) | 7 |
| [Adoption guide index](adoption/README.md) | all |
| [Ownership](playbook/ownership.md) | 1 |
| [From analyst answers to golden questions](playbook/from-analyst-answers-to-golden-questions.md) | 1, 2 |
| [Running a definition session](playbook/running-a-definition-session.md) | 1, 2 |
| [A new metric](playbook/a-new-metric.md) | 2 |
| [Changing a rule](playbook/changing-a-rule.md) | 3, 8 |
| [When a golden question fails](playbook/when-a-golden-question-fails.md) | 4 |
| [Recertification](playbook/recertification.md) | 5 |
| [Approving proposals](playbook/approving-proposals.md) | 8 |
| [Playbook index](playbook/README.md) | all |

# Actions

The rest of this guide gets an agent to give the certified number. This
page is about the next request you will get: "can the agent just do it?"
Move the stock, raise the order, send the reminder. It can, safely, if you
treat an action the way the repo treats a metric: one owner, one written
rule, proof in CI, and a person who signs before anything moves.

The repo's example is `propose_transfer`: an agent proposes moving stock
from a store with plenty to one about to run out, and supply chain
approves each proposal. Use it as a template, not as the action you must
start with.

## Start only when the numbers are settled
An action is a decision taken on metrics, so it is only as right as they
are. Do not start until the metrics it reads are certified, owned and
pinned by golden questions.

This repo shows why. Writing the transfer rules down (DR-012) meant asking
what "days of cover" is for a store that has run out. The certified metric
said "no value"; its decision record said 0 days. That gap had passed every
golden question, because none asked about a store that had run out. It was
fixed as `days_of_cover` v2 before any agent proposed anything. Expect the
same: drafting an action's rules is the most thorough review your metrics
will get.

## Pick the first action
Good first actions share four traits:

- **Reversible.** A box sent to the wrong store can be sent back. A refund
  or a price change cannot.
- **Small per decision.** Many decisions of low value each, so one mistake
  is cheap and the volume makes automation worth it.
- **Already decided every day, by phone or spreadsheet.** You are writing
  down a routine, not inventing one, and the people who run it today can
  tell you its rules and its exceptions.
- **One clear owner.** One team decides the thresholds and approves the
  proposals. If two teams must both agree, settle that first, the way a
  definition session settles a metric.

## The six pieces, and who writes each

| Piece | In this repo | Written by | Signed by |
| --- | --- | --- | --- |
| The rules and why | [`decisions/DR-012.md`](../decisions/DR-012.md) | data lead with the owner | the owner (here the Head of Supply Chain) |
| The contract: owner, approver, metrics read and their versions, rules as numbers | [`actions/propose_transfer.yml`](../actions/propose_transfer.yml) | analytics engineer | the owner, through CODEOWNERS |
| Who may approve | [`actions/approvers.yml`](../actions/approvers.yml) | the owner | the owner, through CODEOWNERS |
| An independent reference and golden questions | [`golden/reference/transfer_candidates.sql`](../golden/reference/transfer_candidates.sql), [`golden/actions/`](../golden/actions/questions/transfers.yml) | analyst | the owner signs each question |
| The engine and the agent's tools | [`mcp_server/transfers.py`](../mcp_server/transfers.py), [`mcp_server/actions.py`](../mcp_server/actions.py) | data platform | code review |
| Shadow table, approval, write-back, audit log | [`mcp_server/shadow.py`](../mcp_server/shadow.py), [`mcp_server/approvals.py`](../mcp_server/approvals.py), [`mcp_server/erp.py`](../mcp_server/erp.py) | data platform | code review |

The governance lint ties them together. `make lint` fails when the
contract's owner or approver has no team, its decision record is not
accepted, a metric it pins has moved to a new version, its rules
contradict each other, nobody is listed to approve, it has no golden
question, or CODEOWNERS does not send a change to the owner.
[`actions/README.md`](../actions/README.md) lists every check and walks
through a proposal from agent to ERP.

Two design choices matter more than the code:

- **The rules choose, the agent asks.** The agent names a target; the
  engine picks the donor and the quantity. An agent that may pick freely
  can always pick something the rules would not.
- **Approve or reject, never edit.** An approver who changes the quantity
  has made a decision outside the rule. If the rule is wrong, change the
  rule ([Changing a rule](../playbook/changing-a-rule.md)).

## Roll it out in stages
1. **Proposals only.** Run `make mcp-server-actions` for the people who
   make the decision today and let them compare the proposals with what
   they would have done. Disagreements are either a missing rule (write it
   down) or an exception (decide whether it should be one).
2. **Approval with write-back.** Listed approvers decide with
   `make approve` and `make reject`; approved proposals reach the ERP. The
   owner reads the rejection reasons every month
   ([Approving proposals](../playbook/approving-proposals.md)).
3. **Wider limits, later and carefully.** After months of approvals with
   few rejections, you may raise a limit or add a second action. Keep a
   person on anything that moves stock or money: the approval is where the
   company decides, and the audit log is where it can show it did.

## What to replace in your company
- **The ERP stand-in** (`var/erp.duckdb`): your ERP's API or import table.
  Keep the proposal id as the idempotency key, so a retried approval never
  creates a second request.
- **Email addresses in `approvers.yml`:** map them to your SSO identities,
  but keep the list in Git, owned by the approving team. The list is the
  control; a group in an identity tool that anyone in IT can change is not.
- **The shadow and audit tables** (`var/actions.duckdb`): one database your
  data platform runs, with the audit log under your retention rules.
- **The as-of date:** this demo reads one snapshot. In production the
  engine reads the latest data, and the stale check at approval (versions,
  then a recompute that must give the same proposal) is what protects you
  when stock moves between proposal and approval.

## Policy in a prompt, or policy in the tools
A common shortcut is to paste the policy into the agent's prompt and give
it write access. The repo measured that shortcut against the contract
([results](../agent_eval/results/v0.3.0/summary.md)): same agent, same 8
requests, three times each, DR-012's rules word for word in the prompt
either way.

- With the contract's tools, 24 of 24 runs filed the right transfer, or
  nothing when nothing was due, with a median of 2 tool calls.
- With SQL and an unchecked write tool, 21 of 24 did, with a median of 13
  tool calls and about four times the tokens. It never filed a transfer
  that broke a rule; its misses were transfers it should have made and did
  not, and wrong reasons.
- Every miss had one cause: DR-012 refers to DR-001 for what counts as
  available stock, and the prompt did not carry DR-001's 90-day rule.

The lesson for an owner: a prompt carries only the rules written in it,
not the ones they depend on. Tools that compute with the certified metrics
carry them all. With 8 questions the intervals are wide; rerun the eval on
your own action before you rely on either number (`make agent-eval-probe
ARM=actions`, then `make agent-eval ARM=actions` and `ARM=raw_actions`, as
in [Agents](agents.md)).

## Where the hours go
- **The owner:** deciding the thresholds (here 7, 14, 30 and 60 days, 30
  minutes, whole boxes) and signing the decision record and golden
  questions; then a monthly look at rejections. The thresholds take the
  longest, because each one is a trade-off someone has to own.
- **Approvers:** a short daily slot. The rules do the search; the person
  checks what the rules cannot know, such as stock held for a promotion.
- **Data platform:** most of the build: the engine, the shadow table, the
  write-back and the audit log, once. A second action reuses all of it.
- **Analyst:** the reference and the golden questions, the same skill as
  for metrics.

[Cost and roles](cost-and-roles.md) covers the same split for metrics.

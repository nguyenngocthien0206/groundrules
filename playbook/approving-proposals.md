# Approving proposals

An agent can propose a stock transfer; only a person can make it happen.
This page is the routine for the people listed in
[`actions/approvers.yml`](../actions/approvers.yml) and for the owner who
reads what they decide. The mechanics take minutes a day. The value is in
the reasons people write down when they say no.

## Every day: decide what is waiting
One approver takes a short slot each morning, after the nightly data load:

```bash
make proposals                       # what is waiting, most urgent detail on each line
python mcp_server/approvals.py show TP-...   # one proposal, its numbers and its history
make approve ID=TP-... AS=planner.riverside@example.com
make reject  ID=TP-... AS=planner.riverside@example.com REASON="..."
```

Each line shows the target, the donor, the quantity in whole boxes or
cartons, the drive time and the cover before and after. The rules have
already done the search, so the approver checks what the rules cannot see:
stock promised to a clinic, a promotion next week, a van that is not
running. Three habits keep the record useful:

- **Approve as is, or reject.** There is no edit. If the quantity looks
  wrong, reject with the reason; a changed quantity would be a decision
  outside DR-012 that nobody else could see.
- **Write the reason as a rule would.** "NW009 holds this stock for a
  promotion until 2026-09-30" helps the owner; "not now" does not. The
  command refuses an empty reason.
- **Never approve your own proposal.** The command refuses it anyway, and
  logs the attempt.

An approved proposal becomes one ERP request at once. Running `make
approve` again, by the same or another approver, does not create a second
one.

## When a proposal is stale
`make approve` checks the proposal again before writing anything. It is
marked **stale**, and nothing goes to the ERP, when:

- a metric it read, or the contract, has moved to a new version since it
  was filed; or
- the rules, run again on today's data, now give another donor or quantity.

Stale is not an error. Stock moved, or the rule changed, and the proposal
no longer stands; the agent proposes again and gets today's answer. If
many proposals go stale at once, the warehouse was most likely rebuilt or
a metric was recertified overnight: check the CHANGELOG before anyone
starts approving.

## Every month: read the rejections with the owner
The owner (here the Head of Supply Chain) and the approvers spend half an
hour on the month's rejected and stale proposals. `show` prints each
proposal's full history; the audit log has every rejection reason.

- **A reason that keeps coming back is a rule nobody wrote.** If donors are
  rejected again and again because the stock is held for promotions, the
  rules should know about promotions. That is a rule change: a new decision
  record, a new contract version, golden questions for the new case, and
  the lint will make sure the pin, CODEOWNERS and CHANGELOG follow
  ([Changing a rule](changing-a-rule.md)).
- **Rejections with no pattern** are the exceptions approvers exist for.
  Leave them to people.
- **Few rejections for months** is the evidence to raise a limit, never a
  reason to remove the approver
  ([Actions](../adoption/actions.md#roll-it-out-in-stages)).

## When the log shows a refusal
A `refused` event means someone tried to decide and was stopped: they are
not listed for the action, or they filed the proposal themselves. Most are
honest mistakes, such as a new planner not yet added. The owner follows up:
add the person to `approvers.yml` through a pull request their team
approves, or explain why they should not decide. Nobody edits the list to
get one proposal through.

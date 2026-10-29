# Playbook

The rest of this repo is machinery: a semantic model, decision records,
golden questions, a lint. None of it helps if nobody knows who meets when,
who decides, and what to do when CI goes red on a Tuesday. This folder is
the weekly routine around the machinery.

Each page pairs the mechanics (which file, which command) with the people
side (who is in the room, who signs, who gets paged). Adopt the pages that
fit your team and change the rest; the files and checks will hold whatever
routine you settle on.

| Page | Read it when | Mostly for |
| --- | --- | --- |
| [Running a definition session](running-a-definition-session.md) | two teams give different numbers for the same question | the data lead who runs the meeting |
| [Ownership](ownership.md) | you need to say who decides what a number means | data lead, business owners |
| [From analyst answers to golden questions](from-analyst-answers-to-golden-questions.md) | you want tests that capture judgment, not just syntax | analysts, analytics engineers |
| [Changing a rule](changing-a-rule.md) | a definition has to change | whoever opens the pull request, and its reviewers |
| [When a golden question fails](when-a-golden-question-fails.md) | CI is red on `make golden` | the metric's owner and the on-call data person |
| [Recertification](recertification.md) | a metric is due for review, or the lint warns that it is stale | business owners, data lead |
| [Approving proposals](approving-proposals.md) | an agent has proposed an action, or the month's rejections are due for review | approvers, the action's owner |

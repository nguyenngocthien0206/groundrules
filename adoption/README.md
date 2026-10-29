# Adoption guide

This folder is for the data lead who has read the demos and is asking: what
would this take in my company, on my dbt project, with my warehouse and my
BI tool?

The short answer: very little tooling and a fair amount of business
experts' time. Everything here runs on what you likely already have (dbt,
MetricFlow, Git, a CI runner). The hard part is getting the people who own
the numbers to decide and sign, and the guide spends most of its words
there.

| Page | Answers |
| --- | --- |
| [Adopt in 30 days](adopt-in-30-days.md) | what to do each week, who spends the hours, what you have at the end |
| [Existing dbt project](existing-dbt-project.md) | which folders to copy, what to adopt in dbt, what to delete |
| [Warehouses](warehouses.md) | exactly what changes when you leave DuckDB |
| [BI tools](bi-tools.md) | how to keep your BI tool from becoming a second place where metrics are defined |
| [Agents](agents.md) | how an AI agent asks the semantic layer over MCP instead of writing SQL |
| [Actions](actions.md) | when and how to let an agent propose changes, who approves, and what a contract adds to a prompt |
| [Cost and roles](cost-and-roles.md) | where the hours go and who to involve |

## If you only have one afternoon
Copy two things and leave the rest for later:

1. **`decisions/`** with the template. Write one decision record for the
   number your company argues about most. It costs an hour with its owner
   and it is useful even with nothing else in place.
2. **Three golden questions** for that number, with `why` and a sign-off,
   in `golden/questions/`. Even before the runner is wired up, they are the
   clearest spec your analytics engineers will ever get.

Then read [Adopt in 30 days](adopt-in-30-days.md) to plan the rest.

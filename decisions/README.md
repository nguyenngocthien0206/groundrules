# Decision records

A decision record (DR) writes down why a number is defined the way it is.
The semantic layer says *what* a metric computes. The DR says *why*: what
the question was, who disagreed, who decided, what else was on the table,
and one case worked out by hand.

Most of these rules used to live in a senior analyst's head. When a person
asked for "available stock", the analyst knew to drop short-dated batches
and stock already on a truck to another store. An AI agent has no such
analyst in the loop, so the rule has to be written where both people and
agents can read it.

## When to write one
- A metric is created, or its definition changes in any way that moves a number.
- Two teams give different answers to the same question.
- Someone asks "why is it computed like this?" and the answer is not in the code.

Write it in the same pull request as the metric change. The PR template
asks for the link, and CODEOWNERS sends it to the business owner.

## How to write one
Copy `TEMPLATE.md` to the next free number. The front matter is read by
the governance lint; the body is for people. Keep the worked example real:
pick rows from the data, show the arithmetic, and reuse the same case in a
golden question so the record and the test can never drift apart.

A record is never edited to change its decision. To change a rule, write a
new record that `supersedes` the old one and set `superseded_by` on the old one.

## Index
| DR | Decision | Decided by | Metrics |
| --- | --- | --- | --- |
| [DR-001](DR-001.md) | Available stock excludes batches under 90 days to expiry; near-expiry value counts them | Head of Supply Chain | available_stock, near_expiry_value |
| [DR-002](DR-002.md) | Returns count in the month they come back | Chief Financial Officer | net_revenue |
| [DR-003](DR-003.md) | Cancelled transfers are not stock in transit | Head of Supply Chain | available_stock |
| [DR-004](DR-004.md) | The business day is local time; lagging stores stay in, flagged | Head of Retail Operations | net_revenue, available_stock, days_of_cover |
| [DR-005](DR-005.md) | Deprecate revenue_v1 in favor of net_revenue | Chief Financial Officer | revenue_v1, net_revenue |
| [DR-006](DR-006.md) | Revenue is reported before VAT | Chief Financial Officer | net_revenue, gross_margin |
| [DR-007](DR-007.md) | Stock and units sold are counted in the base unit | Head of Supply Chain | available_stock, sell_through_rate, days_of_cover |
| [DR-008](DR-008.md) | Cost of goods sold uses the store's weighted average cost | Chief Financial Officer | gross_margin |
| [DR-009](DR-009.md) | Sell-through divides units sold by units received net of transfers out | Head of Supply Chain | sell_through_rate |
| [DR-010](DR-010.md) | Days of cover uses the pace of the 28 full days before the snapshot | Head of Supply Chain | days_of_cover |

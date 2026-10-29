# Agents

Everything else in this repo makes definitions safe for people. This page
is about the reader the repo was built for: an AI agent answering business
questions on its own, with no analyst in the loop to catch a wrong rule.

The rule is simple. An agent asks the semantic layer, never the tables.
`mcp_server/semantic.py` is how it asks.

## What the agent gets
The server speaks MCP, the protocol most agent tools use to call external
tools, and offers four:

| Tool | What it does |
| --- | --- |
| `list_metrics` | the metrics the agent may use, with status, version and owner; hidden building blocks are never listed |
| `describe_metric` | what one metric counts, its owner, the decision record behind it, the notes written for agents, and the caveats an answer can carry |
| `find_values` | turns "Old Quarter" or "vitamins" into the codes the metric needs |
| `query_metric` | the answer, with its caveats |

`query_metric` takes the same code path the golden questions prove. So an
agent gets exactly the number CI checks on every pull request, including:

- **Refusals.** Ask for `revenue_v1` and the answer is a refusal with
  `use_instead: net_revenue`, not a number. Ask for a building block such as
  `units_sold` and the refusal lists the certified metrics.
- **Caveats.** An answer that depends on a store whose POS data runs behind
  carries `pos_sync_lag:<store>`; a sell-through answer that includes a new
  store carries `new_store:<store>`. The server instructs the agent to report
  them verbatim.
- **No value.** NW030's sell-through in September 2026 comes back as `null`
  with a note, never 0 and never -20.43 (DR-011).
- **Bad requests explained.** A name instead of a code, two periods at once
  or a malformed month returns an error that says what to fix.

Nothing in the server defines a metric. If a number is wrong, the fix is in
the semantic layer and its decision record, and every agent, dashboard and
golden question moves together.

## Connect it
The server runs over stdio from the repo, after `make build`.

Claude Code:

```bash
claude mcp add groundrules -- uv run --directory /path/to/groundrules python mcp_server/semantic.py
```

Claude Desktop or any other MCP client, in its JSON configuration:

```json
{
  "mcpServers": {
    "groundrules": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/groundrules", "python", "mcp_server/semantic.py"]
    }
  }
}
```

`make mcp-server` starts it by hand, which is mostly useful to see that it
loads. The first call takes a few seconds while MetricFlow loads; after that
answers are fast.

The server opens the warehouse read-only, so several agents can share it,
and nothing an agent does can change the data.

## Let it propose, not act
`mcp_server/actions.py` is a second server, for the one thing an agent may
do besides answer: propose a stock transfer between stores. Connect it next
to the metrics server, the same way, with `mcp_server/actions.py` in place
of `mcp_server/semantic.py` (`make mcp-server-actions` starts it by hand).

| Tool | What it does |
| --- | --- |
| `describe_action` | the rules, who approves, the decision record (DR-012) and what to tell people |
| `find_transfer_candidates` | what the rules would propose, filtered by store, district or SKU, and why other targets get nothing; saves nothing |
| `simulate_transfer` | any what-if, checked against every rule; saves nothing |
| `propose_transfer` | files the rules' proposal for one target store and SKU, to wait for approval |
| `list_proposals` | what has been filed |

The agent picks the target; the rules pick the donor and the quantity, from
the certified metrics at the versions the contract pins
(`actions/propose_transfer.yml`). If the semantic layer serves a different
version, or `days_of_cover` stops agreeing with stock and pace, the server
refuses to propose anything. Proposals go to a separate file,
`var/actions.duckdb` (or `GROUNDRULES_ACTIONS_DB`), never the warehouse,
and nothing reaches the ERP until a person in supply chain approves it.
Filing the same proposal twice keeps one row.

## The control arm, and why not to ship it
`mcp_server/raw_sql.py` gives an agent what it is commonly given today:
the reporting tables, their column descriptions and a read-only SQL tool.
It exists only so the agent eval can measure the difference on the same
questions. Do not hand it to an agent in production.

With only the tables, an agent has to rediscover every rule on its own:
- that available stock leaves out batches within 90 days of expiry
  (`days_to_expiry` is in the table; the threshold is not)
- that revenue is before VAT and counts a refund in the month it comes back
- that two stores' POS data is days behind
- that a deprecated metric should not be answered at all

Each one it misses is a confident wrong answer. The column descriptions
help, but a description is not a decision, and nothing checks it.

## Measure it
`agent_eval/` asks an agent the golden questions through one server or
the other and grades every answer with the golden runner's own check: the
right number, the right caveats, and refusing a deprecated metric.

```bash
make agent-eval-probe                                 # is the agent's context clean?
make agent-eval ARM=semantic RUN=pilot REPS=1 CASES=GQ-SELL-01
make agent-eval ARM=raw_sql  RUN=pilot REPS=1 CASES=GQ-SELL-01
make agent-eval-summary RUN=pilot
```

Two providers run the agent:

- **`claude-code`** (default) runs Claude Code headless on a Claude
  subscription, so it uses the plan's usage limits instead of a bill. It
  needs Claude Code 2.1.221 or later, which waits for MCP servers before the
  first turn. Each question runs from an empty folder with CLAUDE.md files,
  auto memory and bundled skills switched off, only the arm's server, and
  no built-in file, shell or web tools. The probe checks this before any
  scored run.
- **`anthropic-api`** calls the Claude API with `ANTHROPIC_API_KEY`, billed
  per token, after `uv sync --group eval-api`. It has not been run in this
  repo yet.

### What it measured
Claude Sonnet 5.5 answered the 30 golden questions three times each through
each server: 180 answers, no failed runs
([results](../agent_eval/results/v0.2.0/summary.md)).

- **With the governed server, 89 of 90 answers were correct** (99%, 95%
  interval 97% to 100%), with a median of 2.5 tool calls.
- **With raw SQL, 7 of 90 were** (8%, interval 0% to 18%). Only 13% had the
  right number, and none of the conflict, caveat or deprecated questions was
  answered correctly.

The raw SQL agent's mistakes read like a list of the decision records:
- it counted a bottle that expires in 71 days, so 49 instead of 48 (DR-001)
- it left returns out of revenue, so August came out as the old store
  sales dashboard's number, while noting that returns were "about 68.9M VND
  excl. VAT in August" (DR-002)
- it answered two of three margin questions as a percentage (DR-008)
- it wrote "The warehouse has no sell-through metric, so I calculated it
  myself", divided units sold by opening stock plus receipts, and answered
  0.579 instead of 1.117 (DR-009)
- it gave NW030's September sell-through a number instead of no value
  (DR-011)
- it saw that NW029's sync was behind, but said so in a sentence a program
  cannot read instead of `pos_sync_lag:NW029` (DR-004)
- it answered `revenue_v1` with a number instead of refusing it (DR-005)

It sounded just as sure every time.

The governed agent's one miss is worth reading too. Asked "What margin did
vitamins and supplements make in July 2026?", it fetched the right amount,
then followed `gross_margin`'s own note ("For a margin rate, divide by
net_revenue for the same scope and say so") and answered a rate. The other
two runs of the same question answered the amount. The lesson is that
`agent_notes` are instructions an agent will act on, so they need the same
review as the rule itself.

After the release the note was rewritten to make the amount the default
and a rate the exception, through finance's review like any rule change.
All three margin questions, run three times each, then came back right
9 times out of 9; one run explained "The question asks for margin, not a
rate, so I report the VND amount"
([results](../agent_eval/results/followup-margin/summary.md)).

## What to adapt in your company
- **Point the server at your semantic layer.** It reuses
  `golden/semantic_client.py`, so it works wherever the golden runner works.
  On the dbt platform, the official `dbt-mcp` server offers semantic layer
  tools directly; keep this repo's golden questions to check that it returns
  the same answers.
- **Write `agent_notes` for every certified metric.** They are the one field
  written for agents, and `describe_metric` passes them through. Say what a
  null means, what not to sum, what to say when a caveat appears.
- **Keep the refusal behavior.** An agent that refuses a deprecated metric
  and names the replacement is what makes retiring a metric possible
  without hunting down every prompt that mentions it.

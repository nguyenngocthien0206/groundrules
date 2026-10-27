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
`agent_eval/` asks an agent the 30 golden questions through one server or
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

One development run shows why the eval matters. Asked NW014's August
sell-through, the agent with the semantic layer answered 1.117 in five tool
calls. The agent with raw SQL wrote: "The warehouse has no sell-through
definition, so I used units sold / (opening stock + units received)", left
out transfers, and answered 0.556. Both sounded equally sure.

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

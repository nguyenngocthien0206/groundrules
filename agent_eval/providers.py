"""Who runs the agent: Claude Code headless, or the Claude API.

Both connect the agent to one arm's MCP server, ask one golden question, and
return a RunResult with the structured answer, the served model, usage and a
trace. They never grade; grading.py does.

- ClaudeCodeProvider runs `claude -p` on the user's Claude subscription. It
  starts from an empty folder with CLAUDE.md files, auto memory and bundled
  skills switched off, only the arm's MCP server, and no built-in tools.
  API credentials are removed from its environment, so a key set for the
  other provider can never turn subscription runs into per-token billing.
- AnthropicApiProvider calls the Claude API with ANTHROPIC_API_KEY (billed
  per token, separately from a subscription). It is written to the SDK's
  documented interface and has not been run in this repo yet.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from prompt import ACTION_ANSWER_SCHEMA, ACTION_SYSTEM_PROMPT, ANSWER_SCHEMA, SYSTEM_PROMPT, user_message

ROOT = Path(__file__).resolve().parent.parent
RAW_SQL_TOOLS = ("list_tables", "describe_table", "run_sql")
ARMS = {
    "semantic": {"server": "groundrules", "script": ROOT / "mcp_server" / "semantic.py", "task": "metric",
                 "tools": ("list_metrics", "describe_metric", "find_values", "query_metric")},
    "raw_sql": {"server": "warehouse", "script": ROOT / "mcp_server" / "raw_sql.py", "task": "metric",
                "tools": RAW_SQL_TOOLS},
    # Action questions (v0.3): the contract's tools, or raw SQL plus a write tool that checks nothing.
    "actions": {"server": "groundrules-actions", "script": ROOT / "mcp_server" / "actions.py", "task": "action",
                "tools": ("describe_action", "find_transfer_candidates", "simulate_transfer", "propose_transfer", "list_proposals")},
    "raw_actions": {"server": "warehouse-actions", "script": ROOT / "mcp_server" / "raw_actions.py", "task": "action",
                    "tools": (*RAW_SQL_TOOLS, "file_transfer")},
}
PROMPTS = {"metric": (SYSTEM_PROMPT, ANSWER_SCHEMA), "action": (ACTION_SYSTEM_PROMPT, ACTION_ANSWER_SCHEMA)}


def mcp_config(arm: str, env: dict[str, str] | None = None) -> dict:
    """The MCP configuration for one arm: its server only, with any env it needs (the run's own files)."""
    server = {"command": sys.executable, "args": [str(ARMS[arm]["script"])]}
    if env:
        server["env"] = dict(env)
    return {"mcpServers": {ARMS[arm]["server"]: server}}
STRUCTURED_TOOL = "StructuredOutput"  # Claude Code's tool for --json-schema answers
MIN_CLAUDE_CODE = (2, 1, 221)  # first version that waits for MCP servers before the first turn in -p mode


@dataclass
class RunResult:
    answer: dict | None = None
    model: str | None = None
    tools: list[str] = field(default_factory=list)  # every tool the agent could call
    usage: dict = field(default_factory=dict)
    tool_calls: int = 0
    turns: int = 0
    latency_s: float = 0.0
    trace: list[dict] = field(default_factory=list)
    stop_reason: str | None = None
    cost_usd: float | None = None  # what the same tokens would cost on the API; a subscription is not billed per token
    error: str | None = None  # failure class: timeout | harness_error | mcp_not_connected | no_answer | refused | model_mismatch
    detail: str = ""


class EvalError(Exception):
    pass


def served_model_matches(requested: str, served: str | None) -> bool:
    """An alias (`sonnet`) matches its family; a full id must match exactly."""
    if not served:
        return False
    if requested.startswith("claude-"):
        return served == requested or served.startswith(requested + "-")
    return served.startswith(f"claude-{requested}")


# Claude Code headless


def find_claude_code() -> str:
    """The Claude Code executable: $CLAUDE_BIN, else `claude` on PATH.

    On Windows npm installs a `claude.cmd` shim; a batch file cuts arguments at
    newlines and mangles quotes, so the native claude.exe it wraps is used.
    """
    found = os.environ.get("CLAUDE_BIN") or shutil.which("claude")
    if not found:
        raise EvalError("Claude Code not found: install it, or set CLAUDE_BIN to its executable")
    path = Path(found)
    if path.suffix.lower() in {".cmd", ".bat"} or (sys.platform == "win32" and path.suffix == ""):
        native = path.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if native.exists():
            return str(native)
    return str(path)


def claude_code_version(binary: str) -> tuple[int, ...]:
    out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=60).stdout
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    if not match:
        raise EvalError(f"could not read the Claude Code version from {out!r}")
    return tuple(int(x) for x in match.groups())


# Credentials that would make Claude Code bill the Claude API per token
# instead of using the subscription the claude-code provider is meant for.
API_CREDENTIALS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


def claude_code_env() -> dict[str, str]:
    """The environment for one `claude -p`: the user's, without API credentials,
    with CLAUDE.md files, auto memory and bundled skills switched off."""
    env = {k: v for k, v in os.environ.items() if k not in API_CREDENTIALS}
    env.update(CLAUDE_CODE_DISABLE_CLAUDE_MDS="1",
               CLAUDE_CODE_DISABLE_AUTO_MEMORY="1",
               CLAUDE_CODE_DISABLE_BUNDLED_SKILLS="1")
    return env


def parse_stream(lines: list[str], server: str) -> RunResult:
    """Turn `claude -p --output-format stream-json --verbose` output into a RunResult."""
    result = RunResult()
    final = None
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        event = json.loads(line)
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            result.model = event.get("model")
            result.tools = list(event.get("tools") or [])
            status ={s.get("name"): s.get("status") for s in event.get("mcp_servers") or []}
            if status.get(server) != "connected":
                result.error, result.detail = "mcp_not_connected", f"{server}: {status.get(server)}"
        elif kind in {"assistant", "user"}:
            for block in (event.get("message") or {}).get("content") or []:
                result.trace.extend(_trace_turns(kind, block))
        elif kind == "result":
            final = event
    for turn in result.trace:
        if turn["role"] == "tool_call" and turn["name"] != STRUCTURED_TOOL:
            result.tool_calls += 1
    if final is None:
        result.error = result.error or "harness_error"
        result.detail = result.detail or "no result event in the stream"
        return result
    result.usage = {**(final.get("usage") or {}), "by_model": final.get("modelUsage") or {}}
    result.turns = final.get("num_turns") or 0
    result.cost_usd = final.get("total_cost_usd")
    result.stop_reason = final.get("stop_reason")
    result.answer = final.get("structured_output")
    if result.error is None:
        if result.stop_reason == "refusal":
            result.error = "refused"
        elif final.get("is_error"):
            result.error, result.detail = "harness_error", str(final.get("result") or final.get("subtype"))
        elif result.answer is None:
            result.error, result.detail = "no_answer", str(final.get("result") or "")[:500]
    return result


def _trace_turns(kind: str, block: dict) -> list[dict]:
    btype = block.get("type")
    if btype == "text" and block.get("text", "").strip():
        return [{"role": "assistant", "content": block["text"]}]
    if btype == "tool_use":
        return [{"role": "tool_call", "name": block.get("name"), "content": json.dumps(block.get("input"), indent=2)}]
    if btype == "tool_result":
        content = block.get("content")
        if isinstance(content, list):
            content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
        return [{"role": "tool_result", "content": str(content), **({"is_error": True} if block.get("is_error") else {})}]
    return []


class ClaudeCodeProvider:
    name = "claude-code"
    default_model = "sonnet"

    def __init__(self, model: str | None = None):
        self.model = model or self.default_model
        self.binary = find_claude_code()
        self.version = claude_code_version(self.binary)
        if self.version < MIN_CLAUDE_CODE:
            raise EvalError(
                f"Claude Code {'.'.join(map(str, self.version))} does not wait for MCP servers in -p mode; "
                f"update to {'.'.join(map(str, MIN_CLAUDE_CODE))} or later (`claude update`), or set CLAUDE_BIN"
            )

    def describe(self) -> dict:
        return {"provider": self.name, "model": self.model, "claude_code": ".".join(map(str, self.version))}

    def command(self, prompt: str, schema: dict, arm: str, config: Path, system_prompt: str = SYSTEM_PROMPT) -> list[str]:
        return [
            self.binary, "-p", prompt,
            "--output-format", "stream-json", "--verbose",
            "--json-schema", json.dumps(schema),
            "--model", self.model,
            "--system-prompt", system_prompt,
            "--tools", "",
            "--strict-mcp-config", "--mcp-config", str(config),
            "--allowedTools", f"mcp__{ARMS[arm]['server']}",
            "--permission-mode", "dontAsk",
            "--no-session-persistence",
            "--setting-sources", "project",
        ]

    def run(self, question: str, arm: str, timeout_s: float, schema: dict | None = None, raw: bool = False,
            env: dict[str, str] | None = None) -> RunResult:
        server = ARMS[arm]["server"]
        system_prompt, default_schema = PROMPTS[ARMS[arm]["task"]]
        with tempfile.TemporaryDirectory(prefix="agent-eval-") as work:
            config = Path(work) / "mcp.json"
            config.write_text(json.dumps(mcp_config(arm, env)), encoding="utf-8")
            prompt = question if raw else user_message(question)
            started = time.perf_counter()
            try:
                proc = subprocess.run(self.command(prompt, schema or default_schema, arm, config, system_prompt), cwd=work,
                                      env=claude_code_env(),
                                      capture_output=True, text=True, encoding="utf-8", timeout=timeout_s)
            except subprocess.TimeoutExpired:
                return RunResult(error="timeout", detail=f"no answer within {timeout_s:.0f}s",
                                 latency_s=round(time.perf_counter() - started, 1))
        result = parse_stream(proc.stdout.splitlines(), server)
        result.latency_s = round(time.perf_counter() - started, 1)
        if proc.returncode != 0 and result.error is None:
            result.error, result.detail = "harness_error", (proc.stderr or "")[-500:]
        if result.error is None and not served_model_matches(self.model, result.model):
            result.error, result.detail = "model_mismatch", f"asked for {self.model}, served {result.model}"
        return result


# Claude API (written, not run yet)


class AnthropicApiProvider:
    """The same eval on the Claude API. Needs `uv sync --group eval-api` and ANTHROPIC_API_KEY.

    The harness is the MCP client: the API's own MCP connector only reaches
    remote servers, not a local stdio one. The answer arrives through a
    harness-only submit_answer tool, since Sonnet 5.5 rejects forced tool use.
    """

    name = "anthropic-api"
    default_model = "claude-sonnet-5-5"
    effort = "medium"
    max_turns = 30

    def __init__(self, model: str | None = None):
        try:
            import anthropic  # noqa: F401
        except ImportError as e:
            raise EvalError("the anthropic-api provider needs `uv sync --group eval-api`") from e
        self.model = model or self.default_model

    def describe(self) -> dict:
        import anthropic

        return {"provider": self.name, "model": self.model, "anthropic_sdk": anthropic.__version__, "effort": self.effort}

    def run(self, question: str, arm: str, timeout_s: float, schema: dict | None = None, raw: bool = False,
            env: dict[str, str] | None = None) -> RunResult:
        import asyncio

        system_prompt, default_schema = PROMPTS[ARMS[arm]["task"]]
        started = time.perf_counter()
        try:
            result = asyncio.run(asyncio.wait_for(
                self._run(question, arm, schema or default_schema, raw, system_prompt, env), timeout_s))
        except TimeoutError:
            result = RunResult(error="timeout", detail=f"no answer within {timeout_s:.0f}s")
        result.latency_s = round(time.perf_counter() - started, 1)
        return result

    async def _run(self, question: str, arm: str, schema: dict, raw: bool, system_prompt: str,
                   env: dict[str, str] | None) -> RunResult:
        import anthropic
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        client = anthropic.AsyncAnthropic()
        result = RunResult(model=self.model)
        totals: dict[str, int] = {}
        params = StdioServerParameters(command=sys.executable, args=[str(ARMS[arm]["script"])],
                                       env={**os.environ, **env} if env else None)
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            listed = (await session.list_tools()).tools
            tools = [{"name": t.name, "description": t.description or "", "input_schema": t.input_schema} for t in listed]
            tools.append({"name": "submit_answer", "description": "Submit the final answer. Call it exactly once, last.",
                          "input_schema": schema, "strict": True})
            result.tools = [t["name"] for t in tools]
            messages = [{"role": "user", "content": question if raw else user_message(question)}]
            result.trace.append({"role": "system", "content": system_prompt})
            result.trace.append({"role": "user", "content": messages[0]["content"]})
            for _ in range(self.max_turns):
                response = await client.beta.messages.create(
                    model=self.model,
                    max_tokens=16000,
                    system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                    tools=tools,
                    tool_choice={"type": "auto"},
                    messages=messages,
                    output_config={"effort": self.effort},
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
                result.turns += 1
                for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                    totals[key] = totals.get(key, 0) + (getattr(response.usage, key, 0) or 0)
                if any(getattr(i, "type", "") == "fallback_message" for i in (response.usage.iterations or [])):
                    result.error, result.detail = "model_mismatch", f"answered by a fallback model: {response.model}"
                result.model = response.model
                result.stop_reason = response.stop_reason
                if response.stop_reason in {"refusal", "max_tokens"}:
                    result.error = result.error or ("refused" if response.stop_reason == "refusal" else "harness_error")
                    break
                messages.append({"role": "assistant", "content": response.content})
                calls = [b for b in response.content if b.type == "tool_use"]
                for block in response.content:
                    if block.type == "text" and block.text.strip():
                        result.trace.append({"role": "assistant", "content": block.text})
                submitted = next((b for b in calls if b.name == "submit_answer"), None)
                if submitted is not None:
                    result.answer = dict(submitted.input)
                    result.trace.append({"role": "tool_call", "name": "submit_answer", "content": json.dumps(submitted.input, indent=2)})
                    break
                if not calls:
                    result.error = result.error or "no_answer"
                    break
                outcomes = []
                for call in calls:
                    result.tool_calls += 1
                    result.trace.append({"role": "tool_call", "name": call.name, "content": json.dumps(call.input, indent=2)})
                    tool = await session.call_tool(call.name, dict(call.input))
                    text = "\n".join(getattr(c, "text", "") for c in tool.content)
                    result.trace.append({"role": "tool_result", "content": text})
                    outcomes.append({"type": "tool_result", "tool_use_id": call.id, "content": text,
                                     "is_error": bool(tool.is_error)})
                messages.append({"role": "user", "content": outcomes})  # every result in one message
            else:
                result.error = result.error or "no_answer"
        result.usage = totals
        if result.answer is None and result.error is None:
            result.error = "no_answer"
        return result


PROVIDERS = {ClaudeCodeProvider.name: ClaudeCodeProvider, AnthropicApiProvider.name: AnthropicApiProvider}

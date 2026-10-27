"""A thin client for the semantic layer, through MetricFlow's Python engine.

The same engine `mf query` uses, with two rules learned in step 3:
- run with the dbt folder as project and profiles dir, and an absolute path
  to the DuckDB file (the profile's path is relative to the working folder);
- pass each filter as its own where constraint. Joined with "and" into one
  string, MetricFlow pushes a time filter below a derived metric's offset
  and days_of_cover comes back empty.
Every user of this client only reads, so the warehouse is opened read-only:
the golden runner, the export and several MCP servers can share the file.
"""

import json
import os
from pathlib import Path

DBT_DIR = Path(__file__).resolve().parent.parent / "dbt"
DUCKDB_FILE = DBT_DIR / "groundrules.duckdb"
SEMANTIC_MANIFEST = DBT_DIR / "target" / "semantic_manifest.json"
# DuckDB refuses a second connection in one process with a different config,
# so direct connections next to this client must pass exactly this.
READ_ONLY = {"access_mode": "READ_ONLY"}


class SemanticLayer:
    def __init__(self, dbt_dir: Path = DBT_DIR):
        if not (dbt_dir / "groundrules.duckdb").exists() or not (dbt_dir / "target" / "semantic_manifest.json").exists():
            raise FileNotFoundError("No warehouse or semantic manifest: run `make data && make build` first.")
        os.environ["GROUNDRULES_DUCKDB"] = str(dbt_dir / "groundrules.duckdb")
        os.environ["GROUNDRULES_DUCKDB_ACCESS"] = READ_ONLY["access_mode"]  # read by profiles.yml
        from dbt_metricflow.cli.cli_configuration import CLIConfiguration
        from metricflow.engine.metricflow_engine import MetricFlowQueryRequest

        self._request = MetricFlowQueryRequest
        self._cfg = CLIConfiguration()
        self._cfg.setup(dbt_profiles_path=dbt_dir, dbt_project_path=dbt_dir, configure_file_logging=False)
        manifest = json.loads((dbt_dir / "target" / "semantic_manifest.json").read_text(encoding="utf-8"))
        self.metrics = {m["name"]: m for m in manifest["metrics"]}

    def query(self, metrics: list[str], group_by: list[str], where: list[str] | None = None) -> list[dict]:
        """Run one query; each item of `where` is its own constraint."""
        request = self._request.create(
            metric_names=metrics or None, group_by_names=group_by, where_constraints=list(where or [])
        )
        table = self._cfg.mf.query(request).result_df
        names = [c.column_name for c in table.column_descriptions]
        return [dict(zip(names, row)) for row in table.rows]

    def saved_query(self, name: str) -> list[dict]:
        """Run a dbt saved query by name, exactly as it is defined in the project."""
        table = self._cfg.mf.query(self._request.create(saved_query_name=name)).result_df
        names = [c.column_name for c in table.column_descriptions]
        return [dict(zip(names, row)) for row in table.rows]

    def governance(self, metric: str) -> dict:
        """The metric's governance fields, or {} for a building block or an unknown name."""
        found = self.metrics.get(metric) or {}
        # The v2 parser writes `config: null` for metrics without config.
        return dict((found.get("config") or {}).get("meta") or {})

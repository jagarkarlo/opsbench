"""Model Context Protocol (MCP) context adapters for GitHub, GitLab, Jira, Grafana, and Kubernetes."""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import json
from typing import Any, Protocol, Sequence

from opsbench.scenarios import ScenarioPack


@dataclass(frozen=True)
class MCPResource:
    """A content-addressed or URI-identified resource exposed by an MCP adapter."""

    uri: str
    name: str
    media_type: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.uri, str) or not self.uri.strip():
            raise ValueError("uri must be a non-empty string")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if not isinstance(self.media_type, str) or "/" not in self.media_type:
            raise ValueError("media_type must be a valid MIME type")
        if not isinstance(self.content, str):
            raise ValueError("content must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "media_type": self.media_type,
            "metadata": dict(self.metadata),
            "name": self.name,
            "uri": self.uri,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPResource:
        return cls(
            uri=str(data["uri"]),
            name=str(data["name"]),
            media_type=str(data["media_type"]),
            content=str(data["content"]),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class MCPToolDefinition:
    """Tool schema declaration exposed to LLMs via an MCP server/adapter."""

    name: str
    description: str
    parameters_schema: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "name": self.name,
            "parameters_schema": dict(self.parameters_schema),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPToolDefinition:
        return cls(
            name=str(data["name"]),
            description=str(data["description"]),
            parameters_schema=dict(data.get("parameters_schema", {})),
        )


@dataclass(frozen=True)
class MCPContextPayload:
    """Aggregated bundle of contextual resources and tools resolved for an incident."""

    provider: str
    resources: tuple[MCPResource, ...]
    tools: tuple[MCPToolDefinition, ...]
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError("provider must be a non-empty string")
        if not isinstance(self.resources, tuple):
            raise ValueError("resources must be a tuple of MCPResource")
        if not isinstance(self.tools, tuple):
            raise ValueError("tools must be a tuple of MCPToolDefinition")

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "resources": [r.to_dict() for r in self.resources],
            "timestamp": self.timestamp,
            "tools": [t.to_dict() for t in self.tools],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPContextPayload:
        return cls(
            provider=str(data["provider"]),
            resources=tuple(MCPResource.from_dict(r) for r in data.get("resources", [])),
            tools=tuple(MCPToolDefinition.from_dict(t) for t in data.get("tools", [])),
            timestamp=str(data.get("timestamp", "")),
        )


class MCPContextAdapter(Protocol):
    """Protocol for platform context providers conforming to Model Context Protocol concepts."""

    @property
    def provider_name(self) -> str:
        """The identifier of the context provider (e.g. 'jira', 'kubernetes')."""

    def get_available_resources(self, pack: ScenarioPack) -> Sequence[MCPResource]:
        """Produce available contextual resources pertinent to this scenario."""

    def get_tool_definitions(self) -> Sequence[MCPToolDefinition]:
        """Declare tools that this adapter provides for live inspection."""

    def invoke_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute one tool invocation against this adapter."""


class JiraMCPAdapter:
    """MCP context adapter for Atlassian Jira issue tracking and incident tickets."""

    def __init__(self, *, project_key: str = "OPS", adapter_name: str = "jira") -> None:
        self._project_key = project_key
        self._name = adapter_name

    @property
    def provider_name(self) -> str:
        return self._name

    def get_available_resources(self, pack: ScenarioPack) -> Sequence[MCPResource]:
        issue_key = f"{self._project_key}-101"
        issue_body = {
            "key": issue_key,
            "fields": {
                "summary": f"Incident Investigation: {pack.manifest.title}",
                "description": f"Operational incident reported under {pack.manifest.category} category for scenario {pack.manifest.scenario_id}.",
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "category": pack.manifest.category,
                "scenario_id": pack.manifest.scenario_id,
            },
        }
        res_issue = MCPResource(
            uri=f"jira://issue/{issue_key}",
            name=f"Jira Ticket {issue_key}",
            media_type="application/json",
            content=json.dumps(issue_body, indent=2),
            metadata={"issue_key": issue_key, "scenario_id": pack.manifest.scenario_id},
        )
        return (res_issue,)

    def get_tool_definitions(self) -> Sequence[MCPToolDefinition]:
        return (
            MCPToolDefinition(
                name="jira_get_issue",
                description="Fetch details of a specific Jira issue ticket",
                parameters_schema={"type": "object", "properties": {"issue_key": {"type": "string"}}, "required": ["issue_key"]},
            ),
            MCPToolDefinition(
                name="jira_search_issues",
                description="Search Jira issues using JQL syntax",
                parameters_schema={"type": "object", "properties": {"jql": {"type": "string"}}, "required": ["jql"]},
            ),
        )

    def invoke_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "jira_get_issue":
            key = str(arguments.get("issue_key", f"{self._project_key}-101"))
            return {
                "key": key,
                "status": "In Progress",
                "summary": f"Operational issue {key}",
                "priority": "High",
            }
        elif tool_name == "jira_search_issues":
            jql = str(arguments.get("jql", ""))
            return {
                "jql": jql,
                "total": 1,
                "issues": [{"key": f"{self._project_key}-101", "summary": "Active incident ticket"}],
            }
        raise ValueError(f"unknown Jira tool: {tool_name}")


class GitHubMCPAdapter:
    """MCP context adapter for GitHub repositories, pull requests, and commit histories."""

    def __init__(self, *, repository: str = "org/repo", adapter_name: str = "github") -> None:
        self._repo = repository
        self._name = adapter_name

    @property
    def provider_name(self) -> str:
        return self._name

    def get_available_resources(self, pack: ScenarioPack) -> Sequence[MCPResource]:
        commit_content = {
            "repository": self._repo,
            "commit_sha": "a1b2c3d4e5f678901234567890abcdef12345678",
            "message": f"fix({pack.manifest.category}): deploy updates for {pack.manifest.scenario_id}",
            "author": "devops-bot@company.internal",
            "date": "2026-09-04T06:00:00Z",
        }
        res_commit = MCPResource(
            uri=f"github://repo/{self._repo}/commits/latest",
            name="Latest GitHub Commit",
            media_type="application/json",
            content=json.dumps(commit_content, indent=2),
            metadata={"repository": self._repo},
        )
        return (res_commit,)

    def get_tool_definitions(self) -> Sequence[MCPToolDefinition]:
        return (
            MCPToolDefinition(
                name="github_get_pull_request",
                description="Get pull request details and changed files",
                parameters_schema={"type": "object", "properties": {"pr_number": {"type": "integer"}}, "required": ["pr_number"]},
            ),
            MCPToolDefinition(
                name="github_get_commit",
                description="Retrieve git commit message and diff summary",
                parameters_schema={"type": "object", "properties": {"sha": {"type": "string"}}, "required": ["sha"]},
            ),
        )

    def invoke_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "github_get_pull_request":
            pr_num = int(arguments.get("pr_number", 42))
            return {
                "number": pr_num,
                "title": f"Update infrastructure configurations (PR #{pr_num})",
                "state": "merged",
                "changed_files": 3,
            }
        elif tool_name == "github_get_commit":
            sha = str(arguments.get("sha", "a1b2c3d"))
            return {
                "sha": sha,
                "message": f"Commit {sha} applied to master",
                "files_changed": ["manifest.yaml", "config.json"],
            }
        raise ValueError(f"unknown GitHub tool: {tool_name}")


class GitLabMCPAdapter:
    """MCP context adapter for GitLab CI/CD pipelines, jobs, and merge requests."""

    def __init__(self, *, project_path: str = "cloudops/infrastructure", adapter_name: str = "gitlab") -> None:
        self._project = project_path
        self._name = adapter_name

    @property
    def provider_name(self) -> str:
        return self._name

    def get_available_resources(self, pack: ScenarioPack) -> Sequence[MCPResource]:
        pipeline_info = {
            "project": self._project,
            "pipeline_id": 98765,
            "ref": "main",
            "status": "failed" if "error" in pack.manifest.scenario_id or "fail" in pack.manifest.scenario_id else "running",
            "stages": [
                {"name": "build", "status": "success"},
                {"name": "test", "status": "success"},
                {"name": "deploy", "status": "failed"},
            ],
        }
        res_pipeline = MCPResource(
            uri=f"gitlab://project/{self._project}/pipelines/latest",
            name="Latest GitLab Pipeline",
            media_type="application/json",
            content=json.dumps(pipeline_info, indent=2),
            metadata={"project": self._project},
        )
        return (res_pipeline,)

    def get_tool_definitions(self) -> Sequence[MCPToolDefinition]:
        return (
            MCPToolDefinition(
                name="gitlab_get_pipeline_status",
                description="Fetch GitLab CI/CD pipeline execution status and failed jobs",
                parameters_schema={"type": "object", "properties": {"pipeline_id": {"type": "integer"}}, "required": ["pipeline_id"]},
            ),
            MCPToolDefinition(
                name="gitlab_get_merge_request",
                description="Retrieve GitLab merge request status and discussion threads",
                parameters_schema={"type": "object", "properties": {"mr_iid": {"type": "integer"}}, "required": ["mr_iid"]},
            ),
        )

    def invoke_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "gitlab_get_pipeline_status":
            pid = int(arguments.get("pipeline_id", 98765))
            return {
                "pipeline_id": pid,
                "status": "failed",
                "failed_jobs": ["deploy_to_k8s"],
            }
        elif tool_name == "gitlab_get_merge_request":
            mr = int(arguments.get("mr_iid", 12))
            return {
                "iid": mr,
                "title": f"Resolve deployment drift (MR !{mr})",
                "state": "opened",
                "pipeline_status": "passed",
            }
        raise ValueError(f"unknown GitLab tool: {tool_name}")


class GrafanaMCPAdapter:
    """MCP context adapter for Grafana dashboards, Loki log queries, and Prometheus alerts."""

    def __init__(self, *, endpoint: str = "http://grafana:3000", adapter_name: str = "grafana") -> None:
        self._endpoint = endpoint
        self._name = adapter_name

    @property
    def provider_name(self) -> str:
        return self._name

    def get_available_resources(self, pack: ScenarioPack) -> Sequence[MCPResource]:
        alert_info = {
            "alerts": [
                {
                    "rule_name": f"{pack.manifest.category.upper()}_Service_Degraded",
                    "state": "Firing",
                    "severity": "critical",
                    "scenario_id": pack.manifest.scenario_id,
                    "active_since": "2026-09-04T07:10:00Z",
                    "labels": {"alertname": "ServiceDegraded", "category": pack.manifest.category},
                    "annotations": {"summary": f"Detected degradation in {pack.manifest.title}"},
                }
            ]
        }
        res_alerts = MCPResource(
            uri="grafana://alerting/firing-rules",
            name="Grafana Firing Alert Rules",
            media_type="application/json",
            content=json.dumps(alert_info, indent=2),
            metadata={"endpoint": self._endpoint},
        )
        return (res_alerts,)

    def get_tool_definitions(self) -> Sequence[MCPToolDefinition]:
        return (
            MCPToolDefinition(
                name="grafana_query_metrics",
                description="Execute a PromQL metric expression query against Prometheus via Grafana",
                parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            ),
            MCPToolDefinition(
                name="grafana_get_firing_alerts",
                description="List all active alerts currently in firing or pending state",
                parameters_schema={"type": "object", "properties": {}, "required": []},
            ),
        )

    def invoke_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "grafana_query_metrics":
            q = str(arguments.get("query", "up"))
            return {
                "query": q,
                "resultType": "vector",
                "result": [{"metric": {"__name__": "up", "job": "node"}, "value": [1788500000, "1"]}],
            }
        elif tool_name == "grafana_get_firing_alerts":
            return {
                "active_alerts_count": 1,
                "alerts": [{"name": "HighLatency", "severity": "warning", "state": "firing"}],
            }
        raise ValueError(f"unknown Grafana tool: {tool_name}")


class KubernetesMCPAdapter:
    """MCP context adapter for Kubernetes pods, namespaces, deployments, and cluster events."""

    def __init__(self, *, default_namespace: str = "default", adapter_name: str = "kubernetes") -> None:
        self._namespace = default_namespace
        self._name = adapter_name

    @property
    def provider_name(self) -> str:
        return self._name

    def get_available_resources(self, pack: ScenarioPack) -> Sequence[MCPResource]:
        cluster_info = {
            "namespace": self._namespace,
            "scenario_id": pack.manifest.scenario_id,
            "pods": [
                {
                    "name": f"{pack.manifest.category}-workload-7b8f9c-xyz",
                    "status": "Running" if "healthy" in pack.manifest.scenario_id else "CrashLoopBackOff",
                    "restart_count": 5,
                    "ready": "0/1",
                }
            ],
            "events": [
                {
                    "type": "Warning",
                    "reason": "BackOff",
                    "message": f"Back-off restarting failed container in scenario {pack.manifest.scenario_id}",
                }
            ],
        }
        res_k8s = MCPResource(
            uri=f"k8s://namespaces/{self._namespace}/status",
            name="Kubernetes Namespace Status",
            media_type="application/json",
            content=json.dumps(cluster_info, indent=2),
            metadata={"namespace": self._namespace},
        )
        return (res_k8s,)

    def get_tool_definitions(self) -> Sequence[MCPToolDefinition]:
        return (
            MCPToolDefinition(
                name="k8s_get_pod_status",
                description="Inspect status, conditions, and restart counts for a Kubernetes pod",
                parameters_schema={"type": "object", "properties": {"pod_name": {"type": "string"}, "namespace": {"type": "string"}}, "required": ["pod_name"]},
            ),
            MCPToolDefinition(
                name="k8s_get_warning_events",
                description="List recent cluster warning events within a namespace",
                parameters_schema={"type": "object", "properties": {"namespace": {"type": "string"}}, "required": []},
            ),
        )

    def invoke_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "k8s_get_pod_status":
            name = str(arguments.get("pod_name", "workload-01"))
            ns = str(arguments.get("namespace", self._namespace))
            return {
                "name": name,
                "namespace": ns,
                "phase": "Failed",
                "restarts": 4,
            }
        elif tool_name == "k8s_get_warning_events":
            ns = str(arguments.get("namespace", self._namespace))
            return {
                "namespace": ns,
                "events": [{"reason": "FailedScheduling", "message": "0/3 nodes available"}],
            }
        raise ValueError(f"unknown Kubernetes tool: {tool_name}")


class MCPRegistry:
    """Central registry managing MCP context adapters for OpsBench."""

    def __init__(self) -> None:
        self._adapters: dict[str, MCPContextAdapter] = {}

    def register(self, adapter: MCPContextAdapter) -> None:
        if not hasattr(adapter, "provider_name") or not isinstance(adapter.provider_name, str):
            raise ValueError("adapter must have a valid string provider_name")
        self._adapters[adapter.provider_name] = adapter

    def get(self, provider_name: str) -> MCPContextAdapter:
        if provider_name not in self._adapters:
            raise KeyError(f"no MCP adapter registered for provider: {provider_name}")
        return self._adapters[provider_name]

    def list_providers(self) -> list[str]:
        return sorted(self._adapters.keys())

    def collect_context(
        self,
        pack: ScenarioPack,
        providers: Sequence[str] | None = None,
    ) -> list[MCPContextPayload]:
        selected = self.list_providers() if providers is None else list(providers)
        results: list[MCPContextPayload] = []
        for p in selected:
            if p in self._adapters:
                ad = self._adapters[p]
                res = tuple(ad.get_available_resources(pack))
                tools = tuple(ad.get_tool_definitions())
                results.append(
                    MCPContextPayload(
                        provider=p,
                        resources=res,
                        tools=tools,
                    )
                )
        return results

    @classmethod
    def create_default(cls) -> MCPRegistry:
        """Create a pre-configured registry containing all standard ecosystem adapters."""
        reg = cls()
        reg.register(JiraMCPAdapter())
        reg.register(GitHubMCPAdapter())
        reg.register(GitLabMCPAdapter())
        reg.register(GrafanaMCPAdapter())
        reg.register(KubernetesMCPAdapter())
        return reg

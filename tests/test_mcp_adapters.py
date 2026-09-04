from pathlib import Path
import unittest

from opsbench.mcp_adapters import (
    GitHubMCPAdapter,
    GitLabMCPAdapter,
    GrafanaMCPAdapter,
    JiraMCPAdapter,
    KubernetesMCPAdapter,
    MCPContextPayload,
    MCPRegistry,
    MCPResource,
    MCPToolDefinition,
)
from opsbench.prompts import render_prompt
from opsbench.scenarios import (
    EvidenceArtifact,
    ScenarioManifest,
    ScenarioPack,
)


class MCPAdaptersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = ScenarioManifest(
            scenario_id="kubernetes-ingress-502",
            title="Diagnose Ingress 502",
            category="kubernetes",
        )
        self.pack = ScenarioPack(
            manifest=self.manifest,
            evidence=(EvidenceArtifact("ingress.yaml", "text/plain", b"apiVersion: v1\n"),),
        )

    def test_mcp_resource_serialization(self) -> None:
        res = MCPResource(
            uri="k8s://pods/ingress-controller",
            name="Ingress Controller Pod",
            media_type="application/json",
            content='{"status": "degraded"}',
            metadata={"namespace": "ingress-nginx"},
        )
        data = res.to_dict()
        restored = MCPResource.from_dict(data)
        self.assertEqual(restored.uri, "k8s://pods/ingress-controller")
        self.assertEqual(restored.metadata["namespace"], "ingress-nginx")

        with self.assertRaises(ValueError):
            MCPResource("", "name", "text/plain", "content")
        with self.assertRaises(ValueError):
            MCPResource("uri", "name", "invalid-type", "content")

    def test_mcp_tool_definition_serialization(self) -> None:
        tool = MCPToolDefinition(
            name="k8s_get_pod",
            description="Fetch pod information",
            parameters_schema={"type": "object", "properties": {"pod_name": {"type": "string"}}},
        )
        data = tool.to_dict()
        restored = MCPToolDefinition.from_dict(data)
        self.assertEqual(restored.name, "k8s_get_pod")
        self.assertEqual(restored.parameters_schema["type"], "object")

        with self.assertRaises(ValueError):
            MCPToolDefinition("", "desc")

    def test_jira_mcp_adapter(self) -> None:
        adapter = JiraMCPAdapter(project_key="INC")
        self.assertEqual(adapter.provider_name, "jira")
        resources = adapter.get_available_resources(self.pack)
        self.assertEqual(len(resources), 1)
        self.assertIn("jira://issue/INC-101", resources[0].uri)
        self.assertIn("Diagnose Ingress 502", resources[0].content)

        tools = adapter.get_tool_definitions()
        self.assertEqual(len(tools), 2)
        tool_names = {t.name for t in tools}
        self.assertIn("jira_get_issue", tool_names)
        self.assertIn("jira_search_issues", tool_names)

        issue_res = adapter.invoke_tool("jira_get_issue", {"issue_key": "INC-101"})
        self.assertEqual(issue_res["key"], "INC-101")
        self.assertEqual(issue_res["status"], "In Progress")

        with self.assertRaises(ValueError):
            adapter.invoke_tool("unknown_tool", {})

    def test_github_mcp_adapter(self) -> None:
        adapter = GitHubMCPAdapter(repository="cloudops/ingress-gateway")
        self.assertEqual(adapter.provider_name, "github")
        resources = adapter.get_available_resources(self.pack)
        self.assertEqual(len(resources), 1)
        self.assertIn("github://repo/cloudops/ingress-gateway/commits/latest", resources[0].uri)

        tools = adapter.get_tool_definitions()
        self.assertEqual(len(tools), 2)
        pr_info = adapter.invoke_tool("github_get_pull_request", {"pr_number": 105})
        self.assertEqual(pr_info["number"], 105)
        self.assertEqual(pr_info["state"], "merged")

    def test_gitlab_mcp_adapter(self) -> None:
        adapter = GitLabMCPAdapter(project_path="core/edge-proxy")
        self.assertEqual(adapter.provider_name, "gitlab")
        resources = adapter.get_available_resources(self.pack)
        self.assertEqual(len(resources), 1)
        self.assertIn("gitlab://project/core/edge-proxy/pipelines/latest", resources[0].uri)

        pipeline_status = adapter.invoke_tool("gitlab_get_pipeline_status", {"pipeline_id": 1234})
        self.assertEqual(pipeline_status["pipeline_id"], 1234)
        self.assertEqual(pipeline_status["status"], "failed")

    def test_grafana_mcp_adapter(self) -> None:
        adapter = GrafanaMCPAdapter(endpoint="http://monitoring.internal:3000")
        self.assertEqual(adapter.provider_name, "grafana")
        resources = adapter.get_available_resources(self.pack)
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].uri, "grafana://alerting/firing-rules")
        self.assertIn("Firing", resources[0].content)

        metrics = adapter.invoke_tool("grafana_query_metrics", {"query": "http_requests_total"})
        self.assertEqual(metrics["query"], "http_requests_total")

    def test_kubernetes_mcp_adapter(self) -> None:
        adapter = KubernetesMCPAdapter(default_namespace="kube-system")
        self.assertEqual(adapter.provider_name, "kubernetes")
        resources = adapter.get_available_resources(self.pack)
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].uri, "k8s://namespaces/kube-system/status")

        pod_info = adapter.invoke_tool("k8s_get_pod_status", {"pod_name": "coredns-1", "namespace": "kube-system"})
        self.assertEqual(pod_info["name"], "coredns-1")
        self.assertEqual(pod_info["namespace"], "kube-system")

    def test_mcp_registry_and_context_collection(self) -> None:
        registry = MCPRegistry.create_default()
        providers = registry.list_providers()
        self.assertEqual(providers, ["github", "gitlab", "grafana", "jira", "kubernetes"])

        # Collect subset
        contexts = registry.collect_context(self.pack, providers=["jira", "kubernetes"])
        self.assertEqual(len(contexts), 2)
        self.assertEqual({c.provider for c in contexts}, {"jira", "kubernetes"})

        with self.assertRaises(KeyError):
            registry.get("nonexistent")

    def test_prompt_rendering_with_mcp_context(self) -> None:
        registry = MCPRegistry.create_default()
        contexts = registry.collect_context(self.pack, providers=["jira", "grafana"])
        prompt = render_prompt(self.pack, mcp_contexts=contexts)

        self.assertIn("## MCP Platform Context", prompt)
        self.assertIn("### Provider: jira", prompt)
        self.assertIn("jira://issue/OPS-101", prompt)
        self.assertIn("### Provider: grafana", prompt)
        self.assertIn("Available MCP Tools:", prompt)
        self.assertIn("- `jira_get_issue`:", prompt)
        self.assertIn("- `grafana_query_metrics`:", prompt)


if __name__ == "__main__":
    unittest.main()

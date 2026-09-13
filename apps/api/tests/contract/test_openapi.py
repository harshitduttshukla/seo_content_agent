from app.config.settings import Settings
from app.main import create_app


def test_phase3_openapi_contract_contains_expected_resources() -> None:
    schema = create_app(Settings(_env_file=None)).openapi()
    paths = set(schema["paths"])

    # SaaS Foundation (Phase 1)
    assert "/api/v1/organizations" in paths
    assert "/api/v1/projects/{project_id}" in paths
    assert "/api/v1/projects/{project_id}/websites" in paths
    assert "/api/v1/websites/{website_id}" in paths

    # Crawling (Phase 2)
    assert "/api/v1/websites/{website_id}/crawl-jobs" in paths
    assert "/api/v1/websites/{website_id}/pages" in paths

    # Strategy, Keywords, Clusters, and Content Architecture (Phase 3)
    assert "/api/v1/projects/{project_id}/strategy" in paths
    assert "/api/v1/projects/{project_id}/strategy/generate" in paths
    assert "/api/v1/projects/{project_id}/keywords" in paths
    keyword_item_path = schema["paths"]["/api/v1/projects/{project_id}/keywords/{keyword_id}"]
    assert "put" in keyword_item_path
    assert "delete" in keyword_item_path
    assert "/api/v1/projects/{project_id}/clustering-runs" in paths
    assert "/api/v1/projects/{project_id}/clusters" in paths
    assert "delete" in schema["paths"]["/api/v1/projects/{project_id}/clusters/{cluster_id}"]
    assert "/api/v1/projects/{project_id}/content-pillars" in paths
    assert "/api/v1/projects/{project_id}/topics" in paths
    assert "/api/v1/projects/{project_id}/content-opportunities" in paths
    assert "/api/v1/projects/{project_id}/content-architecture/graph" in paths

    # Governed tool catalog (Phase 6)
    assert "/api/v1/orchestrator/tools" in paths
    tool_descriptor = schema["components"]["schemas"]["ToolDescriptorDTO"]
    assert {
        "name",
        "description",
        "input_schema",
        "output_schema",
        "authentication_requirements",
        "permissions",
        "cost",
        "rate_limits",
        "availability",
        "version",
    }.issubset(tool_descriptor["required"])

    # Future Phase 4+ features must NOT be exposed yet
    assert not any(
        "/ai/writer" in path or "/publishing" in path or "/planner" in path for path in paths
    )

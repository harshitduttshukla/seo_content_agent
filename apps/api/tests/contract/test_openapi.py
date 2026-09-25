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


def test_v3_card_workflow_contract_stops_at_approval() -> None:
    schema = create_app(Settings(_env_file=None)).openapi()
    paths = set(schema["paths"])
    card = "/api/v3/content-hub/cards/{card_id}"
    for suffix in (
        "",
        "/bundle",
        "/outline",
        "/outline/generate",
        "/g1/approve",
        "/g1/send-back",
        "/draft/generate",
        "/qa/run",
        "/qa/repair",
        "/sections/{section_id}/regenerate",
        "/g2/approve",
        "/g2/send-back",
        "/g2/warning-dismiss",
    ):
        assert card + suffix in paths
    for run in ("v3-outline-runs", "v3-draft-runs", "v3-production-runs"):
        assert f"/api/v1/content-harness/{run}" in paths
    # Publishing, CMS and the live transition belong to later phases.
    hub = [p for p in paths if p.startswith("/api/v3/content-hub/")]
    assert not any(word in p for p in hub for word in ("/publish", "/cms", "/live", "/export"))
    send_back = schema["components"]["schemas"]["G2SendBackRequest"]
    assert {"revision", "reason", "feedback"} <= set(send_back["required"])

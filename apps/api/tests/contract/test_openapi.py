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


def test_v3_card_workflow_contract_stops_at_the_draft() -> None:
    schema = create_app(Settings(_env_file=None)).openapi()
    paths = set(schema["paths"])
    card = "/api/v3/content-hub/cards/{card_id}"
    for suffix in ("", "/bundle", "/outline", "/outline/generate", "/g1/approve", "/g1/send-back",
                   "/draft/generate"):  # fmt: skip
        assert card + suffix in paths
    assert "/api/v1/content-harness/v3-draft-runs" in paths
    # QA, G2, final approval and publishing belong to later phases.
    hub = [p for p in paths if p.startswith("/api/v3/content-hub/")]
    assert not any(word in p for p in hub for word in ("/qa", "/g2", "/publish", "/approve-final"))
    send_back = schema["components"]["schemas"]["G1SendBackRequest"]
    assert {"revision", "reason", "feedback"} <= set(send_back["required"])

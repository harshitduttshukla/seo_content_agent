from app.config.settings import Settings
from app.main import create_app


def test_phase1_openapi_contract_contains_only_foundation_resources() -> None:
    schema = create_app(Settings(_env_file=None)).openapi()
    paths = set(schema["paths"])

    assert "/api/v1/organizations" in paths
    assert "/api/v1/projects/{project_id}" in paths
    assert "/api/v1/projects/{project_id}/websites" in paths
    assert "/api/v1/websites/{website_id}" in paths
    assert not any("keyword" in path or "strategy" in path or "/ai" in path for path in paths)

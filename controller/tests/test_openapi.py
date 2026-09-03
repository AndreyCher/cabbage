from app.main import app


def test_openapi_exposes_complete_worker_control_contract():
    document = app.openapi()
    paths = document["paths"]
    assert "/api/v1/worker-config/schema" in paths
    assert "/api/v1/runs/{run_id}/runtime" in paths
    assert "/api/v1/runs/{run_id}/inputs/{key}" in paths
    assert "/api/v1/identities/{identity}/reset" in paths
    assert "/api/v1/identities/{identity}/update" in paths
    assert "/api/v1/proxies/{proxy_id}" in paths
    assert "/api/v1/settings/worker-defaults" in paths


def test_run_create_schema_does_not_expose_raw_docker_or_worker_api_fields():
    schema = app.openapi()["components"]["schemas"]["RunCreate"]
    properties = schema["properties"]
    assert "worker_config" in properties
    for forbidden in ("overrides", "image", "mounts", "network", "environment", "api"):
        assert forbidden not in properties


def test_context_defaults_expose_proxy_configuration_references():
    schemas = app.openapi()["components"]["schemas"]
    assert "default_proxy_config_id" in schemas["IdentityCreate"]["properties"]
    assert "default_proxy_config_id" in schemas["IdentityUpdate"]["properties"]
    assert "default_proxy_config_id" in schemas["IdentityRead"]["properties"]
    assert "default_proxy_config_id" in schemas["ScenarioCreate"]["properties"]
    assert "default_proxy_config_id" in schemas["ScenarioRead"]["properties"]

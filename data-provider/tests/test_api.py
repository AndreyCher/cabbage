import json

from fastapi import HTTPException

from app import main
from app.providers import DataResolver, JsonFileProvider


def test_health_exposes_component_version():
    response = main.health_v1()
    assert response["component"] == "data-provider"
    assert response["version"] == "0.1.0"


def test_versioned_and_compatibility_profile_endpoints(tmp_path):
    source = tmp_path / "profiles.json"
    source.write_text(json.dumps({"profiles": {"user-001": {"login": "demo"}}}))
    main.resolver = DataResolver([JsonFileProvider(source)])
    payload = {"id": "user-001", "identity": "test-user", "run_id": "run-1"}
    request = main.ProfileRequest(**payload)
    assert main.profile_v1(request) == {"login": "demo"}
    assert main.profile_compatibility(request) == {"login": "demo"}
    assert main.data_v1(main.DataRequest(namespace="profiles", key="user-001")) == {"login": "demo"}


def test_missing_profile_returns_404(tmp_path):
    source = tmp_path / "profiles.json"
    source.write_text('{"profiles": {}}')
    main.resolver = DataResolver([JsonFileProvider(source)])
    try:
        main.profile_v1(main.ProfileRequest(id="missing"))
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("missing profile must return HTTP 404")

import json

import httpx
import pytest

from riad_data.fabric import API, Fabric, FabricError


def fabric(handler):
    return Fabric(
        httpx.Client(base_url=API, transport=httpx.MockTransport(handler)), sleep=lambda s: None
    )


def capacities(*items):
    def handler(request):
        return httpx.Response(200, json={"value": list(items)})

    return handler


def test_trial_capacity_is_the_one_active_trial_sku():
    trial = {"id": "t", "displayName": "Trial-2026", "sku": "FT1", "state": "Active"}
    paid = {"id": "p", "displayName": "f2", "sku": "F2", "state": "Active"}
    assert fabric(capacities(trial, paid)).trial_capacity()["id"] == "t"


def test_no_trial_capacity_lists_what_exists():
    paused = {"id": "p", "displayName": "f2", "sku": "F2", "state": "Paused"}
    with pytest.raises(FabricError, match="active capacities: none"):
        fabric(capacities(paused)).trial_capacity()


def test_existing_workspace_is_reused():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(
            200, json={"value": [{"id": "w1", "displayName": "margin", "capacityId": "t"}]}
        )

    assert fabric(handler).ensure_workspace("margin", "t") == "w1"
    assert calls == [("GET", "/v1/workspaces")]


def test_missing_workspace_is_created_on_the_capacity():
    sent = {}

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"value": []})
        sent.update(json.loads(request.content))
        return httpx.Response(201, json={"id": "w2"})

    assert fabric(handler).ensure_workspace("margin", "t") == "w2"
    assert sent == {"displayName": "margin", "capacityId": "t"}


def test_lakehouse_creation_waits_for_the_long_running_operation():
    state = {"created": False, "polls": 0}

    def handler(request):
        path = request.url.path
        if request.method == "POST":
            assert json.loads(request.content)["creationPayload"] == {"enableSchemas": True}
            return httpx.Response(
                202, headers={"Location": f"{API}/operations/op1", "Retry-After": "1"}
            )
        if path.endswith("/operations/op1"):
            state["polls"] += 1
            state["created"] = state["polls"] >= 2
            return httpx.Response(
                200, json={"status": "Succeeded" if state["created"] else "Running"}
            )
        items = [{"id": "lh1", "displayName": "riad"}] if state["created"] else []
        return httpx.Response(200, json={"value": items})

    assert fabric(handler).ensure_lakehouse("w1", "riad") == "lh1"
    assert state["polls"] == 2


def test_sql_endpoint_waits_for_provisioning():
    statuses = iter(["InProgress", "Success"])

    def handler(request):
        status = next(statuses)
        endpoint = {
            "provisioningStatus": status,
            "connectionString": "x.datawarehouse.fabric.microsoft.com",
            "id": "sql1",
        }
        return httpx.Response(200, json={"properties": {"sqlEndpointProperties": endpoint}})

    assert fabric(handler).sql_endpoint("w1", "lh1") == (
        "x.datawarehouse.fabric.microsoft.com",
        "sql1",
    )


def test_viewer_role_is_added_once():
    posts = []

    def handler(request):
        if request.method == "POST":
            posts.append(json.loads(request.content))
            return httpx.Response(201, json={})
        existing = [{"principal": {"id": "g1"}}] if posts else []
        return httpx.Response(200, json={"value": existing})

    client = fabric(handler)
    assert client.ensure_viewer("w1", "g1") is True
    assert client.ensure_viewer("w1", "g1") is False
    assert posts == [{"principal": {"id": "g1", "type": "Group"}, "role": "Viewer"}]


def test_failed_operation_raises():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(202, headers={"Location": f"{API}/operations/op2"})
        return httpx.Response(200, json={"status": "Failed", "error": {"message": "boom"}})

    with pytest.raises(FabricError, match="operation failed"):
        fabric(handler).refresh_metadata("w1", "sql1")

"""The Fabric REST calls setup needs. Every step finds what exists before creating it."""

import time

import httpx

API = "https://api.fabric.microsoft.com/v1"


class FabricError(RuntimeError):
    pass


class Fabric:
    def __init__(self, http: httpx.Client, sleep=time.sleep) -> None:
        self.http = http  # base_url API, Authorization header set by the caller
        self.sleep = sleep

    def _get(self, path: str) -> dict:
        response = self.http.get(path)
        response.raise_for_status()
        return response.json()

    def _wait(self, response: httpx.Response) -> None:
        """Polls a long-running operation (202 + Location) until it succeeds."""
        if response.status_code != 202:
            response.raise_for_status()
            return
        location = response.headers["Location"]
        for _ in range(120):
            self.sleep(int(response.headers.get("Retry-After", "5")))
            state = self.http.get(location).json()
            if state.get("status") == "Succeeded":
                return
            if state.get("status") in ("Failed", "Undefined"):
                raise FabricError(f"operation failed: {state.get('error')}")
        raise FabricError("operation timed out")

    def trial_capacity(self, name: str | None = None) -> dict:
        capacities = [c for c in self._get("/capacities")["value"] if c.get("state") == "Active"]
        if name:
            matches = [c for c in capacities if c["displayName"] == name]
        else:
            matches = [
                c
                for c in capacities
                if c["sku"].upper().startswith("FT") or "trial" in c["sku"].lower()
            ]
        if len(matches) != 1:
            found = ", ".join(f"{c['displayName']} ({c['sku']})" for c in capacities) or "none"
            raise FabricError(f"expected one matching active capacity; active capacities: {found}")
        return matches[0]

    def ensure_workspace(self, name: str, capacity_id: str) -> str:
        found = [w for w in self._get("/workspaces")["value"] if w["displayName"] == name]
        if not found:
            response = self.http.post(
                "/workspaces", json={"displayName": name, "capacityId": capacity_id}
            )
            response.raise_for_status()
            return response.json()["id"]
        workspace = found[0]
        if workspace.get("capacityId") != capacity_id:
            response = self.http.post(
                f"/workspaces/{workspace['id']}/assignToCapacity", json={"capacityId": capacity_id}
            )
            self._wait(response)
        return workspace["id"]

    def ensure_lakehouse(self, workspace_id: str, name: str) -> str:
        def find() -> list[dict]:
            items = self._get(f"/workspaces/{workspace_id}/lakehouses")["value"]
            return [item for item in items if item["displayName"] == name]

        if not (found := find()):
            response = self.http.post(
                f"/workspaces/{workspace_id}/lakehouses",
                json={"displayName": name, "creationPayload": {"enableSchemas": True}},
            )
            self._wait(response)
            found = find()
        return found[0]["id"]

    def sql_endpoint(self, workspace_id: str, lakehouse_id: str) -> tuple[str, str]:
        """(connection string host, SQL endpoint id) once the endpoint is provisioned."""
        for _ in range(60):
            props = self._get(f"/workspaces/{workspace_id}/lakehouses/{lakehouse_id}")["properties"]
            endpoint = props.get("sqlEndpointProperties") or {}
            if endpoint.get("provisioningStatus") == "Success":
                return endpoint["connectionString"], endpoint["id"]
            if endpoint.get("provisioningStatus") == "Failed":
                raise FabricError("SQL endpoint provisioning failed")
            self.sleep(10)
        raise FabricError("SQL endpoint not ready after 10 minutes")

    def ensure_viewer(
        self, workspace_id: str, principal_id: str, principal_type: str = "Group"
    ) -> bool:
        assignments = self._get(f"/workspaces/{workspace_id}/roleAssignments")["value"]
        if any(a["principal"]["id"] == principal_id for a in assignments):
            return False
        response = self.http.post(
            f"/workspaces/{workspace_id}/roleAssignments",
            json={"principal": {"id": principal_id, "type": principal_type}, "role": "Viewer"},
        )
        response.raise_for_status()
        return True

    def refresh_metadata(self, workspace_id: str, sql_endpoint_id: str) -> None:
        response = self.http.post(
            f"/workspaces/{workspace_id}/sqlEndpoints/{sql_endpoint_id}/refreshMetadata", json={}
        )
        self._wait(response)

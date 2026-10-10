"""Minimal Freya v2 API client (spec: docs/freya/openapi-prod.json).

Every response is wrapped as {"success": bool, "data": {"message": str, "result": ...}};
this client unwraps to `result` and raises on success=false.
"""
from __future__ import annotations

import os
from typing import Any

import httpx


class FreyaError(RuntimeError):
    pass


class Freya:
    def __init__(
        self,
        api_key: str | None = None,
        workspace_id: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or os.environ["FREYA_API_KEY"]
        self.workspace_id = workspace_id or os.getenv("FREYA_WORKSPACE_ID")
        self.base_url = (base_url or os.getenv("FREYA_BASE_URL") or "https://app.freyavoice.ai/api/v2").rstrip("/")
        self.http = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=120,
        )

    def _req(self, method: str, path: str, **kw) -> Any:
        r = self.http.request(method, path, **kw)
        try:
            body = r.json()
        except ValueError:
            raise FreyaError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
        if r.status_code >= 400 or not body.get("success", False):
            raise FreyaError(f"{method} {path} -> {r.status_code}: {body}")
        return body.get("data", {}).get("result")

    def _ws(self, extra: dict | None = None) -> dict:
        p = {"workspaceId": self.workspace_id} if self.workspace_id else {}
        p.update(extra or {})
        return p

    # --- keys / workspace -------------------------------------------------
    def check_key(self) -> Any:
        return self._req("GET", "/api-keys/check")

    def workspaces(self) -> Any:
        return self._req("GET", "/workspaces")

    # --- agents -------------------------------------------------------------
    def agent_defaults(self, language: str | None = None) -> dict:
        return self._req("GET", "/agents/defaults", params=self._ws({"language": language} if language else None))

    def list_agents(self) -> Any:
        return self._req("GET", "/agents", params=self._ws({"entityType": "agent"}))

    def get_agent(self, agent_id: str) -> dict:
        return self._req("GET", f"/agents/{agent_id}", params=self._ws())

    def create_agent(self, name: str, config: dict, language: str | None = None) -> dict:
        body: dict = {"name": name, "config": config}
        if self.workspace_id:
            body["workspaceId"] = self.workspace_id
        if language:
            body["language"] = language
        return self._req("POST", "/agents", json=body)

    def update_agent(self, agent_id: str, name: str | None = None, config: dict | None = None) -> dict:
        body: dict = {}
        if self.workspace_id:
            body["workspaceId"] = self.workspace_id
        if name:
            body["name"] = name
        if config:
            body["config"] = config
        return self._req("PUT", f"/agents/{agent_id}", json=body)

    # --- text chat against an agent (fast iteration loop) -------------------
    def chat(
        self,
        agent_id: str,
        message: str,
        call_id: str | None = None,
        customer_variables: dict | None = None,
    ) -> dict:
        body: dict = {"agentId": agent_id, "message": message}
        if call_id:
            body["callId"] = call_id
        if customer_variables:
            body["customerVariables"] = customer_variables
        return self._req("POST", "/chat/message", json=body)

    def chat_end(self, call_id: str) -> Any:
        return self._req("POST", "/chat/end", json={"callId": call_id})

    def get_call(self, call_id: str) -> dict:
        return self._req("GET", f"/call/{call_id}", params=self._ws())

    # --- personas & simulations (Freya-native eval) ------------------------
    def create_personas(self, personas: list[dict]) -> Any:
        body: dict = {"personas": personas}
        if self.workspace_id:
            body["workspaceId"] = self.workspace_id
        return self._req("POST", "/personas", json=body)

    def create_simulation(self, **body) -> Any:
        if self.workspace_id:
            body.setdefault("workspaceId", self.workspace_id)
        return self._req("POST", "/simulations", json=body)

    def get_simulation(self, simulation_id: str) -> Any:
        return self._req("GET", f"/simulations/{simulation_id}", params=self._ws())

    def simulation_iterations(self, simulation_id: str) -> Any:
        return self._req("GET", f"/simulations/{simulation_id}/iterations", params=self._ws())

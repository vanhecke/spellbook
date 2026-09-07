# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: GoCortexIO
"""Knowledge Center client for Agentix Collection sibling documents.

A pack collection is a handle. Indexed documents are a separate tenant object
created through POST /xsoar/agentix/knowledge. Pack-installed agents are
system items, so sources are always shared with all agents.
"""

from __future__ import annotations

import base64
import json
import ssl
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .agentix import KnowledgeDocument
from .tenant import TenantCredentials


class KnowledgeError(Exception):
    """Knowledge Center HTTP, indexing, or binding failure."""


class AgentNotInstalled(KnowledgeError):
    def __init__(self, agent_ids: tuple[str, ...]) -> None:
        self.agent_ids = agent_ids
        listed = ", ".join(agent_ids) or "(none)"
        super().__init__(
            f"agent {listed} is not on this tenant. "
            "Install the pack first: spellbook upload <Pack>"
        )


@dataclass(frozen=True)
class KnowledgeResult:
    source_name: str
    source_id: str
    created: bool
    size_bytes: int | None
    bound_agents: tuple[str, ...]


class KnowledgeCenter:
    """Idempotent create-or-update of File knowledge sources."""

    def __init__(
        self,
        credentials: TenantCredentials,
        *,
        insecure: bool = False,
        ready_timeout_seconds: int = 90,
    ) -> None:
        self._credentials = credentials
        self._insecure = insecure
        self._ready_timeout_seconds = ready_timeout_seconds

    def sync(
        self,
        documents: tuple[KnowledgeDocument, ...],
    ) -> list[KnowledgeResult]:
        if not documents:
            return []
        existing = self._sources_by_name()
        results: list[KnowledgeResult] = []
        for document in documents:
            results.append(self._upsert(document, existing))
        self._verify_bindings(documents, results)
        return results

    def _upsert(
        self,
        document: KnowledgeDocument,
        existing: dict[str, dict[str, Any]],
    ) -> KnowledgeResult:
        payload: dict[str, Any] = {
            "name": document.source_name,
            "sourceType": "File",
            "contentType": document.content_type,
            "file": base64.b64encode(document.path.read_bytes()).decode(),
            "sharedWithAllAgents": True,
        }
        prior = existing.get(document.source_name)
        created = prior is None
        if prior is not None:
            matches = [
                item
                for item in existing.values()
                if item.get("name") == document.source_name
            ]
            if len(matches) > 1:
                raise KnowledgeError(
                    f"multiple knowledge sources named {document.source_name!r}; "
                    "refusing to guess which to update"
                )
            payload["id"] = prior["id"]
            payload["version"] = prior.get("version", 0)

        status, source = self._request("POST", "/xsoar/agentix/knowledge", payload)
        if status == 409 and prior is not None:
            refreshed = self._sources_by_name().get(document.source_name)
            if refreshed is None:
                raise KnowledgeError(
                    f"knowledge source {document.source_name!r} vanished after version conflict"
                )
            payload["id"] = refreshed["id"]
            payload["version"] = refreshed.get("version", 0)
            status, source = self._request("POST", "/xsoar/agentix/knowledge", payload)
        if status != 200:
            raise KnowledgeError(
                f"POST /xsoar/agentix/knowledge failed ({status}): {_err_text(source)}"
            )
        if not isinstance(source, dict) or "id" not in source:
            raise KnowledgeError("knowledge POST returned no source id")
        source_id = str(source["id"])
        ready = self._wait_ready(source_id)
        size = ready.get("contentSizeInBytes") or ready.get("sizeInBytes")
        return KnowledgeResult(
            source_name=document.source_name,
            source_id=source_id,
            created=created,
            size_bytes=int(size) if isinstance(size, int) else None,
            bound_agents=(),
        )

    def _verify_bindings(
        self,
        documents: tuple[KnowledgeDocument, ...],
        results: list[KnowledgeResult],
    ) -> None:
        status, agents = self._request("GET", "/xsoar/agentix/agents")
        if status != 200 or not isinstance(agents, list):
            raise KnowledgeError(
                f"GET /xsoar/agentix/agents failed ({status}): {_err_text(agents)}"
            )
        by_id = {
            item.get("id"): item
            for item in agents
            if isinstance(item, dict) and item.get("id")
        }
        updated: list[KnowledgeResult] = []
        for document, result in zip(documents, results, strict=True):
            if not document.agent_ids:
                updated.append(result)
                continue
            bound: list[str] = []
            missing: list[str] = []
            for agent_id in document.agent_ids:
                agent = by_id.get(agent_id)
                if agent is None:
                    missing.append(agent_id)
                    continue
                user_ids = agent.get("userKnowledgeSourceIds") or []
                system_ids = agent.get("systemKnowledgeSourceIds") or []
                if result.source_id in user_ids or result.source_id in system_ids:
                    bound.append(agent_id)
                else:
                    raise KnowledgeError(
                        f"agent {agent_id} does not list knowledge source "
                        f"{result.source_id} ({result.source_name})"
                    )
            if missing:
                raise AgentNotInstalled(tuple(missing))
            updated.append(
                KnowledgeResult(
                    source_name=result.source_name,
                    source_id=result.source_id,
                    created=result.created,
                    size_bytes=result.size_bytes,
                    bound_agents=tuple(bound),
                )
            )
        results[:] = updated

    def _sources_by_name(self) -> dict[str, dict[str, Any]]:
        status, sources = self._request("GET", "/xsoar/agentix/knowledges")
        if status != 200:
            raise KnowledgeError(
                f"GET /xsoar/agentix/knowledges failed ({status}): {_err_text(sources)}"
            )
        if not isinstance(sources, list):
            raise KnowledgeError("GET /xsoar/agentix/knowledges did not return a list")
        indexed: dict[str, dict[str, Any]] = {}
        for item in sources:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str) and name not in indexed:
                indexed[name] = item
        return indexed

    def _wait_ready(self, source_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self._ready_timeout_seconds
        last: Any = {}
        while time.monotonic() < deadline:
            status, last = self._request(
                "GET", f"/xsoar/agentix/knowledges/{source_id}"
            )
            if status != 200:
                raise KnowledgeError(
                    f"GET knowledge {source_id} failed ({status}): {_err_text(last)}"
                )
            if not isinstance(last, dict):
                raise KnowledgeError(f"knowledge {source_id} response was not an object")
            processing = last.get("processingStatus")
            if processing == "ready":
                return last
            if processing == "error":
                raise KnowledgeError(
                    f"knowledge source {source_id} indexed with error: {_err_text(last)}"
                )
            time.sleep(2)
        raise KnowledgeError(
            f"knowledge source {source_id} still "
            f"{last.get('processingStatus')!r} after {self._ready_timeout_seconds}s"
        )

    def _request(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
    ) -> tuple[int, Any]:
        data = None if body is None else json.dumps(dict(body)).encode()
        headers = {
            "Authorization": self._credentials.api_key,
            "x-xdr-auth-id": self._credentials.auth_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        request = Request(
            self._credentials.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        context = ssl.create_default_context()
        if self._insecure:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        try:
            with urlopen(request, context=context, timeout=30) as response:
                raw = response.read().decode() or "null"
                return response.status, json.loads(raw)
        except HTTPError as exc:
            raw = exc.read().decode()
            try:
                parsed: Any = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw[:400]
            return exc.code, parsed
        except URLError as exc:
            raise KnowledgeError(f"request failed: {exc}") from exc


def _err_text(payload: Any) -> str:
    if isinstance(payload, dict):
        return str(
            payload.get("error")
            or payload.get("detail")
            or payload.get("title")
            or payload
        )[:400]
    return str(payload)[:400]

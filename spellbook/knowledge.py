# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: GoCortexIO
"""
Knowledge Module

Uploads the Knowledge Center documents for a pack's Agentix agents.

demisto-sdk has no content type for a knowledge source, so a document cannot
travel inside the pack. It lives in Knowledge/<Pack>/ at the instance root
instead, and follows the pack to the tenant through the Knowledge Center API,
shared with every agent the pack carries. The API authenticates with the same
DEMISTO_* and XSIAM_AUTH_ID variables as the pack upload.
"""

import time
from pathlib import Path

import click
import demisto_client
from demisto_client.demisto_api.rest import ApiException


# The file types the Knowledge Center upload dialog accepts. The server
# expects the content type in lowercase.
KNOWLEDGE_CONTENT_TYPES = {
    ".md": "text/markdown",
    ".json": "application/json",
    ".jsonl": "application/jsonl",
    ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# The create call answers 200 even when indexing then fails, so the source's
# processingStatus is the only failure signal. It settles within seconds.
POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 60


def knowledge_dir(packs_dir: Path, pack_name: str) -> Path:
    """Return the folder holding a pack's Knowledge Center documents."""
    return packs_dir.parent / "Knowledge" / pack_name


def upload_knowledge(pack_path: Path, knowledge_path: Path, insecure: bool) -> bool:
    """Upload each document as a knowledge source for the pack's agents.

    Packs without documents pass immediately. check_knowledge has already
    vetted the documents in upload's pre-flight. A source's content cannot be
    edited, so a document already on the tenant under the same name, and
    shared with one of the pack's agents, is deleted and created again.
    Documents removed from the folder stay on the tenant.

    Args:
        pack_path: Path to the pack directory.
        knowledge_path: Path to the pack's knowledge folder.
        insecure: Skip certificate validation, as for the pack upload.

    Returns:
        True if every document is ready on the tenant, False otherwise.
    """
    # Hidden files, such as the .DS_Store Finder leaves behind, are not documents.
    documents = sorted(knowledge_path.glob("[!.]*"))
    if not documents:
        return True

    # demisto-sdk requires an agent's file stem to match its id.
    agent_ids = sorted(path.stem for path in pack_path.glob("AgentixAgents/*/*.yml"))
    client = demisto_client.configure(verify_ssl=not insecure)

    try:
        existing, _, _ = demisto_client.generic_request_func(
            client, "/cm/agentix/knowledges", "GET", response_type="object"
        )
        for path in documents:
            # The API omits userAgentIds from a source shared with no agent.
            stale = [
                source["id"]
                for source in existing
                if source["name"] == path.name
                and set(agent_ids) & set(source.get("userAgentIds", []))
            ]
            if stale:
                click.echo(f"[INFO] Replacing knowledge: {path.name}")
            for source_id in stale:
                demisto_client.generic_request_func(
                    client, f"/cm/agentix/knowledges/{source_id}", "DELETE"
                )

            body = {
                "sourceType": "FILE",
                "name": path.name,
                "contentType": KNOWLEDGE_CONTENT_TYPES[path.suffix],
                "sharedWithAllAgents": False,
                "userAgentIds": agent_ids,
                "systemAgentIds": [],
                "periodicSync": False,
                "sourceDetails": {"datasource": None, "instanceName": None, "args": {}},
                "file": list(path.read_bytes()),
            }
            created, _, _ = demisto_client.generic_request_func(
                client,
                "/cm/agentix/knowledge",
                "POST",
                body=body,
                response_type="object",
            )

            status = "processing"
            for _ in range(POLL_TIMEOUT_SECONDS // POLL_INTERVAL_SECONDS):
                time.sleep(POLL_INTERVAL_SECONDS)
                source, _, _ = demisto_client.generic_request_func(
                    client,
                    f"/cm/agentix/knowledges/{created['id']}",
                    "GET",
                    response_type="object",
                )
                status = source["processingStatus"]
                if status != "processing":
                    break

            if status != "ready":
                click.echo(
                    f"[FAIL] Knowledge: {path.name} (processing status: {status})"
                )
                return False
            click.echo(f"[OK] Knowledge: {path.name} ({path.stat().st_size} bytes)")
    except ApiException as e:
        click.echo(f"[FAIL] Knowledge upload failed: {e.status} {e.reason}")
        return False

    return True

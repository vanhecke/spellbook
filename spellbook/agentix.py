# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: GoCortexIO
"""Agentix deploy policy for Spellbook.

Spellbook does not parse Agentix YAML schemas. demisto-sdk owns those.
This module answers whether a pack carries Agentix source directories, which
marketplace the dump must target, which validation profile apply, and which
Collection sibling documents must go through the Knowledge Center API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Mapping, assert_never

import yaml

# demisto-sdk declares this upload flag with an underscore, not a hyphen
# (see demisto_sdk/commands/upload/upload_setup.py). Passing the hyphenated
# form is rejected as an unknown option.
SDK_UPLOAD_SKIP_VALIDATION_FLAG = "--skip_validation"

AGENTIX_SOURCE_DIRS: tuple[str, ...] = (
    "AgentixAgents",
    "AgentixActions",
    "AgentixSkills",
    "Collections",
)

KNOWLEDGE_SUFFIX_TO_MIME: Mapping[str, str] = {
    ".md": "text/markdown",
    ".json": "application/json",
    ".csv": "text/csv",
    ".jsonl": "application/jsonl",
}

BUNDLED_VALIDATION_CONFIG = (
    Path(__file__).parent / "assets" / "agentix_validation_config.toml"
)


class AgentixKind(StrEnum):
    """SDK pack-folder names for Agentix content.

    The enum value is the directory name demisto-sdk uses. This is the only
    place Spellbook writes those strings down.
    """

    AGENT = "AgentixAgents"
    ACTION = "AgentixActions"
    SKILL = "AgentixSkills"
    COLLECTION = "Collections"

    def release_note_header(self) -> str:
        if self is AgentixKind.AGENT:
            return "Agents"
        if self is AgentixKind.ACTION:
            return "Actions"
        if self is AgentixKind.SKILL:
            return "Skills"
        if self is AgentixKind.COLLECTION:
            return "Collections"
        assert_never(self)


class MarketplaceConflict(Exception):
    """The requested marketplace would silently drop Agentix items."""

    def __init__(self, requested: str, dropped: tuple[str, ...]) -> None:
        self.requested = requested
        self.dropped = dropped
        listed = ", ".join(dropped[:10])
        extra = "" if len(dropped) <= 10 else f" (and {len(dropped) - 10} more)"
        super().__init__(
            f"Agentix content is platform-only; {requested} would drop: "
            f"{listed}{extra}"
        )


@dataclass(frozen=True)
class KnowledgeDocument:
    """A Collection sibling file that is not pack content.

    The SDK dump drops these. They reach the tenant only through
    POST /xsoar/agentix/knowledge. Sharing is always all-agents: pack-installed
    agents are system items and reject per-agent share.
    """

    path: Path
    source_name: str
    content_type: str
    collection_id: str
    agent_ids: tuple[str, ...]


@dataclass(frozen=True)
class AgentixPack:
    """Filesystem handle to a pack that may contain Agentix source.

    `detected` is true when at least one nested `<id>/<id>.yml` exists under
    an SDK Agentix folder. Empty scaffold directories do not count.
    """

    path: Path
    items: tuple[str, ...]
    agent_ids: tuple[str, ...]
    documents: tuple[KnowledgeDocument, ...]
    declares_platform: bool

    @property
    def detected(self) -> bool:
        return bool(self.items)

    def summary(self) -> str:
        agents = sum(1 for item in self.items if item.startswith("AgentixAgents/"))
        actions = sum(1 for item in self.items if item.startswith("AgentixActions/"))
        skills = sum(1 for item in self.items if item.startswith("AgentixSkills/"))
        collections = sum(1 for item in self.items if item.startswith("Collections/"))
        return (
            f"{agents} agent, {actions} actions, {skills} skill, "
            f"{collections} collection"
        )

    @classmethod
    def probe(cls, pack_dir: Path) -> AgentixPack:
        pack_dir = pack_dir.resolve()
        items: list[str] = []
        agent_ids: list[str] = []
        collection_ids: list[str] = []
        collection_names: dict[str, str] = {}

        for kind in AgentixKind:
            kind_dir = pack_dir / kind.value
            if not kind_dir.is_dir():
                continue
            for entry in sorted(kind_dir.iterdir()):
                yaml_path = entry / f"{entry.name}.yml"
                if not entry.is_dir() or not yaml_path.is_file():
                    continue
                items.append(f"{kind.value}/{entry.name}")
                if kind is AgentixKind.AGENT:
                    agent_ids.append(entry.name)
                elif kind is AgentixKind.ACTION:
                    pass
                elif kind is AgentixKind.SKILL:
                    pass
                elif kind is AgentixKind.COLLECTION:
                    collection_ids.append(entry.name)
                    collection_names[entry.name] = _collection_source_name(
                        yaml_path, entry.name
                    )
                else:
                    assert_never(kind)

        documents = _discover_knowledge(
            pack_dir,
            collection_ids,
            collection_names,
            tuple(agent_ids),
        )
        return cls(
            path=pack_dir,
            items=tuple(items),
            agent_ids=tuple(agent_ids),
            documents=tuple(documents),
            declares_platform=_pack_declares_platform(pack_dir),
        )


@dataclass(frozen=True)
class UploadPlan:
    pack_path: Path
    marketplace: str
    override_existing: bool
    validation_config: Path | None
    documents: tuple[KnowledgeDocument, ...]
    sdk_argv: tuple[str, ...]
    summary: str

    def render(self) -> str:
        lines = [
            f"Agentix content: {self.summary}",
            f"  Marketplace .......... {self.marketplace} (forced: pack carries Agentix content)",
            "  Installed copy ....... replaced (--override-existing)",
        ]
        if self.validation_config is not None:
            lines.append(
                f"  Validation config .... {self.validation_config.name}"
            )
        lines.append(
            f"  Knowledge documents .. {len(self.documents)} "
            "(not pack content; pushed after install)"
        )
        for document in self.documents:
            lines.append(
                f'[OK] {document.path.name} will be pushed as knowledge source '
                f'"{document.source_name}"'
            )
        return "\n".join(lines)


def bundled_validation_config() -> Path:
    return BUNDLED_VALIDATION_CONFIG


def plan_upload(
    pack: AgentixPack,
    *,
    xsiam: bool,
    insecure: bool,
    skip_validation: bool,
) -> UploadPlan:
    if not pack.detected:
        raise ValueError("plan_upload requires a pack with Agentix content")
    if xsiam:
        raise MarketplaceConflict("marketplacev2/--xsiam", pack.items)
    argv = sdk_upload_argv(
        pack.path,
        insecure=insecure,
        skip_validation=skip_validation,
    )
    return UploadPlan(
        pack_path=pack.path,
        marketplace="platform",
        override_existing=True,
        validation_config=bundled_validation_config() if pack.detected else None,
        documents=pack.documents,
        sdk_argv=tuple(argv),
        summary=pack.summary(),
    )


def sdk_upload_argv(
    pack_dir: Path,
    *,
    insecure: bool,
    skip_validation: bool,
) -> list[str]:
    argv = [
        "demisto-sdk",
        "upload",
        "-i",
        str(pack_dir),
        "-z",
        "--marketplace",
        "platform",
        "--override-existing",
    ]
    if insecure:
        argv.append("--insecure")
    if skip_validation:
        argv.append(SDK_UPLOAD_SKIP_VALIDATION_FLAG)
    return argv


def release_note_headers(pack: AgentixPack) -> tuple[str, ...]:
    if not pack.detected:
        return ()
    present = {item.split("/", 1)[0] for item in pack.items}
    headers: list[str] = []
    for kind in AgentixKind:
        if kind.value in present:
            headers.append(kind.release_note_header())
    return tuple(headers)


def _pack_declares_platform(pack_dir: Path) -> bool:
    metadata_path = pack_dir / "pack_metadata.json"
    if not metadata_path.is_file():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig") or "{}")
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False
    raw = metadata.get("marketplaces")
    if not isinstance(raw, list):
        return False
    return "platform" in [str(item) for item in raw]


def _collection_source_name(yaml_path: Path, fallback: str) -> str:
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return fallback
    if not isinstance(data, dict):
        return fallback
    name = data.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return fallback


def _discover_knowledge(
    pack_dir: Path,
    collection_ids: list[str],
    collection_names: dict[str, str],
    agent_ids: tuple[str, ...],
) -> list[KnowledgeDocument]:
    documents: list[KnowledgeDocument] = []
    collections_dir = pack_dir / AgentixKind.COLLECTION.value
    for collection_id in collection_ids:
        item_dir = collections_dir / collection_id
        if not item_dir.is_dir():
            continue
        for path in sorted(item_dir.iterdir()):
            mime = KNOWLEDGE_SUFFIX_TO_MIME.get(path.suffix.lower())
            if not path.is_file() or mime is None:
                continue
            documents.append(
                KnowledgeDocument(
                    path=path,
                    source_name=collection_names.get(collection_id, collection_id),
                    content_type=mime,
                    collection_id=collection_id,
                    agent_ids=agent_ids,
                )
            )
    return documents

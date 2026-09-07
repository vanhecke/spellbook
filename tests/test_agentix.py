# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: GoCortexIO

from pathlib import Path

import pytest

from spellbook.agentix import (
    AgentixKind,
    AgentixPack,
    MarketplaceConflict,
    bundled_validation_config,
    plan_upload,
    release_note_headers,
    sdk_upload_argv,
)
from spellbook.instance import InstanceManager
from spellbook.pack_template import PackTemplate
from spellbook.tenant import MissingCredentials, TenantCredentials

FIXTURE_PACK = Path(__file__).parent / "fixtures" / "agentix_pack"
FIREWALL_PACK = Path(
    "/home/joris/Projects/cortex_agent_builder/Cortex-FirewallAlertAnalyst"
    "/Packs/FirewallAlertAnalyst"
)


def test_probe_fixture_inventory() -> None:
    pack = AgentixPack.probe(FIXTURE_PACK)
    assert pack.detected
    assert pack.declares_platform
    assert pack.agent_ids == ("demo-agent",)
    assert "AgentixAgents/demo-agent" in pack.items
    assert "AgentixActions/DemoAction" in pack.items
    assert "AgentixSkills/demo-skill" in pack.items
    assert "Collections/DemoCollection" in pack.items
    assert len(pack.documents) == 1
    document = pack.documents[0]
    assert document.source_name == "Demo Worked Alerts"
    assert document.content_type == "text/markdown"
    assert document.path.name == "notes.md"
    assert document.agent_ids == ("demo-agent",)


def test_empty_scaffold_dir_is_not_agentix(tmp_path: Path) -> None:
    pack_dir = tmp_path / "EmptyPack"
    (pack_dir / "AgentixAgents").mkdir(parents=True)
    (pack_dir / "pack_metadata.json").write_text(
        '{"name": "EmptyPack", "marketplaces": ["platform"]}',
        encoding="utf-8",
    )
    pack = AgentixPack.probe(pack_dir)
    assert not pack.detected
    assert pack.documents == ()


def test_xsiam_plan_is_a_hard_conflict() -> None:
    pack = AgentixPack.probe(FIXTURE_PACK)
    with pytest.raises(MarketplaceConflict) as caught:
        plan_upload(
            pack,
            xsiam=True,
            insecure=False,
            skip_validation=False,
        )
    assert "DemoAction" in ",".join(caught.value.dropped)


def test_upload_plan_forces_platform_and_override() -> None:
    pack = AgentixPack.probe(FIXTURE_PACK)
    plan = plan_upload(
        pack,
        xsiam=False,
        insecure=False,
        skip_validation=False,
    )
    assert plan.marketplace == "platform"
    assert plan.override_existing is True
    assert plan.sdk_argv[:3] == ("demisto-sdk", "upload", "-i")
    assert "--marketplace" in plan.sdk_argv
    assert "platform" in plan.sdk_argv
    assert "--override-existing" in plan.sdk_argv
    assert "-z" in plan.sdk_argv
    assert len(plan.documents) == 1


def test_sdk_argv_skip_validation_uses_underscore_flag() -> None:
    argv = sdk_upload_argv(FIXTURE_PACK, insecure=True, skip_validation=True)
    assert "--skip_validation" in argv
    assert "--insecure" in argv
    assert "--skip-validation" not in argv


def test_bundled_validation_config_omits_ag100_and_ag118() -> None:
    path = bundled_validation_config()
    assert path.is_file()
    selected = [
        line.strip().strip(",").strip('"')
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith('"AG')
    ]
    assert "AG101" in selected
    assert "AG100" not in selected
    assert "AG118" not in selected
    assert "DO104" in path.read_text(encoding="utf-8")


def test_release_note_headers_follow_present_kinds() -> None:
    pack = AgentixPack.probe(FIXTURE_PACK)
    headers = release_note_headers(pack)
    assert headers == (
        AgentixKind.AGENT.release_note_header(),
        AgentixKind.ACTION.release_note_header(),
        AgentixKind.SKILL.release_note_header(),
        AgentixKind.COLLECTION.release_note_header(),
    )


def test_tenant_credentials_from_env_and_aliases() -> None:
    creds = TenantCredentials.from_env(
        {
            "TENANT_BASE_URL": "https://api.example.com/",
            "TENANT_API_KEY": "secret",
            "TENANT_API_ID": "17",
        }
    )
    assert creds.base_url == "https://api.example.com"
    assert creds.api_key == "secret"
    assert creds.auth_id == "17"
    assert "secret" not in repr(creds)


def test_tenant_credentials_report_every_missing_variable() -> None:
    with pytest.raises(MissingCredentials) as caught:
        TenantCredentials.from_env({})
    assert caught.value.missing == (
        "DEMISTO_BASE_URL",
        "DEMISTO_API_KEY",
        "XSIAM_AUTH_ID",
    )


@pytest.mark.skipif(not FIREWALL_PACK.is_dir(), reason="Firewall Analyst pack not checked out")
def test_probe_firewall_analyst_inventory() -> None:
    pack = AgentixPack.probe(FIREWALL_PACK)
    assert pack.detected
    assert pack.declares_platform
    assert pack.agent_ids == ("firewall-alert-analyst-agent",)
    assert len([item for item in pack.items if item.startswith("AgentixActions/")]) == 7
    assert "AgentixSkills/firewall-alert-triage-skill" in pack.items
    assert "Collections/FirewallTriageWorkedAlertsCollection" in pack.items
    assert len(pack.documents) == 1
    document = pack.documents[0]
    assert document.source_name == "Firewall Triage Worked Alerts"
    assert document.path.name == "FirewallTriageWorkedAlerts.md"
    assert document.content_type == "text/markdown"


def test_init_sample_pack_includes_agentix(tmp_path: Path) -> None:
    instance = InstanceManager(base_path=str(tmp_path)).create_instance(
        "demo",
        author="Test Author",
        include_ci=False,
    )
    pack_dir = instance / "Packs" / "SamplePack"
    pack = AgentixPack.probe(pack_dir)
    assert pack.detected
    assert pack.declares_platform
    assert pack.agent_ids == ("sample-analyst-agent",)
    assert "AgentixActions/SampleScoreAction" in pack.items
    assert "AgentixSkills/sample-analyst-skill" in pack.items
    assert "Collections/SampleWorkedAlertsCollection" in pack.items
    assert len(pack.documents) == 1
    assert pack.documents[0].source_name == "Sample Worked Alerts"
    assert (
        pack_dir
        / "AgentixAgents"
        / "sample-analyst-agent"
        / "sample-analyst-agent_systeminstructions.md"
    ).is_file()
    assert (pack_dir / "Scripts" / "SampleScoreScript" / "SampleScoreScript.py").is_file()
    assert not (pack_dir / "Scripts" / ".gitkeep").exists()


def test_create_pack_does_not_scaffold_agentix_dirs(tmp_path: Path) -> None:
    packs = tmp_path / "Packs"
    packs.mkdir()
    template = PackTemplate.__new__(PackTemplate)
    template.config = {}
    template.packs_dir = packs
    template.defaults = {
        "support": "community",
        "author": "Test",
        "url": "",
        "email": "",
        "categories": [],
        "tags": [],
        "useCases": [],
        "keywords": [],
        "marketplaces": ["xsoar", "marketplacev2", "platform"],
    }
    pack_path = template.create_pack("OtherPack", "not a sample")
    assert not (pack_path / "AgentixAgents").exists()
    assert not (pack_path / "AgentixActions").exists()
    assert not (pack_path / "AgentixSkills").exists()
    assert not AgentixPack.probe(pack_path).detected

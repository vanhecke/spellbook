# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: GoCortexIO
"""
Pack Template Module

Creates new content pack scaffolding from templates.
"""

import json
import os
import shutil
import uuid
from pathlib import Path

import click
import yaml


# The author image is bundled inside the package so it ships in both the
# container (COPY spellbook/) and the wheel. demisto-sdk auto-detects an
# author image at the pack root named Author_image.png.
AUTHOR_IMAGE_FILENAME = "Author_image.png"
AUTHOR_IMAGE_SOURCE = Path(__file__).parent / "assets" / AUTHOR_IMAGE_FILENAME


class PackTemplate:
    """Creates new pack structures from templates."""

    CONTENT_DIRECTORIES = [
        "Integrations",
        "Scripts",
        "Playbooks",
        "IncidentTypes",
        "IncidentFields",
        "Layouts",
        "Classifiers",
        "CorrelationRules",
        "ParsingRules",
        "ModelingRules",
        "XSIAMDashboards",
        "XSIAMReports",
        "Triggers",
        "Jobs",
        "XDRCTemplates",
        "ReleaseNotes",
    ]

    XSIAM_DIRECTORIES = [
        "CorrelationRules",
        "ParsingRules",
        "ModelingRules",
        "XSIAMDashboards",
        "XSIAMReports",
        "Triggers",
        "Jobs",
        "XDRCTemplates",
    ]

    def __init__(self, config_path: str = "spellbook.yaml"):
        """
        Initialise the pack template generator.

        Args:
            config_path: Path to the spellbook configuration file.
        """
        self.config = self._load_config(config_path)
        self._repo_root = Path(config_path).resolve().parent
        raw_packs_dir = self.config.get("packs_directory", "Packs")
        resolved_packs = (self._repo_root / raw_packs_dir).resolve()
        try:
            resolved_packs.relative_to(self._repo_root)
        except ValueError:
            raise ValueError(
                f"packs_directory '{raw_packs_dir}' resolves outside the content repository"
            )
        self.packs_dir = resolved_packs
        self.defaults = self.config.get("defaults", {})

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        path = Path(config_path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def create_pack(
        self,
        pack_name: str,
        description: str = "",
        author: str | None = None,
        categories: list[str] | None = None,
        create_directories: list[str] | None = None,
        include_author_image: bool = True
    ) -> Path:
        """
        Create a new pack with standard structure.

        Args:
            pack_name: Name of the pack (no spaces).
            description: Short description of the pack.
            author: Author name (uses default if not provided).
            categories: List of categories.
            create_directories: Specific directories to create.
            include_author_image: Scaffold the bundled author image at the
                pack root.

        Returns:
            Path to the created pack directory.
        """
        pack_path = (self.packs_dir / pack_name).resolve()
        try:
            pack_path.relative_to(self.packs_dir)
        except ValueError:
            raise ValueError(
                f"pack_name '{pack_name}' resolves outside the packs directory"
            )
        pack_path.mkdir(parents=True, exist_ok=True)

        self._create_metadata(
            pack_path,
            pack_name,
            description,
            author,
            categories
        )

        self._create_readme(pack_path, pack_name, description)

        self._create_pack_ignore(pack_path)

        self._create_secrets_ignore(pack_path)

        self._create_contributors(pack_path, author)

        if include_author_image:
            self._create_author_image(pack_path)

        directories = create_directories or self.CONTENT_DIRECTORIES
        for directory in directories:
            dir_path = pack_path / directory
            dir_path.mkdir(exist_ok=True)
            gitkeep = dir_path / ".gitkeep"
            gitkeep.touch()

        click.echo(f"Created pack: {pack_path}")
        return pack_path

    def _create_author_image(self, pack_path: Path) -> None:
        """Copy the bundled author image to the pack root as Author_image.png.

        Skips silently if the bundled asset is missing, and does not overwrite
        an existing author image.
        """
        if not AUTHOR_IMAGE_SOURCE.exists():
            return
        target = pack_path / AUTHOR_IMAGE_FILENAME
        if target.exists():
            return
        shutil.copyfile(AUTHOR_IMAGE_SOURCE, target)

    def _create_metadata(
        self,
        pack_path: Path,
        pack_name: str,
        description: str,
        author: str | None,
        categories: list[str] | None
    ) -> None:
        """Create pack_metadata.json file."""
        metadata = {
            "name": pack_name,
            "description": description or f"{pack_name} content pack",
            "support": self.defaults.get("support", "community"),
            "currentVersion": "1.0.0",
            "author": author or self.defaults.get("author", ""),
            "url": self.defaults.get("url", ""),
            "email": self.defaults.get("email", ""),
            "categories": categories or self.defaults.get("categories", []),
            "tags": self.defaults.get("tags", []),
            "useCases": self.defaults.get("useCases", []),
            "keywords": self.defaults.get("keywords", []),
            "marketplaces": self.defaults.get(
                "marketplaces",
                ["xsoar", "marketplacev2", "platform"]
            ),
            "githubUser": []
        }

        metadata_path = pack_path / "pack_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
            f.write("\n")

    def _create_readme(
        self,
        pack_path: Path,
        pack_name: str,
        description: str
    ) -> None:
        """Create README.md file."""
        readme_content = f"""# {pack_name}

{description or 'Content pack for Cortex Platform.'}

## Overview

This pack contains content for use with Cortex Platform.

## Content Items

### Parsing Rules

Rules for parsing raw log data into structured fields.

### Modelling Rules

Rules for mapping parsed data to the XDM (Cross Data Model) schema.

### Correlation Rules

Detection rules that identify security events and generate alerts.

### XSIAM Dashboards

Visual dashboards for monitoring and analysis.

### XSIAM Reports

Report templates for scheduled reporting.

### Integrations

(List integrations here)

### Scripts

(List scripts here)

### Playbooks

(List playbooks here)

### Triggers

Automation triggers for event-driven workflows.

### Jobs

Scheduled jobs for recurring tasks.

## Installation

Upload the pack zip file to your Cortex Platform instance.

## Requirements

- Cortex Platform version 6.0 or later

## Support

For support, please refer to the pack metadata for contact information.

## Version History (Managed by GoCortex Spellbook)

<!-- spellbook:version-history:start -->
### 1.0.0

- Initial release.

<!-- spellbook:version-history:end -->
"""
        readme_path = pack_path / "README.md"
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)

    def _create_contributors(self, pack_path: Path, author: str | None) -> None:
        """Write CONTRIBUTORS.json, seeded with the pack author.

        demisto-sdk reads this file as a flat list of contributor names and
        renders them into the pack README, so the format is an array of
        strings and nothing else. Validation requires it, so scaffolding it
        keeps a freshly created pack passing; edit it to add reviewers and
        maintainers.
        """
        name = (author or self.defaults.get("author", "")).strip()
        if not name:
            # Writing [] would produce a pack that fails our own validation
            # the moment it is created. Say so here, and leave the file out
            # so validate reports the missing-file case, whose message
            # carries the example to copy.
            click.echo(
                "[WARN] no author configured, so no CONTRIBUTORS.json was "
                "written - pass --author, or set defaults.author in "
                "spellbook.yaml, or add the file by hand"
            )
            return

        path = pack_path / "CONTRIBUTORS.json"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump([name], handle, indent=4)
            handle.write("\n")

    def _create_pack_ignore(self, pack_path: Path) -> None:
        """Create .pack-ignore file."""
        content = """# Pack ignore file
# Use this file to ignore specific linter errors or tests

# Ignore a specific test
# [file:playbook-Test.yml]
# ignore=auto-test

# Ignore linter errors
# [file:integration.yml]
# ignore=IN126,PA116

# Require network for tests
# [tests_require_network]
# integration-id
"""
        ignore_path = pack_path / ".pack-ignore"
        with open(ignore_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _create_secrets_ignore(self, pack_path: Path) -> None:
        """Create .secrets-ignore file."""
        content = """# Secrets ignore file
# Add words that should be allowed in secret scanning

# Example allowed words:
# example_api_key
# test_token
"""
        secrets_path = pack_path / ".secrets-ignore"
        with open(secrets_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _create_correlation_rule(self, pack_path: Path, pack_name: str) -> None:
        """Create sample correlation rule for Cortex Platform.
        
        Follows the demisto-sdk correlationrule.yml schema with all required
        fields. Based on working examples from demisto/content repository.
        """
        rules_dir = pack_path / "CorrelationRules"
        rules_dir.mkdir(exist_ok=True)

        rule_name = f"{pack_name} - Multiple Failed Login Attempts"
        vendor = pack_name.lower()
        dataset = f"{vendor}_raw"
        global_id = str(uuid.uuid4())

        rule_yml = f"""alert_category: CREDENTIAL_ACCESS
alert_description: Multiple failed login attempts detected from $xdm.source.ipv4 targeting $xdm.target.user.username which may indicate a brute force attack.
alert_fields:
  actor_effective_username: xdm.source.user.username
  agent_hostname: xdm.source.host.hostname
alert_name: {pack_name} - Brute Force Attack Detected
dataset: alerts
description: Detects multiple failed authentication attempts from a single source within a short time window indicating a potential brute force attack.
drilldown_query_timeframe: ALERT
execution_mode: REAL_TIME
fromversion: 8.4.0
global_rule_id: {global_id}
investigation_query_link: dataset = {dataset} | filter user = $xdm.target.user.username
mapping_strategy: CUSTOM
mitre_defs:
  TA0006 - Credential Access:
  - T1110 - Brute Force
name: {rule_name}
severity: SEV_030_MEDIUM
suppression_duration: 1 hours
suppression_enabled: true
suppression_fields: xdm.source.ipv4|xdm.target.user.username
xql_query: |
  datamodel dataset = {dataset}
  | filter xdm.event.type = "AUTHENTICATION" and xdm.event.outcome = "FAILED"
  | fields xdm.event.type, xdm.event.outcome, xdm.source.ipv4, xdm.source.host.hostname, xdm.target.user.username, xdm.source.user.username
"""

        rule_filename = rule_name.replace(" ", "_").replace("-", "_")
        rule_path = rules_dir / f"{rule_filename}.yml"
        with open(rule_path, "w", encoding="utf-8") as f:
            f.write(rule_yml)

        self._create_scheduled_correlation_rule(rules_dir, pack_name, dataset)

    def _create_scheduled_correlation_rule(self, rules_dir: Path, pack_name: str, dataset: str) -> None:
        """Create sample scheduled correlation rule for Cortex Platform.
        
        Demonstrates how to configure a CRON-based scheduled correlation rule
        instead of real-time execution. Requires crontab, execution_mode, and
        search_window fields.
        """
        rule_name = f"{pack_name} - Multiple Failed Login Attempts-Scheduled"
        global_id = str(uuid.uuid4())

        rule_yml = f"""alert_category: CREDENTIAL_ACCESS
alert_description: Multiple failed login attempts detected from $xdm.source.ipv4 targeting $xdm.target.user.username which may indicate a brute force attack.
alert_fields:
  actor_effective_username: xdm.source.user.username
  agent_hostname: xdm.source.host.hostname
alert_name: {pack_name} - Brute Force Attack Detected-Scheduled
crontab: '*/10 * * * *'
dataset: alerts
description: Detects multiple failed authentication attempts from a single source using scheduled execution. Runs every 10 minutes with a 15 minute search window.
drilldown_query_timeframe: ALERT
execution_mode: SCHEDULED
fromversion: 8.4.0
global_rule_id: {global_id}
investigation_query_link: dataset = {dataset} | filter user = $xdm.target.user.username
mapping_strategy: CUSTOM
mitre_defs:
  TA0006 - Credential Access:
  - T1110 - Brute Force
name: {rule_name}
search_window: 15 minutes
severity: SEV_030_MEDIUM
suppression_duration: 1 hours
suppression_enabled: true
suppression_fields: xdm.source.ipv4|xdm.target.user.username
xql_query: |
  datamodel dataset = {dataset}
  | filter xdm.event.type = "AUTHENTICATION" and xdm.event.outcome = "FAILED"
  | fields xdm.event.type, xdm.event.outcome, xdm.source.ipv4, xdm.source.host.hostname, xdm.target.user.username, xdm.source.user.username
"""

        rule_filename = rule_name.replace(" ", "_").replace("-", "_")
        rule_path = rules_dir / f"{rule_filename}.yml"
        with open(rule_path, "w", encoding="utf-8") as f:
            f.write(rule_yml)

    def _create_parsing_rule(self, pack_path: Path, pack_name: str) -> None:
        """Create sample parsing rule for Cortex Platform.
        
        Follows the demisto-sdk parsingrule.yml schema. The rules and samples
        fields are empty strings as the SDK unifies them automatically.
        Based on working examples from demisto/content repository.
        """
        rules_dir = pack_path / "ParsingRules" / f"{pack_name}ParsingRules"
        rules_dir.mkdir(parents=True, exist_ok=True)

        # Validator PR101 requires the id to end with 'ParsingRule' and the
        # name to end with 'Parsing Rule'.
        rule_id = f"{pack_name}ParsingRule"
        rule_file_base = f"{pack_name}ParsingRules"
        vendor = pack_name.lower()
        dataset = f"{vendor}_raw"

        rule_yml = f"""id: {rule_id}
name: {pack_name} Parsing Rule
fromversion: 6.10.0
tags: []
rules: ''
samples: ''
"""

        xif_content = f"""[INGEST:vendor="{pack_name}", product="{pack_name}", target_dataset="{dataset}", no_hit=keep]
filter _raw_log ~= "\\d{{4}}-\\d{{2}}-\\d{{2}}T\\d{{2}}:\\d{{2}}:\\d{{2}}"
| alter
    tmp_timestamp = arrayindex(regextract(_raw_log, "(\\d{{4}}-\\d{{2}}-\\d{{2}}T\\d{{2}}:\\d{{2}}:\\d{{2}}[Z\\d\\.]*)"), 0),
    hostname = arrayindex(regextract(_raw_log, "\\d{{4}}-\\d{{2}}-\\d{{2}}T\\d{{2}}:\\d{{2}}:\\d{{2}}[Z\\d\\.]*\\s+(\\S+)"), 0),
    process_name = arrayindex(regextract(_raw_log, "\\d{{4}}-\\d{{2}}-\\d{{2}}T\\d{{2}}:\\d{{2}}:\\d{{2}}[Z\\d\\.]*\\s+\\S+\\s+(\\w+)"), 0),
    message = arrayindex(regextract(_raw_log, "\\d{{4}}-\\d{{2}}-\\d{{2}}T\\d{{2}}:\\d{{2}}:\\d{{2}}[Z\\d\\.]*\\s+\\S+\\s+\\w+[:\\s]+(.*)$"), 0)
| alter
    _time = if(tmp_timestamp ~= "\\.", parse_timestamp("%Y-%m-%dT%H:%M:%E3SZ", tmp_timestamp), parse_timestamp("%Y-%m-%dT%H:%M:%SZ", tmp_timestamp))
| fields -tmp_timestamp;
"""

        with open(rules_dir / f"{rule_file_base}.yml", "w", encoding="utf-8") as f:
            f.write(rule_yml)

        with open(rules_dir / f"{rule_file_base}.xif", "w", encoding="utf-8") as f:
            f.write(xif_content)

    def _create_modeling_rule(self, pack_path: Path, pack_name: str) -> None:
        """Create sample modelling rule for Cortex Platform.
        
        Follows the demisto-sdk modelingrule.yml schema. The rules and schema
        fields are empty strings as the SDK unifies them automatically.
        Based on working VMwareESXi example from demisto/content repository.
        """
        rules_dir = pack_path / "ModelingRules" / f"{pack_name}ModelingRules"
        rules_dir.mkdir(parents=True, exist_ok=True)

        rule_file_base = f"{pack_name}ModelingRules"
        vendor = pack_name.lower()
        dataset = f"{vendor}_raw"

        # Validator MR108 requires the id to end with 'ModelingRule' and the
        # name to end with 'Modeling Rule'.
        rule_yml = f"""fromversion: 6.10.0
id: {pack_name}ModelingRule
name: {pack_name} Modeling Rule
rules: ''
schema: ''
tags: {pack_name}
"""

        # Two conventions in the XQL below, both taken from official
        # demisto/content modelling rules: the MODEL header leaves the dataset
        # unquoted, and xdm.source.port is integer-typed so it takes
        # to_integer() rather than to_number(), which yields a float.
        xif_content = f"""[MODEL: dataset={dataset}]
alter
    event_type = arrayindex(regextract(_raw_log, "\\d{{4}}-\\d{{2}}-\\d{{2}}T\\d{{2}}:\\d{{2}}:\\d{{2}}[Z\\d\\.]*\\s+\\S+\\s+(\\w+)"), 0),
    username = arrayindex(regextract(_raw_log, "user[=:\\s]+(\\S+)"), 0),
    source_ip = arrayindex(regextract(_raw_log, "from\\s+(\\d+\\.\\d+\\.\\d+\\.\\d+)"), 0),
    source_port = arrayindex(regextract(_raw_log, "port\\s+(\\d+)"), 0),
    message = arrayindex(regextract(_raw_log, "\\d{{4}}-\\d{{2}}-\\d{{2}}T\\d{{2}}:\\d{{2}}:\\d{{2}}[Z\\d\\.]*\\s+\\S+\\s+\\w+[:\\s]+(.*)$"), 0)
| alter
    xdm.event.type = event_type,
    xdm.source.user.username = username,
    xdm.source.ipv4 = source_ip,
    xdm.source.port = to_integer(source_port),
    xdm.event.description = message;
"""

        schema_json = f"""{{
  "{dataset}": {{
    "_raw_log": {{
      "type": "string",
      "is_array": false
    }}
  }}
}}
"""

        with open(rules_dir / f"{rule_file_base}.yml", "w", encoding="utf-8") as f:
            f.write(rule_yml)

        with open(rules_dir / f"{rule_file_base}.xif", "w", encoding="utf-8") as f:
            f.write(xif_content)

        with open(rules_dir / f"{rule_file_base}_schema.json", "w", encoding="utf-8") as f:
            f.write(schema_json)

    def _create_release_notes(self, pack_path: Path, pack_name: str) -> None:
        """Create ReleaseNotes folder with initial version file.
        
        Creates a 1_0_0.md file documenting the initial release.
        """
        notes_dir = pack_path / "ReleaseNotes"
        notes_dir.mkdir(exist_ok=True)

        release_content = f"""#### Parsing Rules

##### {pack_name} Parsing Rule

- Initial release of {pack_name} parsing rules.

#### Modeling Rules

##### {pack_name} Modeling Rule

- Initial release of {pack_name} modelling rules for XDM mapping.

#### Correlation Rules

##### {pack_name} - Multiple Failed Login Attempts

- Initial release of brute force detection correlation rule.

#### XSIAM Dashboards

##### {pack_name} Example

- Initial release of example dashboard.

#### XSIAM Reports

##### {pack_name} Example

- Initial release of example report.

#### Triggers

##### {pack_name} Alert Handler

- Initial release of alert handler trigger.
"""

        with open(notes_dir / "1_0_0.md", "w", encoding="utf-8") as f:
            f.write(release_content)

    def _create_xsiam_dashboard(self, pack_path: Path, pack_name: str) -> None:
        """Create sample XSIAM dashboard for Cortex Platform.
        
        Creates an example dashboard JSON file that can be uploaded to XSIAM.
        The dashboard includes a header and sample widgets.
        Structure matches the format exported from XSIAM Dashboard Manager.
        """
        dashboards_dir = pack_path / "XSIAMDashboards"
        dashboards_dir.mkdir(exist_ok=True)
        
        dashboard_id = f"{pack_name.lower()}_example_dashboard"
        dashboard_name = f"{pack_name} Example"
        
        dashboard_data = {
            "dashboards_data": [
                {
                    "name": dashboard_name,
                    "description": f"An example dashboard for {pack_name}",
                    "status": "ENABLED",
                    "layout": [
                        {
                            "id": "row-header",
                            "data": [
                                {
                                    "key": "header",
                                    "data": {
                                        "name": dashboard_name,
                                        "type": "",
                                        "width": 100,
                                        "height": 250,
                                        "description": f"An example dashboard for {pack_name}"
                                    }
                                }
                            ]
                        }
                    ],
                    "global_id": dashboard_id,
                    "metadata": {"params": []}
                }
            ],
            "widgets_data": [],
            "id": dashboard_id,
            "name": dashboard_name
        }
        
        # The store rejects depth-one XSIAM filenames that do not start with
        # "<PackFolder>_" (demisto-sdk XSIAM_DEPTH_1_CHECKS).
        dashboard_path = dashboards_dir / f"{pack_name}_ExampleDashboard.json"
        with open(dashboard_path, "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, indent=2)
            f.write("\n")
    
    def _create_xsiam_report(self, pack_path: Path, pack_name: str) -> None:
        """Create sample XSIAM report for Cortex Platform.
        
        Creates an example report JSON file that can be uploaded to XSIAM.
        The report includes a header and sample layout.
        Structure matches the format exported from XSIAM Report Templates.
        """
        reports_dir = pack_path / "XSIAMReports"
        reports_dir.mkdir(exist_ok=True)
        
        report_id = f"{pack_name.lower()}_example_report"
        report_name = f"{pack_name} Example"
        
        report_data = {
            "templates_data": [
                {
                    "report_name": report_name,
                    "report_description": f"An example report for {pack_name}",
                    "layout": [
                        {
                            "id": "row-header",
                            "data": [
                                {
                                    "key": "header",
                                    "data": {
                                        "name": report_name,
                                        "type": "",
                                        "width": 100,
                                        "height": 250,
                                        "description": f"An example report for {pack_name}"
                                    }
                                }
                            ]
                        }
                    ],
                    "default_template_id": None,
                    "time_frame": {"relativeTime": 86400000},
                    "global_id": report_id,
                    "time_offset": 0,
                    "metadata": "{\"params\": []}"
                }
            ],
            "widgets_data": [],
            "id": report_id,
            "name": report_name
        }
        
        # See the dashboard note above: the "<PackFolder>_" prefix is required.
        report_path = reports_dir / f"{pack_name}_ExampleReport.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
            f.write("\n")

    def create_agentix_content(self, pack_path: Path, pack_name: str) -> None:
        """Write SamplePack Agentix starter items.

        Called only from instance init. `create` does not scaffold empty
        Agentix directories: AG110 requires a `_systeminstructions.md`
        sidecar whose name uses an underscore, and empty Agentix folders
        on every detection pack would trip filename checks.
        """
        self._create_sample_agent(pack_path)
        self._create_sample_score_script(pack_path)
        self._create_sample_score_action(pack_path)
        self._create_sample_skill(pack_path)
        self._create_sample_collection(pack_path)
        self._append_agentix_readme(pack_path)
        self._append_agentix_release_notes(pack_path, pack_name)

    def _write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _create_sample_agent(self, pack_path: Path) -> None:
        agent_id = "sample-analyst-agent"
        item_dir = pack_path / "AgentixAgents" / agent_id
        self._write_text(
            item_dir / f"{agent_id}.yml",
            f"""commonfields:
  id: {agent_id}
  version: -1
display: Sample Analyst
name: Sample Analyst
tags:
  - example
category: Utilities
description: >-
  Starter Agentix agent. Score one alert with Sample Score, then read the
  sample collection before you escalate. Replace these items with a real
  agent, or reshape them after init.
color: "#4C6FFF"
visibility: public
systeminstructions: ""
conversationstarters:
  - "Score this sample alert: deny, src 203.0.113.10, dst port 3389"
actionids:
  - SampleScoreAction
builtinactions:
  - InvokeLLM
skillids:
  - sample-analyst-skill
collectionids:
  - SampleWorkedAlertsCollection
autoenablenewactions: false
roles:
  - Analyst
sharedwithroles:
  - Analyst
marketplaces:
  - platform
supportedModules:
  - agentix
""",
        )
        self._write_text(
            item_dir / f"{agent_id}_systeminstructions.md",
            """You are the Sample Analyst. Score the alert first, then consult the
sample collection before you escalate.

Follow the Sample Analyst skill. Run Sample Score before you form an
opinion. The collection carries estate facts that can override a high
score.

Close with one verdict, the evidence it rests on, and nothing else.
""",
        )

    def _create_sample_score_script(self, pack_path: Path) -> None:
        gitkeep = pack_path / "Scripts" / ".gitkeep"
        if gitkeep.exists():
            gitkeep.unlink()
        script_dir = pack_path / "Scripts" / "SampleScoreScript"
        self._write_text(
            script_dir / "SampleScoreScript.yml",
            """commonfields:
  id: SampleScoreScript
  version: -1
name: SampleScoreScript
comment: >-
  Deterministic 0-100 score for a single sample alert. Backs Sample Score.
script: ''
type: python
subtype: python3
dockerimage: demisto/python3:3.9.8.24399
args:
  - name: alert
    description: One alert as a JSON object (action, src_ip, dst_port).
    required: true
outputs:
  - contextPath: SampleAlert.Score.score
    description: Risk score from 0 to 100.
    type: Number
  - contextPath: SampleAlert.Score.band
    description: informational, low, medium or high.
    type: String
fromversion: 8.14.0
tags: []
marketplaces:
  - platform
""",
        )
        self._write_text(
            script_dir / "SampleScoreScript.py",
            '''"""Sample Score Script - starter scoring for the Sample Analyst agent."""

import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401,F403

import json

ADMIN_PORTS = {22, 23, 445, 3389, 5900}


def score_alert(alert):
    reasons = []
    score = 0
    action = str(alert.get("action", "")).lower()
    if action in ("deny", "drop", "reset"):
        score += 40
        reasons.append("action=%s (+40)" % action)
    try:
        port = int(alert.get("dst_port") or 0)
    except (TypeError, ValueError):
        port = 0
    if port in ADMIN_PORTS:
        score += 40
        reasons.append("destination port %d is an admin service (+40)" % port)
    score = min(score, 100)
    if score >= 70:
        band = "high"
    elif score >= 40:
        band = "medium"
    elif score > 0:
        band = "low"
    else:
        band = "informational"
        reasons.append("no scoring signal present in the alert")
    return score, band, reasons


def main():
    raw = demisto.args().get("alert") or "{}"
    try:
        alert = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError as exc:
        return_error("alert is not valid JSON: %s" % exc)
        return
    if not isinstance(alert, dict):
        return_error("alert must be a JSON object describing ONE alert")
        return
    score, band, reasons = score_alert(alert)
    return_results(
        CommandResults(
            outputs_prefix="SampleAlert.Score",
            outputs={"score": score, "band": band, "reasons": reasons},
            readable_output="### Sample alert score\\n**%d / 100 (%s)**" % (score, band),
        )
    )


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
''',
        )

    def _create_sample_score_action(self, pack_path: Path) -> None:
        action_id = "SampleScoreAction"
        item_dir = pack_path / "AgentixActions" / action_id
        self._write_text(
            item_dir / f"{action_id}.yml",
            """commonfields:
  id: SampleScoreAction
  version: -1
display: Sample Score
name: SampleScoreAction
tags:
  - example
category: Utilities
description: >-
  Score one sample alert 0-100 and band it informational / low / medium / high.
args:
  - name: alert
    description: One alert as JSON (action, src_ip, dst_port).
    type: string
    required: true
    isgeneratable: true
    underlyingargname: alert
outputs:
  - name: score
    description: Risk score from 0 to 100.
    type: number
    underlyingoutputcontextpath: SampleAlert.Score.score
  - name: band
    description: informational, low, medium or high.
    type: string
    underlyingoutputcontextpath: SampleAlert.Score.band
underlyingcontentitem:
  id: SampleScoreScript
  name: SampleScoreScript
  type: script
  version: -1
requiresuserapproval: false
fewshots:
  - >-
    Score a denied inbound hit: alert="{\\"action\\":\\"deny\\",\\"src_ip\\":\\"203.0.113.10\\",
    \\"dst_port\\":3389}". Returns high.
marketplaces:
  - platform
supportedModules:
  - agentix
""",
        )
        self._write_text(
            item_dir / f"{action_id}_test.yml",
            """tests:
  - name: scores a denied inbound RDP hit as high
    prompt: >-
      Score this alert: deny, src 203.0.113.10, dst port 3389.
    agent_id: sample-analyst-agent
    expected_outcomes:
      - evaluation_mode: any_of
        actions:
          - action_name: SampleScoreAction
        expected_output: high
fixtures: []
""",
        )

    def _create_sample_skill(self, pack_path: Path) -> None:
        skill_id = "sample-analyst-skill"
        item_dir = pack_path / "AgentixSkills" / skill_id
        self._write_text(
            item_dir / f"{skill_id}.yml",
            f"""commonfields:
  id: {skill_id}
  version: -1
name: Sample Analyst
description: >-
  Starter triage procedure: score the alert, then consult the sample collection.
content: ""
fromversion: 8.15.0
tags:
  - example
internal: false
disabled: false
marketplaces:
  - platform
supportedModules:
  - agentix
""",
        )
        self._write_text(
            item_dir / f"{skill_id}_skill.md",
            """# Sample analyst procedure

Work one alert at a time.

## 1. Score before you judge

Run <action=SampleScoreAction> on the alert first. A score of 0 banding
informational is a result - report it and stop.

## 2. Check the sample collection

Read the Sample Worked Alerts collection before you escalate. Known-benign
sources override a high score.

## 3. Close once

State the verdict, the score, and the evidence. Do not recommend containment.
""",
        )

    def _create_sample_collection(self, pack_path: Path) -> None:
        collection_id = "SampleWorkedAlertsCollection"
        item_dir = pack_path / "Collections" / collection_id
        self._write_text(
            item_dir / f"{collection_id}.yml",
            f"""commonfields:
  id: {collection_id}
  version: -1
name: Sample Worked Alerts
description: >-
  Starter collection handle. The sibling markdown is not pack content;
  spellbook upload pushes it to the Knowledge Center after install.
fromversion: 8.15.0
marketplaces:
  - platform
supportedModules:
  - agentix
""",
        )
        self._write_text(
            item_dir / "SampleWorkedAlerts.md",
            """# Sample worked alerts

Estate facts for the Sample Analyst. Replace this file with real knowledge.

- 203.0.113.0/24 is the documentation range. Hits from it are usually tests.
- Escalation code for a confirmed malicious admin-port hit: FW-SAMPLE-1.
""",
        )

    def _append_agentix_readme(self, pack_path: Path) -> None:
        readme_path = pack_path / "README.md"
        if not readme_path.is_file():
            return
        text = readme_path.read_text(encoding="utf-8")
        marker = "### Integrations"
        section = """### Agents

Starter Agentix agent (`sample-analyst-agent`) with system instructions.

### Actions

`SampleScoreAction`, backed by `SampleScoreScript`.

### Skills

`sample-analyst-skill`, the procedure the sample agent follows.

### Collections

`SampleWorkedAlertsCollection`. Sibling markdown is pushed as knowledge on upload.

### Integrations"""
        if marker in text:
            text = text.replace(marker, section, 1)
            readme_path.write_text(text, encoding="utf-8")

    def _append_agentix_release_notes(self, pack_path: Path, pack_name: str) -> None:
        notes_path = pack_path / "ReleaseNotes" / "1_0_0.md"
        extra = f"""
#### Agents

##### Sample Analyst

- Initial release of the {pack_name} sample agent.

#### Actions

##### Sample Score

- Initial release of the sample scoring action.

#### Skills

##### Sample Analyst

- Initial release of the sample analyst skill.

#### Collections

##### Sample Worked Alerts

- Initial release of the sample collection handle.
"""
        if notes_path.is_file():
            notes_path.write_text(
                notes_path.read_text(encoding="utf-8") + extra,
                encoding="utf-8",
            )

    def create_xsiam_content(self, pack_path: Path, pack_name: str) -> None:
        """Create Cortex Platform content structure.
        
        Creates complete XSIAM content including ParsingRules, ModelingRules,
        CorrelationRules, XSIAMDashboards, XSIAMReports, and ReleaseNotes.

        No Trigger is written. A trigger binds an issue to a playbook by
        the playbook's id, and this sample ships no playbook, so any
        trigger here would bind to nothing. The scaffold used to emit one
        carrying a PLAYBOOK_ID_HERE placeholder, which validation now
        rejects. The reference shape is in XSIAM_CONTENT_GUIDELINES.
        All templates follow the official demisto-sdk schemas and are based
        on working examples from the demisto/content repository.
        """
        self._create_parsing_rule(pack_path, pack_name)
        self._create_modeling_rule(pack_path, pack_name)
        self._create_correlation_rule(pack_path, pack_name)
        self._create_xsiam_dashboard(pack_path, pack_name)
        self._create_xsiam_report(pack_path, pack_name)
        self._create_release_notes(pack_path, pack_name)

    def list_templates(self) -> list[str]:
        """List available pack templates."""
        return ["default", "integration", "playbook", "minimal"]

    def create_from_template(
        self,
        template_name: str,
        pack_name: str,
        description: str = "",
        author: str | None = None,
        include_author_image: bool = True
    ) -> Path:
        """
        Create a pack from a predefined template.

        Args:
            template_name: Name of the template to use.
            pack_name: Name of the pack.
            description: Pack description.
            author: Pack author (uses the configured default if not provided).
            include_author_image: Scaffold the bundled author image at the
                pack root.

        Returns:
            Path to the created pack.
        """
        templates = {
            "default": self.CONTENT_DIRECTORIES,
            "integration": ["Integrations", "TestPlaybooks"],
            "playbook": ["Playbooks", "Scripts"],
            "minimal": []
        }

        directories = templates.get(template_name, self.CONTENT_DIRECTORIES)
        return self.create_pack(
            pack_name,
            description,
            author=author,
            create_directories=directories,
            include_author_image=include_author_image
        )

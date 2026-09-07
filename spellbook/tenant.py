# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: GoCortexIO
"""Tenant credentials for Cortex Platform upload and Knowledge Center calls."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping


class MissingCredentials(Exception):
    """One or more required tenant environment variables are unset."""

    def __init__(self, missing: tuple[str, ...]) -> None:
        self.missing = missing
        listed = ", ".join(missing)
        super().__init__(f"missing required environment variables: {listed}")


@dataclass(frozen=True)
class TenantCredentials:
    """Cortex Platform API credentials, resolved from the environment.

    Secret fields are excluded from repr. DEMISTO_* names are canonical;
    TENANT_BASE_URL / TENANT_API_KEY / TENANT_API_ID are accepted aliases.
    """

    base_url: str
    api_key: str = field(repr=False)
    auth_id: str = field(repr=False)

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> TenantCredentials:
        env = os.environ if environ is None else environ
        base_url = _first(env, "DEMISTO_BASE_URL", "TENANT_BASE_URL")
        api_key = _first(env, "DEMISTO_API_KEY", "TENANT_API_KEY")
        auth_id = _first(env, "XSIAM_AUTH_ID", "TENANT_API_ID")
        missing = tuple(
            name
            for name, value in (
                ("DEMISTO_BASE_URL", base_url),
                ("DEMISTO_API_KEY", api_key),
                ("XSIAM_AUTH_ID", auth_id),
            )
            if not value
        )
        if missing:
            raise MissingCredentials(missing)
        return cls(base_url=base_url.rstrip("/"), api_key=api_key, auth_id=auth_id)


def _first(env: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        value = env.get(name)
        if value:
            return value
    return None

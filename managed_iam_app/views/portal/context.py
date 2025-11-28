from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from managed_iam.schemas.orgs import OrgRegisterResponse
from managed_iam.services.integration import IntegrationLinks
from managed_iam.services.workload import WorkloadActionResult, WorkloadStatus


@dataclass
class PortalContext:
    alerts: list[dict[str, str]] = field(default_factory=list)
    created_user_id: str | None = None
    registration_result: OrgRegisterResponse | None = None
    selected_org: str | None = None
    integration_links: IntegrationLinks | None = None
    org_details: dict[str, Any] | None = None
    stack_status: WorkloadStatus | None = None
    workload_result: WorkloadActionResult | None = None
    created_keypair_name: str | None = None
    created_keypair_download: str | None = None

    def add_alert(self, level: str, message: str) -> None:
        self.alerts.append({"level": level, "message": message})


__all__ = ["PortalContext"]

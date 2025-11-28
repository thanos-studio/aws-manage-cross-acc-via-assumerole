from __future__ import annotations

from dataclasses import dataclass, field

from managed_iam.services.integration import IntegrationService
from managed_iam.services.orgs import OrganisationService
from managed_iam.services.users import UserService
from managed_iam.services.workload import WorkloadStackService


@dataclass(slots=True)
class PortalServices:
    user: UserService = field(default_factory=UserService)
    org: OrganisationService = field(default_factory=OrganisationService)
    workload: WorkloadStackService = field(default_factory=WorkloadStackService)
    integration: IntegrationService | None = None

    def __post_init__(self) -> None:
        if self.integration is None:
            self.integration = IntegrationService(org_service=self.org)


__all__ = ["PortalServices"]

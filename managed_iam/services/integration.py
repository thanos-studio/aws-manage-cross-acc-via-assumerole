"""Service for integration helper links."""

from __future__ import annotations

from dataclasses import dataclass
from shlex import quote as shell_quote

from managed_iam.config import settings
from managed_iam.services.orgs import OrganisationService
from managed_iam.services.stack import StackService


@dataclass
class IntegrationLinks:
    console_url: str
    aws_cli_command: str
    template_url: str
    region: str


class IntegrationService:
    def __init__(
        self,
        stack_service: StackService | None = None,
        org_service: OrganisationService | None = None,
    ) -> None:
        self._stack_service = stack_service or StackService()
        self._org_service = org_service or OrganisationService()

    async def build_links(
        self,
        *,
        org_name: str,
        aws_profile: str | None = None,
        expires_in: int = 3600,
    ) -> IntegrationLinks:
        record = await self._org_service.get_org(org_name)
        if not record:
            raise ValueError("organisation not found")

        external_id = self._org_service.decrypt_external_id(record)
        api_key = self._org_service.decrypt_api_key(record)
        template_info = self._stack_service.generate_template_url(org_name=org_name, expires_in=expires_in)
        parameters = {
            "OrganizationName": org_name,
            "ExternalId": external_id,
            "SunrinApiKey": api_key,
        }

        console_url = self._stack_service.console_url(
            stack_name=template_info.stack_name,
            template_url=template_info.template_url,
            region=template_info.region,
            parameters=parameters,
        )

        overrides = " ".join(shell_quote(f"{key}={value}") for key, value in parameters.items())
        profile_flag = f" --profile {shell_quote(aws_profile)}" if aws_profile else ""
        local_template = f"{template_info.stack_name}.template.yaml"
        download_command = (
            "curl -fsSL"
            f" {shell_quote(template_info.template_url)}"
            f" -o {shell_quote(local_template)}"
        )
        capabilities = " ".join(shell_quote(value) for value in ("CAPABILITY_NAMED_IAM", "CAPABILITY_IAM"))
        deploy_command = (
            "aws cloudformation deploy"
            f" --template-file {shell_quote(local_template)}"
            f" --stack-name {shell_quote(template_info.stack_name)}"
            f" --region {shell_quote(template_info.region)}"
            f" --parameter-overrides {overrides}"
            f" --capabilities {capabilities}"
            f"{profile_flag}"
        )
        cli_command = f"{download_command} && {deploy_command}"

        return IntegrationLinks(
            console_url=console_url,
            aws_cli_command=cli_command,
            template_url=template_info.template_url,
            region=template_info.region,
        )

from __future__ import annotations

from asgiref.sync import sync_to_async
from botocore.exceptions import ClientError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from managed_iam.schemas.orgs import OrgRegisterResponse
from managed_iam.services.integration import IntegrationService
from managed_iam_app.forms import (
    KeyPairForm,
    OrgLookupForm,
    OrgRegisterForm,
    UserCreateForm,
    WorkloadDeleteForm,
    WorkloadDeployForm,
)
from managed_iam_app.views.portal.actions import (
    handle_create_keypair,
    handle_create_user,
    handle_delete_workload,
    handle_deploy_workload,
    handle_register_org,
)
from managed_iam_app.views.portal.context import PortalContext
from managed_iam_app.views.portal.services import PortalServices


async def portal(request: HttpRequest) -> HttpResponse:
    services = PortalServices()
    portal_state = PortalContext()

    lookup_form = _resolve_selected_org(OrgLookupForm(request.GET or None), portal_state)
    user_form = UserCreateForm()
    register_form = OrgRegisterForm()
    deploy_form: WorkloadDeployForm | None = None
    delete_form: WorkloadDeleteForm | None = None
    keypair_form = KeyPairForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_user":
            user_form = await handle_create_user(UserCreateForm(request.POST), services=services, context=portal_state)
        elif action == "register_org":
            register_form = await handle_register_org(
                OrgRegisterForm(request.POST),
                services=services,
                context=portal_state,
            )
        elif action == "deploy_workload":
            deploy_form = await handle_deploy_workload(
                WorkloadDeployForm(request.POST),
                services=services,
                context=portal_state,
            )
        elif action == "delete_workload":
            delete_form = await handle_delete_workload(
                WorkloadDeleteForm(request.POST),
                services=services,
                context=portal_state,
            )
        elif action == "create_keypair":
            keypair_form = await handle_create_keypair(
                KeyPairForm(request.POST),
                services=services,
                context=portal_state,
            )

    if request.method != "GET" or not lookup_form.is_bound or not lookup_form.is_valid():
        initial = {"org_name": portal_state.selected_org} if portal_state.selected_org else None
        lookup_form = OrgLookupForm(initial=initial)

    if portal_state.selected_org:
        deploy_form, delete_form, keypair_form = await _hydrate_selected_org(
            portal_state.selected_org,
            services=services,
            portal_state=portal_state,
            deploy_form=deploy_form,
            delete_form=delete_form,
            keypair_form=keypair_form,
        )

    context = {
        "user_form": user_form,
        "register_form": register_form,
        "lookup_form": lookup_form,
        "deploy_form": deploy_form,
        "delete_form": delete_form,
        "keypair_form": keypair_form,
        "alerts": portal_state.alerts,
        "created_user_id": portal_state.created_user_id,
        "registration_result": portal_state.registration_result,
        "selected_org": portal_state.selected_org,
        "org_details": portal_state.org_details,
        "integration_links": portal_state.integration_links,
        "stack_status": portal_state.stack_status,
        "workload_result": portal_state.workload_result,
        "created_keypair_name": portal_state.created_keypair_name,
        "created_keypair_download": portal_state.created_keypair_download,
    }
    return await sync_to_async(render)(request, "portal.html", context)


async def _hydrate_selected_org(
    org_name: str,
    *,
    services: PortalServices,
    portal_state: PortalContext,
    deploy_form: WorkloadDeployForm | None,
    delete_form: WorkloadDeleteForm | None,
    keypair_form: KeyPairForm,
) -> tuple[WorkloadDeployForm | None, WorkloadDeleteForm | None, KeyPairForm]:
    record = await services.org.get_org(org_name)
    if not record:
        portal_state.add_alert("error", f"Organisation '{org_name}' not found.")
        portal_state.org_details = None
        return deploy_form, delete_form, keypair_form

    portal_state.org_details = {
        "org_name": record.org_name,
        "owner_user_id": record.owner_user_id,
        "validated": record.validation_status,
        "validation_updated_at": record.validation_updated_at.isoformat() if record.validation_updated_at else None,
        "account_id": record.account_id,
        "account_partition": record.account_partition,
        "account_tags": record.account_tags or {},
    }

    portal_state.integration_links = None
    integration_service = services.integration or IntegrationService(org_service=services.org)
    try:
        portal_state.integration_links = await integration_service.build_links(org_name=record.org_name)
    except ValueError as exc:
        portal_state.add_alert("error", str(exc))

    deploy_form = deploy_form or _default_deploy_form(record.org_name, record.owner_user_id, portal_state.registration_result)
    delete_form = delete_form or WorkloadDeleteForm(initial={"org_name": record.org_name})

    keypair_initial = {
        "org_name": record.org_name,
        "user_id": record.owner_user_id,
        "api_key": portal_state.registration_result.api_key if portal_state.registration_result else "",
    }
    if not keypair_form.is_bound:
        keypair_form = KeyPairForm(initial=keypair_initial)

    if record.validation_status and record.account_id:
        try:
            portal_state.stack_status = await services.workload.describe_stack(record.org_name)
        except (ValueError, PermissionError, ClientError) as exc:
            portal_state.add_alert("error", str(exc))
            portal_state.stack_status = None
    else:
        portal_state.stack_status = None

    return deploy_form, delete_form, keypair_form


def _default_deploy_form(
    org_name: str,
    owner_user_id: str,
    registration_result: OrgRegisterResponse | None,
) -> WorkloadDeployForm:
    default_env = f"{org_name}-prod"
    initial = {
        "org_name": org_name,
        "user_id": owner_user_id,
        "api_key": registration_result.api_key if registration_result else "",
        "environment_name": default_env,
        "bastion_allowed_cidr": "0.0.0.0/0",
        "dynamo_table_name": f"{org_name}AppTable",
    }
    return WorkloadDeployForm(initial=initial)


def _resolve_selected_org(form: OrgLookupForm, portal_state: PortalContext) -> OrgLookupForm:
    if form.is_bound and form.is_valid():
        portal_state.selected_org = form.cleaned_data["org_name"]
    return form


__all__ = ["portal"]

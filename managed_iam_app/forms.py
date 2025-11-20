from __future__ import annotations

import json
from typing import Any

from django import forms


class UserCreateForm(forms.Form):
    metadata = forms.CharField(
        label="Metadata (JSON)",
        required=False,
        help_text="Optional JSON blob stored with the operator identity.",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": '{"team": "platform"}'}),
    )

    def metadata_dict(self) -> dict[str, Any]:
        value = self.cleaned_data.get("metadata")
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Metadata must be valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise forms.ValidationError("Metadata JSON must be an object.")
        return parsed


class OrgRegisterForm(forms.Form):
    user_id = forms.CharField(label="Operator user_id", max_length=64)
    org_name = forms.CharField(
        label="Organisation name",
        max_length=32,
        help_text="Allowed characters: letters, numbers, dash, underscore.",
    )


class OrgLookupForm(forms.Form):
    org_name = forms.CharField(label="Organisation name", max_length=64)


class WorkloadDeployForm(forms.Form):
    org_name = forms.CharField(widget=forms.HiddenInput())
    environment_name = forms.CharField(
        label="Environment name",
        max_length=64,
        help_text="Used as prefix for resource names and tags.",
    )
    bastion_key_pair = forms.CharField(label="Bastion key pair name", max_length=128)
    bastion_allowed_cidr = forms.CharField(
        label="Bastion allowed CIDR",
        max_length=64,
        initial="0.0.0.0/0",
        help_text="Restrict SSH ingress to trusted networks.",
    )
    dynamo_table_name = forms.CharField(label="DynamoDB table name", max_length=128)
    asg_desired_capacity = forms.IntegerField(
        label="WAS desired capacity",
        min_value=1,
        max_value=10,
        initial=2,
        help_text="Overrides the Auto Scaling desired capacity (default 2).",
        required=False,
    )


class WorkloadDeleteForm(forms.Form):
    org_name = forms.CharField(widget=forms.HiddenInput())
    confirm_text = forms.CharField(
        label="Type DELETE to confirm",
        max_length=6,
        help_text="Enter DELETE (in caps) to remove the workload stack.",
    )

    def clean_confirm_text(self) -> str:
        value = self.cleaned_data["confirm_text"].strip().upper()
        if value != "DELETE":
            raise forms.ValidationError("Type DELETE in uppercase to confirm removal.")
        return value

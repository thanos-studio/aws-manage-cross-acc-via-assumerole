from __future__ import annotations

import re
from dataclasses import dataclass

from django import forms

IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class UserRegistrationForm(forms.Form):
    pass


class OrganizationRegistrationForm(forms.Form):
    user_id = forms.CharField()
    org_name = forms.CharField()
    region = forms.CharField(required=False)

    def clean_user_id(self) -> str:
        user_id = self.cleaned_data["user_id"].strip()
        if not IDENTIFIER_RE.match(user_id):
            raise forms.ValidationError("user_id must use alphanumeric characters, dashes, or underscores")
        return user_id

    def clean_org_name(self) -> str:
        org_name = self.cleaned_data["org_name"].strip()
        if not IDENTIFIER_RE.match(org_name):
            raise forms.ValidationError("org_name must use alphanumeric characters, dashes, or underscores")
        return org_name

    def clean_region(self) -> str:
        region = self.cleaned_data.get("region") or "us-east-1"
        return region


@dataclass(frozen=True)
class StackRequest:
    user_id: str
    org_name: str
    region: str
    origin_bucket: str


class StackLaunchForm(forms.Form):
    user_id = forms.CharField()
    org_name = forms.CharField()
    region = forms.CharField()
    origin_bucket = forms.CharField()

    def clean_user_id(self) -> str:
        user_id = self.cleaned_data["user_id"].strip()
        if not IDENTIFIER_RE.match(user_id):
            raise forms.ValidationError("user_id must use alphanumeric characters, dashes, or underscores")
        return user_id

    def clean_org_name(self) -> str:
        org_name = self.cleaned_data["org_name"].strip()
        if not IDENTIFIER_RE.match(org_name):
            raise forms.ValidationError("org_name must use alphanumeric characters, dashes, or underscores")
        return org_name

    def clean_region(self) -> str:
        region = self.cleaned_data["region"].strip()
        if not IDENTIFIER_RE.match(region.replace("-", "")):
            raise forms.ValidationError("region must follow AWS naming (e.g., us-east-1)")
        return region

    def clean_origin_bucket(self) -> str:
        bucket = self.cleaned_data["origin_bucket"].strip()
        if not IDENTIFIER_RE.match(bucket.replace(".", "")):
            raise forms.ValidationError("origin_bucket contains invalid characters")
        return bucket

    def clean(self):
        cleaned = super().clean()
        return cleaned

    def to_stack_request(self) -> StackRequest:
        if not self.is_valid():  # pragma: no cover - guard
            raise ValueError("Form is not valid")
        return StackRequest(
            user_id=self.cleaned_data["user_id"],
            org_name=self.cleaned_data["org_name"],
            region=self.cleaned_data["region"],
            origin_bucket=self.cleaned_data["origin_bucket"],
        )

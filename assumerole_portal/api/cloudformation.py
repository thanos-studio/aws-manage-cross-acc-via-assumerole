from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote


CLOUDFRONT_TEMPLATE = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": "CloudFront distribution for AssumeRole onboarding",
    "Parameters": {
        "OriginBucket": {
            "Type": "String",
            "Description": "S3 bucket backing the CloudFront distribution",
        },
        "ExternalId": {
            "Type": "String",
            "Description": "Identifier tying the distribution back to the onboarding org",
        },
        "ViewerProtocolPolicy": {
            "Type": "String",
            "AllowedValues": ["allow-all", "redirect-to-https", "https-only"],
            "Default": "redirect-to-https",
        },
    },
    "Resources": {
        "Distribution": {
            "Type": "AWS::CloudFront::Distribution",
            "Properties": {
                "DistributionConfig": {
                    "Enabled": True,
                    "Origins": [
                        {
                            "Id": {"Ref": "OriginBucket"},
                            "DomainName": {"Fn::Join": ["", [{"Ref": "OriginBucket"}, ".s3.amazonaws.com"]]},
                            "S3OriginConfig": {"OriginAccessIdentity": ""},
                        }
                    ],
                    "DefaultCacheBehavior": {
                        "TargetOriginId": {"Ref": "OriginBucket"},
                        "ViewerProtocolPolicy": {"Ref": "ViewerProtocolPolicy"},
                        "AllowedMethods": ["GET", "HEAD"],
                        "CachedMethods": ["GET", "HEAD"],
                        "ForwardedValues": {
                            "QueryString": False,
                            "Cookies": {"Forward": "none"},
                        },
                    },
                    "DefaultRootObject": "index.html",
                    "Comment": {"Fn::Sub": "Provisioned via AssumeRole portal for ${ExternalId}"},
                }
            },
            "DeletionPolicy": "Retain",
            "UpdateReplacePolicy": "Retain",
            "Metadata": {
                "ExternalId": {"Ref": "ExternalId"},
            },
        }
    },
    "Outputs": {
        "DistributionId": {
            "Description": "CloudFront distribution identifier",
            "Value": {"Ref": "Distribution"},
        },
        "ExternalId": {
            "Description": "External identifier used during provisioning",
            "Value": {"Ref": "ExternalId"},
        }
    },
}


@dataclass(frozen=True)
class StackLaunchLink:
    region: str
    stack_name: str
    parameters: dict[str, Any]

    def console_url(self, template: dict[str, Any] | None = None) -> str:
        template_body = json.dumps(template or CLOUDFRONT_TEMPLATE)
        encoded_body = quote(template_body, safe="")
        param_fragment = "".join(
            f"&param_{quote(name)}={quote(str(value))}"
            for name, value in self.parameters.items()
        )
        return (
            f"https://console.aws.amazon.com/cloudformation/home?region={self.region}"  # noqa: E501
            f"#/stacks/create/review?stackName={quote(self.stack_name)}"
            f"&templateBody={encoded_body}{param_fragment}"
        )

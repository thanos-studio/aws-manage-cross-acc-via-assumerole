# CloudFormation Templates

This folder stores launchable templates referenced by the API responses. Upload the template you plan to deploy to an S3 bucket or serve it from an internal catalog before sharing quick-create URLs with operators.

- `cloudfront_distribution.yaml`: provisions a CloudFront distribution fronting an S3 origin and tags the stack with the org's ExternalId.

When updating existing templates, bump the stack parameter defaults as needed and ensure `GET /api/stack` continues to embed valid parameters.

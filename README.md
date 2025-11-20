# Sunrin Managed IAM – Django Edition

This directory hosts a Django implementation of the Sunrin Managed IAM prototype. It exposes the
same API surface as the original FastAPI service while re-using the underlying encryption, Redis,
and AWS integration layers.

- `POST /api/users` – issue `user_id` values for Sunrin operators.
- `POST /api/register` – create organisation records, generating API keys and ExternalIds per org.
- `POST /api/integrate` – provide console links and AWS CLI commands to redeploy the template and nested validation stack.
- `POST /api/credentials` – broker STS credentials after validating CloudFormation deployment status.
- `POST /api/validate` – sanity check supplied STS credentials.
- `POST /api/integrations/validate` – accept the validation webhook from the one-off Lambda stack.
- `GET /api/health` – lightweight health probe used by load balancers.

The service encrypts API keys/ExternalIds with AES-GCM, stores Redis state with versioned keys, and
requires HMAC signed validation callbacks. AssumeRole sessions use the convention
`Sunrin-{org_name}-{user_id}` for CloudTrail traceability.

## Project layout

```
.
├── cloudformation/             # CloudFormation template served via S3
├── managed_iam/                # Domain logic shared across the API
├── managed_iam_app/            # Django views + URL routing
├── managed_iam_site/           # Django project configuration
├── manage.py                   # Django management entrypoint
└── pyproject.toml              # Poetry configuration and dependency list
```

## Prerequisites

- Python 3.12+
- Redis (local or remote). For development you can use Docker: `docker run -p 6379:6379 redis:7`
- AWS credentials capable of generating pre-signed S3 URLs and STS role credentials (not required
  for local testing when AWS calls are stubbed).

## Environment variables

Copy `.env.sample` to `.env` and replace the placeholder values:

```bash
cp .env.sample .env
# edit .env with a 32-byte base64 AES key, HMAC key, bucket name, etc.
python - <<'PY'
import os, base64
print("SUNRIN_ENCRYPTION_KEY=", base64.b64encode(os.urandom(32)).decode())
print("SUNRIN_HMAC_KEY=", base64.b64encode(os.urandom(32)).decode())
PY
```

Key settings (all prefixed with `SUNRIN_`):

- `ENCRYPTION_KEY` – base64 encoded, 32-byte AES-GCM key used to encrypt API keys.
- `HMAC_KEY` – base64 encoded, 32-byte key for deriving validation webhook signatures.
- `TEMPLATE_BUCKET` / `TEMPLATE_KEY` – S3 location of `cloudformation/stack.yaml`.
- `AWS_REGION` – region for S3 pre-signed URLs, STS calls, and CloudFormation console links.
- `PROVIDER_ACCOUNT_ID` – Sunrin’s AWS account (default `628897991799`).
- `ENCRYPTION_KEY` and `HMAC_KEY` **must** decode to at least 32 bytes; AES requires 128/192/256-bit keys.

## Installing dependencies

```bash
poetry install
```

> **Note:** Installation requires network access to PyPI. If your environment prohibits outbound
> traffic, install dependencies from an internal mirror instead.

## Running the development server

```bash
poetry run python manage.py migrate   # optional: configure Django's auth DB
poetry run python manage.py runserver 0.0.0.0:8000
```

The API is served under the `/api` prefix. For example, `POST http://localhost:8000/api/users`
issues a new operator identity.

You can also start the server with `python -m managed_iam`, which proxies to the Django dev server.

### HTML operator portal

The root path (`/`) exposes a lightweight HTML console where operators can:

- Issue new `user_id` values and register organisations without calling the JSON APIs manually.
- Generate CloudFormation console links/CLI scripts used to connect customer accounts.
- Inspect validation status, connected account metadata, and workload deployment state for a selected organisation.
- Deploy, update, or delete the reference workload stack defined in `cloudformation/workload-stack.yaml`
  directly from the UI (the app assumes the customer's `SunrinPowerUser` role to call CloudFormation).

See `docs/deploy-workload.md` if you prefer running the workload deployment via CLI.

## Endpoint summary

| Method & Path                        | Description                                                                 |
|-------------------------------------|-----------------------------------------------------------------------------|
| `POST /api/users`                   | Issue a new `user_id` and optional metadata entry.                          |
| `POST /api/register?user_id=`       | Register an organisation, generating API key + ExternalId.                  |
| `POST /api/integrate?user_id=`      | Produce console links and AWS CLI commands for redeployment.                |
| `POST /api/credentials?user_id=`    | Assume the Sunrin role in the customer account (requires validation pass). |
| `POST /api/validate`                | Test arbitrary STS credentials for read access.                             |
| `POST /api/integrations/validate`   | Validation webhook (HMAC protected) called by the one-off Lambda stack.     |
| `GET /api/health`                   | Lightweight health probe.                                                   |

Authenticated endpoints require `user_id` as a query parameter; until JWT support is introduced,
requests should be rate-limited and logged. `POST /api/credentials` and `POST /api/validate` will
reject requests with HTTP 412 if the validation Lambda has not marked the org as deployed. The error
body contains console links and CLI commands (including optional `aws_profile`) that mirror the
output from `/api/integrate`.

## S3 CloudFormation template

The CloudFormation template lives under `cloudformation/stack.yaml`. Upload the file referenced in
`SUNRIN_TEMPLATE_BUCKET` / `SUNRIN_TEMPLATE_KEY` so the API can generate download links. The
template provisions a single cross-account role (`SunrinPowerUser`) with the AWS managed
`PowerUserAccess` policy and also launches the validation nested stack used to confirm the
deployment. The assume-role session duration remains 3600 seconds.

### Customer workload stack

After the customer deploys the `SunrinPowerUser` role, you can assume it and roll out the reference
workload defined in `cloudformation/workload-stack.yaml`. This stack creates the VPC, two public
and two private subnets, dual NAT gateways, a bastion instance, an ALB-backed WAS Auto Scaling
group, and a DynamoDB table scoped to the app role. See `docs/deploy-workload.md` for the
step-by-step runbook (including how to export the assumed-role session and call
`aws cloudformation deploy`).

## Running tests

pytest support is available; Django-specific tests can be added under a `tests/` package.

```bash
poetry run pytest
```

Tests rely on `fakeredis` and stubbed AWS clients. If network access to install dependencies is not
available, install them manually in an environment with PyPI access and copy the wheelhouse locally.

## Validation webhook HMAC

The validation Lambda must sign requests using the decrypted API key as the HMAC secret:

```
signature = HMAC-SHA256(secret=api_key, message=f"{timestamp}|{nonce}|{body}")
headers:
  X-Sig-Signature: <hex digest>
  X-Sig-Timestamp: <unix epoch seconds>
  X-Sig-Nonce: <unique nonce>
```

`POST /api/integrations/validate` verifies the signature, ensures the payload API key matches the
stored value, marks the organisation as validated, and unlocks the STS credential flow.

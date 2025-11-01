# aws-manage-another-acc-via-assumerole

This project provides a Django-based dashboard and automation toolkit for managing another AWS account via `sts:AssumeRole`. It pairs web-accessible documentation with reproducible scripts and CloudFormation launch links so operators can review, test, and deploy changes confidently.

## Getting Started

1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
2. Copy `.env.template` to `.env` and populate secrets:
   ```bash
   cp .env.template .env
   ```
3. Run database migrations and start the development server:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

Visit `http://127.0.0.1:8000/docs` for interactive API docs or call the endpoints under `/api/` directly.

## REST API

- `POST /api/users` – issues a new operator `user_id`.
- `POST /api/register` – registers an organization for a user and returns API credentials.
- `GET /api/stack` – returns an AWS CloudFormation quick-create URL for provisioning a CloudFront stack (`user_id`, `org_name`, `region`, `origin_bucket` required).
- `/docs` – interactive Swagger UI backed by the generated OpenAPI document at `/api/openapi.json`.

Refer to `AGENTS.md` for detailed contributor expectations.

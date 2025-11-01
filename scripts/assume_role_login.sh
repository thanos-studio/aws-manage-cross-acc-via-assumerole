#!/usr/bin/env bash
set -euo pipefail

# Provides a short-lived shell with credentials from a target AWS account.
# Usage: ./scripts/assume_role_login.sh <target-account-id> <role-name> [session-name]

usage() {
  echo "Usage: $0 <target-account-id> <role-name> [session-name]" >&2
  exit 1
}

if [[ ${1:-} == "" || ${2:-} == "" ]]; then
  usage
fi

TARGET_ACCOUNT_ID=$1
ROLE_NAME=$2
SESSION_NAME=${3:-$(whoami)-$(date +%Y%m%d%H%M%S)}
PROFILE=${AWS_PROFILE:-management}

echo "Assuming role arn:aws:iam::${TARGET_ACCOUNT_ID}:role/${ROLE_NAME} via profile ${PROFILE}" >&2
CREDS_JSON=$(aws sts assume-role \
  --profile "${PROFILE}" \
  --role-arn "arn:aws:iam::${TARGET_ACCOUNT_ID}:role/${ROLE_NAME}" \
  --role-session-name "${SESSION_NAME}" \
  --duration-seconds 3600)

export AWS_ACCESS_KEY_ID=$(jq -r '.Credentials.AccessKeyId' <<<"${CREDS_JSON}")
export AWS_SECRET_ACCESS_KEY=$(jq -r '.Credentials.SecretAccessKey' <<<"${CREDS_JSON}")
export AWS_SESSION_TOKEN=$(jq -r '.Credentials.SessionToken' <<<"${CREDS_JSON}")

PS1="(assume:${TARGET_ACCOUNT_ID}) ${PS1:-}\$ " exec "$SHELL"

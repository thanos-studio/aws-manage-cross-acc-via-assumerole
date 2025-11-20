# Customer Workload Deployment

The `cloudformation/workload-stack.yaml` template provisions the shared network and compute
foundation (VPC, subnets, bastion, ALB-backed WAS Auto Scaling group, and DynamoDB table) inside a
customer account. Deploy it after you have validated the `SunrinPowerUser` role in the target
account.

## 1. Assume the customer session

Use the console link or AWS CLI snippet returned by `POST /api/integrate` / `POST /api/credentials`
to assume the cross-account role. When assuming through the CLI, export the credentials locally:

```bash
ROLE_ARN="arn:aws:iam::<customer-account-id>:role/SunrinPowerUser"
SESSION_NAME="Sunrin-myorg-myuser"
aws sts assume-role \
  --role-arn "${ROLE_ARN}" \
  --role-session-name "${SESSION_NAME}" \
  --external-id "<ExternalId from /api/register>" \
  --duration-seconds 3600 \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text |
  read AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
export AWS_REGION="ap-northeast-2"
```

> You can also store them in an AWS CLI profile (`aws configure set profile sunrin-session ...`)
> and pass `--profile sunrin-session` to subsequent commands.

## 2. Deploy the workload stack

Run the deployment from the project root. Required parameters are the bastion key pair name and any
custom CIDR blocks that differ from the defaults.

```bash
WORKLOAD_STACK="sunrin-managed-workload"
aws cloudformation deploy \
  --template-file cloudformation/workload-stack.yaml \
  --stack-name "${WORKLOAD_STACK}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      EnvironmentName=myorg-prod \
      BastionKeyPairName=my-existing-key \
      BastionAllowedCidr=203.0.113.0/24 \
      DynamoTableName=MyOrgAppTable
```

The stack creates:

- `10.20.0.0/16` VPC with two public and two private subnets, an internet gateway, and dual NAT
  gateways for the private subnets.
- Bastion EC2 instance (Amazon Linux 2023) in the first public subnet with SSM Session Manager.
- Application Load Balancer spanning the public subnets.
- Private Auto Scaling group (Amazon Linux 2023) running NGINX on port 80 across the private
  subnets, fronted by the ALB and reachable from the bastion on SSH.
- DynamoDB table (`PK/SK` schema, on-demand billing) with IAM permissions scoped to the WAS role.

## 3. Post-deployment validation

1. Check stack completion: `aws cloudformation describe-stacks --stack-name "${WORKLOAD_STACK}"`.
2. Retrieve the load balancer endpoint:
   `aws cloudformation describe-stacks --stack-name "${WORKLOAD_STACK}" --query 'Stacks[0].Outputs'`.
3. Confirm bastion access via SSH or SSM using the exported credentials.
4. (Optional) Update DNS to point to the ALB DNS name exposed in the outputs.

When the deployment is complete you can persist the assumed role credentials in AWS SSO or ask the
customer to redeploy with the generated CLI script.

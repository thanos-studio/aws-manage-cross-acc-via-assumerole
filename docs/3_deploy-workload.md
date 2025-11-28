# 고객 워크로드 배포

`cloudformation/workload-stack.yaml` 템플릿은 고객 계정 안에 공용 네트워크·컴퓨팅 기반(VPC, 서브넷,
베스천, ALB가 앞단에 있는 WAS 오토스케일링 그룹, DynamoDB 테이블)을 구축합니다. 대상 계정에서
`SunrinPowerUser` 역할 검증을 끝낸 뒤 배포하세요.

## 1. 고객 세션 가정하기

`POST /api/integrate`, `POST /api/credentials` 응답에 포함된 콘솔 링크나 AWS CLI 스니펫으로
교차 계정 역할을 가정합니다. CLI로 가정할 경우 아래처럼 자격 증명을 로컬 환경 변수에 설정하세요.

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

> AWS CLI 프로필(`aws configure set profile sunrin-session ...`)에 저장한 뒤 이후 명령어에
> `--profile sunrin-session`을 전달해도 됩니다.

## 2. 워크로드 스택 배포

프로젝트 루트에서 배포 명령을 실행하세요. 반드시 입력해야 하는 파라미터는 베스천 키 페어 이름과
기본값과 다른 CIDR 블록입니다.

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

스택이 생성하는 리소스:

- `10.20.0.0/16` VPC: 공용 2개 + 프라이빗 2개 서브넷, 인터넷 게이트웨이, 프라이빗 구간용 듀얼 NAT
  게이트웨이.
- 첫 번째 공용 서브넷에 위치한 베스천 EC2 인스턴스(Amazon Linux 2023, SSM Session Manager 지원).
- 공용 서브넷에 걸친 Application Load Balancer.
- 프라이빗 서브넷 전용 오토스케일링 그룹(Amazon Linux 2023, 포트 80에서 NGINX 실행). ALB가 프런트에
  있고 베스천에서 SSH로 접근 가능.
- DynamoDB 테이블(`PK/SK` 스키마, 온디맨드 과금)과 WAS 역할 범위로 제한된 IAM 권한.

## 3. 배포 후 검증

1. 스택 완료 여부 확인:
   `aws cloudformation describe-stacks --stack-name "${WORKLOAD_STACK}"`.
2. 로드 밸런서 엔드포인트 조회:
   `aws cloudformation describe-stacks --stack-name "${WORKLOAD_STACK}" --query 'Stacks[0].Outputs'`.
3. 내보낸 자격 증명으로 SSH 또는 SSM을 통해 베스천 접속을 확인.
4. (선택) 출력에 표시된 ALB DNS 이름으로 DNS 레코드를 갱신.

배포가 끝나면 가정한 역할 자격 증명을 AWS SSO에 저장하거나, 생성된 CLI 스크립트를 사용해 고객에게
재배포를 요청할 수 있습니다.

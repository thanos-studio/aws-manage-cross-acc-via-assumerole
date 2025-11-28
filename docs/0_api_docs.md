서버구축 및 운영 REST서비스 API 명세서

본 문서는 Django 기반 Sunrin Managed IAM 서비스의 주요 REST 엔드포인트, 요청/응답 구조, 관련 AWS 동작을 정리한 것이다. 모든 요청은 `application/json`을 사용하며, 명시되지 않은 경우 기본 베이스 URL은 `/api`이다.

## 1. Health

### GET `/api/health`
- **설명**: 배포된 애플리케이션 상태 확인.
- **응답**:
  ```json
  {
    "status": "ok",
    "environment": "dev",
    "version": "0.1.0"
  }
  ```

## 2. 사용자/조직 온보딩

### POST `/api/users`
- **설명**: 운영자용 `user_id` 발급.
- **요청**:
  ```json
  {
    "metadata": {
      "team": "platform",
      "region": "ap-northeast-2"
    }
  }
  ```
- **응답 (201)**:
  ```json
  {
    "user_id": "AbC123xyz789",
    "metadata": {
      "team": "platform",
      "region": "ap-northeast-2"
    }
  }
  ```
- **AWS 연계**: 생성된 `user_id`는 이후 STS AssumeRole 시 `RoleSessionName`에 포함되어 CloudTrail 감사 추적에 사용됨.

### POST `/api/register?user_id=<operator-id>`
- **헤더**: `Idempotency-Key: <uuid>`
- **설명**: 조직 등록, API Key / External ID 발급.
- **요청**:
  ```json
  {
    "org_name": "customer-abc"
  }
  ```
- **응답 (201)**:
  ```json
  {
    "org_name": "customer-abc",
    "api_key": "AbCdEf1234...",
    "external_id": "XyZ987..."
  }
  ```
- **AWS 연계**: External ID는 고객 계정의 SunrinPowerUser 역할 정책 조건 `Condition: { "StringEquals": { "sts:ExternalId": ... } }`으로 사용.

## 3. 통합 및 검증 워크플로

### POST `/api/integrate?user_id=<operator-id>`
- **설명**: CloudFormation 콘솔 링크, CLI 스크립트, Presigned URL.
- **요청**:
  ```json
  {
    "org_name": "customer-abc",
    "api_key": "AbCdEf...",
    "aws_profile": "sunrin-ops",
    "expires_in": 3600
  }
  ```
- **응답 (200)**:
  ```json
  {
    "console_url": "https://console.aws.amazon.com/cloudformation/...",
    "aws_cli_command": "curl ... && aws cloudformation deploy ...",
    "template_url": "https://s3.amazonaws.com/.../workload-stack.yaml",
    "region": "ap-northeast-2"
  }
  ```
- **AWS 연계**: StackService가 S3 presign 또는 Public URL을 생성. 콘솔 링크는 `stackName`, `templateURL`, 파라미터를 fragment로 전달해 고객이 클릭 한 번으로 스택 생성 가능.

### POST `/api/validate`
- **설명**: 고객이 AssumeRole로 발급받은 세션을 검증.
- **요청**:
  ```json
  {
    "user_id": "AbC123",
    "org_name": "customer-abc",
    "api_key": "AbCdEf...",
    "aws_profile": "sunrin-ops",
    "access_key_id": "...",
    "secret_access_key": "...",
    "session_token": "...",
    "region": "ap-northeast-2"
  }
  ```
- **응답 (200)**:
  ```json
  {
    "success": true,
    "identity_arn": "arn:aws:sts::123456789012:assumed-role/SunrinPowerUser/Session123",
    "message": "credentials validated"
  }
  ```
- **AWS 연계**: boto3 STS `GetCallerIdentity` 호출. 실패 시 AWS 에러 메시지를 400으로 전달.

## 4. 자격 증명 발급 및 워크로드 제어

### POST `/api/credentials?user_id=<operator-id>&aws_profile=<optional>`
- **설명**: 서비스가 고객 계정을 대신해 STS 임시 자격 증명 발급.
- **요청**:
  ```json
  {
    "org_name": "customer-abc",
    "api_key": "AbCdEf...",
    "role_type": "readonly",
    "target_account_id": "123456789012"
  }
  ```
- **응답 (200)**:
  ```json
  {
    "access_key_id": "...",
    "secret_access_key": "...",
    "session_token": "...",
    "expiration": "2024-05-01T12:34:56Z",
    "console_url": "...",
    "aws_cli_command": "...",
    "template_url": "...",
    "region": "ap-northeast-2"
  }
  ```
- **AWS 연계**: STS `AssumeRole` 호출. `RoleArn`은 `arn:aws:iam::<target_account_id>:role/SunrinPowerUser`, `ExternalId`는 등록 시 발급된 값. 만료 시간은 3600초 고정.

### POST `/api/integrations/validate`
- **설명**: 고객 계정에서 실행되는 Lambda가 SaaS로 전송하는 검증 웹훅.
- **헤더**: `x-sig-signature`, `x-sig-timestamp`, `x-sig-nonce`
- **요청**:
  ```json
  {
    "org_name": "customer-abc",
    "api_key": "AbCdEf...",
    "account_id": "123456789012",
    "account_partition": "aws",
    "account_tags": {
      "Managed": "Sunrin"
    }
  }
  ```
- **응답 (200)**:
  ```json
  {
    "org_name": "customer-abc",
    "validated": true,
    "account_id": "123456789012",
    "account_partition": "aws",
    "account_tags": {
      "Managed": "Sunrin"
    }
  }
  ```
- **AWS 연계**: Lambda는 CloudFormation Custom Resource 또는 스택 성공 후 API Gateway를 통해 호출한다. SaaS는 HMAC-SHA256으로 서명을 검증하고, nonce를 Redis에 저장해 재사용 방지.

## 5. 포털 전용 액션 요약
- 루트 경로 `/`는 HTML 포털로 사용자, 조직, 워크로드 배포 절차를 UI로 제공한다.
- 내부적으로 `UserService`, `OrganisationService`, `WorkloadStackService`를 호출하며, boto3로 고객 계정 내 CloudFormation 스택을 생성/삭제한다.

## 6. 에러 처리
- 모든 API는 오류 시 `{ "detail": "message" }` 구조를 반환.
- 주요 상태 코드:
  - `400`: JSON 형식 오류, Pydantic 검증 실패, AWS STS/EC2 에러 메시지 전달.
  - `401`: API Key 불일치.
  - `404`: 존재하지 않는 사용자/조직.
  - `409`: 조직 중복 등록 또는 Idempotency 충돌.
  - `412`: 조직 검증 미완료 (CloudFormation 미배포).
  - `429`: 레이트 리밋 초과.
  - `502`: AWS AssumeRole 호출 실패 등 상위 오류.

## 7. AWS 상호작용 요약
- **STS AssumeRole**: 임시 세션 발급, `ExternalId`, `RoleSessionName`, `DurationSeconds=3600`.
- **CloudFormation**: 고객 계정에서 `workload-stack.yaml`을 배포/업데이트하며, SaaS는 세션 자격 증명을 사용.
- **S3 Presign**: 템플릿이 비공개일 때 `generate_presigned_url`을 사용.
- **EC2 CreateKeyPair**: 베스천 키 페어 생성 후 브라우저 다운로드 제공.
- **Redis**: 사용자/조직 레코드 저장, Idempotency/Rate limit/Nonce 관리.

이 명세는 `docs/1_proposal.md`, `docs/2_final-report.md`에 기술된 시스템 목표와 동일한 말투·구조를 유지하며, 실제 구현된 Django 비동기 뷰와 AWS 연계를 기준으로 작성되었다.

서버구축 및 운영 REST서비스 프로젝트 최종 보고서

## 1. 개발 주제 설명 – 왜, 어떻게?

AWS AssumeRole을 사용한 Cross-Account 리소스 제어라는 주제는 “왜 사용자의 루트 자격 증명을 받지 않고도 SaaS가 고객 계정 리소스를 안전하게 조작해야 하는가?”라는 질문에서 출발했다. 퍼블릭 클라우드 서비스를 제공하는 스타트업이 고객 계정에 직접 접근할 때 발생하는 가장 큰 문제는 Access Key · Secret Key 유출 위험이다. 영구 키가 한 번 새어나가면 공격자는 동일한 권한으로 모든 리소스를 삭제할 수 있기 때문에, SaaS 사업자는 고객에게 키를 요구하지 않으면서도 운영 효율을 담보할 수 있는 구조가 필요했다.

이를 해결하기 위해 “어떻게 수행할 것인가”는 AWS IAM의 Trusted Principal + AssumeRole 조합에서 찾았다. 고객이 제공한 CloudFormation 템플릿으로 SunrinPowerUser 역할을 배포하고, 서비스는 External ID로 보호된 STS AssumeRole API를 호출해 1시간짜리 세션을 발급받는다. 세션이 만료되면 권한도 즉시 사라지므로, 전체 시스템은 “임시 세션 → 자동화된 리소스 제어 → 로그 기록”이라는 폐쇄 루프로 운영된다. 또한 Redis 기반으로 등록 조직을 추적하고, AES-GCM/ PBKDF2로 보안 비밀을 암호화해 SaaS 운영 영역에서 평문 비밀이 남지 않도록 했다.

## 2. 주요 기능 및 REST API

### 2.1 사용자/조직 온보딩 API

- `POST /api/users`는 운영자를 위한 사용자 ID를 발급한다. Django 뷰는 Pydantic 모델로 입력을 검증하고, Redis에 shortuuid 기반 키를 저장한다. AWS 원리와 직접적으로 연결되지는 않지만, 이후 AssumeRole 요청마다 SessionName에 사용자 ID를 포함해 감사 추적성을 유지한다.
- `POST /api/register`는 조직 이름과 운영자 ID를 받아 API Key, External ID를 생성한다. External ID는 AWS STS에서 제공하는 “Third-party cross-account role assume 시 필수 조건”으로, 고객 계정의 역할 정책에서 `Condition: { "StringEquals": { "sts:ExternalId": "<value>" } }` 형태로 사용된다. Idempotency-Key 헤더를 검증해 중복 등록을 막고, AES-GCM으로 API Key/External ID를 암호화하여 Redis에 저장한다.

### 2.2 통합/검증 API

- `POST /api/integrate`는 CloudFormation 콘솔 링크와 CLI 스크립트를 돌려준다. 이 과정에서 StackService가 고객이 배포해야 하는 `workload-stack.yaml`의 Presigned URL을 준비한다. AWS 측 원리는 “고객 계정은 CloudFormation StackSet 또는 콘솔에서 SunrinPowerUser 역할을 생성한다 → 역할의 Trusted Principal로 서비스 계정을 지정한다”는 흐름이다.
- `POST /api/validate`는 고객이 발급받은 STS 자격 증명이 실제로 SunrinPowerUser 역할인지 확인한다. 프런트엔드에서 받은 Access Key, Secret Key, Session Token으로 임시 세션을 구성한 뒤 `sts:GetCallerIdentity`를 호출한다. 성공하면 “임시 세션이 올바르게 설정되었으며, AssumeRole 정책이 정상 적용됐다”는 것을 의미한다.

### 2.3 자격 증명 및 리소스 제어 API

- `POST /api/credentials`는 SaaS가 고객 계정 대신 임시 자격 증명을 발급해주는 핵심 엔드포인트다. Redis RateLimiter로 `credentials:<user>:<org>` 버킷을 제어해 남용을 막고, STSService가 `sts:AssumeRole`을 호출한다. AWS 측에서는 역할 ARN `arn:aws:iam::<account-id>:role/SunrinPowerUser`와 External ID를 검증하고, 성공 시 AccessKeyId/SecretAccessKey/SessionToken/Expiration을 되돌려준다. 응답에는 CloudFormation 콘솔 URL, 템플릿 URL, AWS CLI 명령도 포함되어 운영자가 즉시 리소스를 배포할 수 있다.
- `POST /api/integrations/validate`는 고객 계정에서 돌아가는 Lambda가 보낸 웹훅을 검증한다. Lambda는 CloudFormation 스택이 성공하면 계정 ID, 태그, External ID를 SaaS로 전송한다. SaaS는 HMAC-SHA256 서명과 재사용 방지를 위한 Redis nonce 체크로 요청을 검증하고, 조직 레코드에 `validation_status=True`와 계정 ID를 기록한다. 이 상태여야만 `POST /api/credentials`가 리소스를 배포할 수 있다.

### 2.4 포털 및 워크로드 자동화

웹 포털(루트 URL)은 Django 템플릿 기반으로 동작하며 다음 기능을 제공한다.

1. 사용자/조직 생성 폼: REST API를 직접 호출하는 대신 운영자가 브라우저에서 동일 절차를 따라갈 수 있도록 UI를 제공한다.
2. 키 페어 생성: STS 임시 세션으로 고객 계정의 EC2 API를 호출해 베스천 키 페어를 생성하고, PEM을 브라우저로 전달한다. AWS EC2 `CreateKeyPair` 호출은 AssumeRole 세션을 Credential Provider로 전달하여 실행된다.
3. Workload Stack 배포/삭제: Django 뷰는 boto3 CloudFormation 클라이언트를 사용한다. 먼저 `OrganisationService`로 검증 상태를 확인하고, 이후 `WorkloadStackService`가 `create_stack`, `update_stack`, `delete_stack`을 호출한다. STS에서 받은 Credentials를 SDK에 주입해 고객 계정 내에서 직접 스택 작업을 수행하며, IAM 권한은 SunrinPowerUser 역할에 정의된 최소 권한만 사용한다.

이러한 구성 덕분에 서비스의 모든 주요 기능이 REST API로 노출되고, 각 API는 AWS STS, IAM, CloudFormation, EC2 등 구체적인 관리형 서비스를 기반으로 작동한다. 곧바로 프로덕션에서 재사용할 수 있는 레퍼런스를 목적으로 했기에, Django 비동기 뷰 + Redis 레이어 + boto3 호출까지 한 번에 포함한 것이 특징이다.

## 3. 결론

프로젝트는 “왜?”에 해당하는 보안 우려를 해소하기 위해 “어떻게?”를 AWS의 원리에 그대로 맞춘 구조로 완성했다. CloudFormation이 신뢰 체인을 구축하고, STS AssumeRole이 임시 세션을 발급하며, REST API는 해당 세션을 관리·검증하고, Django 포털은 운영자가 안전하게 절차를 수행하도록 돕는다. 결과적으로 퍼블릭 클라우드 SaaS 스타트업이 고객 계정을 안전하게 제어할 수 있는 오픈소스 참고 자료를 제공한다는 초기 목표를 충실히 달성했다.

# Sunrin Managed IAM – Django Edition

## 📚 문서 바로가기

- [API 명세서](docs/0_api_docs.md)
- [프로젝트 제안서](docs/1_proposal.md)
- [최종 보고서](docs/2_final-report.md)
- [워크로드 배포 가이드](docs/3_deploy-workload.md)

이 디렉터리는 Sunrin Managed IAM 프로토타입을 Django로 구현한 버전을 담고 있습니다. 기존 FastAPI 서비스와 동일한 API 표면을 제공하면서도 암호화, Redis, AWS 연동 레이어를 그대로 재사용합니다.

- `POST /api/users` – Sunrin 운영자를 위한 `user_id`를 발급합니다.
- `POST /api/register` – 조직 레코드를 생성하고 조직별 API Key와 ExternalId를 발급합니다.
- `POST /api/integrate` – 템플릿과 검증 스택을 다시 배포할 수 있는 콘솔 링크와 AWS CLI 명령을 제공합니다.
- `POST /api/credentials` – CloudFormation 배포 상태가 검증된 뒤 STS 자격 증명을 중개합니다.
- `POST /api/validate` – 전달된 STS 자격 증명이 유효한지 확인합니다.
- `POST /api/integrations/validate` – 1회성 Lambda 스택이 보내는 검증 웹훅을 수신합니다.
- `GET /api/health` – 로드 밸런서에서 사용하는 경량 헬스 체크입니다.

서비스는 API Key/ExternalId를 AES-GCM으로 암호화하고, Redis 상태는 버전 키로 저장하며, 모든 검증 콜백은 HMAC 서명을 요구합니다. AssumeRole 세션 이름은 CloudTrail 추적을 위해 `Sunrin-{org_name}-{user_id}` 패턴을 사용합니다.

## 프로젝트 구조

```
.
├── cloudformation/             # S3에서 제공되는 CloudFormation 템플릿
├── managed_iam/                # API 전반에서 공유하는 도메인 로직
├── managed_iam_app/            # Django 뷰 + URL 라우팅
├── managed_iam_site/           # Django 프로젝트 설정
├── manage.py                   # Django 관리 진입점
└── pyproject.toml              # Poetry 설정 및 의존성 목록
```

## 필요 조건

- Python 3.12+
- Redis (로컬 또는 원격). 개발 환경에서는 `docker run -p 6379:6379 redis:7`로 실행 가능합니다.
- S3 프리사인 URL과 STS 역할 자격 증명을 생성할 수 있는 AWS 자격 증명(로컬 테스트에서 AWS 호출을 스텁 처리한다면 필수는 아님)

## 환경 변수

`.env.sample`을 `.env`로 복사한 뒤 플레이스홀더 값을 채워 넣습니다.

```bash
cp .env.sample .env
# 32바이트 base64 AES 키, HMAC 키, 버킷 이름 등을 지정하세요.
python - <<'PY'
import os, base64
print("SUNRIN_ENCRYPTION_KEY=", base64.b64encode(os.urandom(32)).decode())
print("SUNRIN_HMAC_KEY=", base64.b64encode(os.urandom(32)).decode())
PY
```

주요 설정(`SUNRIN_` 접두사 사용):

- `ENCRYPTION_KEY` – API Key 암호화에 사용하는 base64 인코딩 32바이트 AES-GCM 키.
- `HMAC_KEY` – 검증 웹훅 서명에 사용하는 base64 인코딩 32바이트 키.
- `TEMPLATE_BUCKET` / `TEMPLATE_KEY` – `cloudformation/stack.yaml`이 위치한 S3 경로.
- `AWS_REGION` – S3 프리사인 URL, STS 호출, CloudFormation 콘솔 링크에서 사용할 리전.
- `PROVIDER_ACCOUNT_ID` – Sunrin AWS 계정 ID(기본값 `628897991799`).
- `ENCRYPTION_KEY`, `HMAC_KEY`는 최소 32바이트를 디코딩해야 하며, AES는 128/192/256비트 키가 필요합니다.
- `DEFAULT_ASSUME_PROFILE` – (선택) Sunrin 역할을 Assume할 때 사용할 AWS CLI 프로파일. Django 서버 시작 전 `.env` 또는 환경 변수로 설정합니다. 요청별 `aws_profile`가 지정되면 해당 값이 우선합니다.

## 의존성 설치

```bash
poetry install
```

> **주의:** 설치 시 PyPI 네트워크 접근이 필요합니다. 외부 트래픽이 차단된 환경이라면 내부 미러를 사용하세요.

## 개발 서버 실행

```bash
poetry run python manage.py migrate      # 선택: Django 인증 DB 초기화
poetry run python manage.py runserver 0.0.0.0:8000
```

API는 `/api` 프리픽스 아래에 노출됩니다. 예를 들어 `POST http://localhost:8000/api/users`는 새 운영자 ID를 발급합니다.

또한 `python -m managed_iam`으로도 개발 서버를 실행할 수 있습니다.

### HTML 운영 포털

루트 경로(`/`)는 운영자를 위한 경량 HTML 콘솔을 제공합니다.

- `user_id` 발급 및 조직 등록을 UI에서 바로 진행.
- 고객 계정을 연결하기 위한 CloudFormation 콘솔 링크/CLI 스크립트 생성.
- 선택한 조직의 검증 상태, 계정 메타데이터, 워크로드 배포 현황을 조회.
- `cloudformation/workload-stack.yaml`에 정의된 참조 워크로드 스택을 UI에서 바로 배포/업데이트/삭제(고객 `SunrinPowerUser` 역할을 Assume하여 CloudFormation 호출).
- `user_id`, `org_name`, `api_key`를 입력하면 고객 계정에 EC2 키 페어를 생성하고 `.pem` 파일을 즉시 다운로드.

CLI로 워크로드를 배포하고 싶다면 `docs/deploy-workload.md`를 참고하세요.

## 엔드포인트 요약

| Method & Path                      | 설명                                                                     |
|-----------------------------------|--------------------------------------------------------------------------|
| `POST /api/users`                 | 새 `user_id`와 메타데이터를 발급.                                         |
| `POST /api/register?user_id=`     | 조직을 등록하고 API Key + ExternalId를 생성.                             |
| `POST /api/integrate?user_id=`    | 재배포용 콘솔 링크와 AWS CLI 명령 제공.                                   |
| `POST /api/credentials?user_id=`  | 검증이 완료된 고객 계정에서 Sunrin 역할 Assume 후 STS 자격 증명 발급.     |
| `POST /api/validate`              | 임의의 STS 자격 증명이 읽기 권한을 갖는지 확인.                           |
| `POST /api/integrations/validate` | 1회성 Lambda 스택이 호출하는 HMAC 보호 검증 웹훅.                         |
| `GET /api/health`                 | 경량 헬스 체크.                                                           |

인증이 필요한 엔드포인트는 쿼리 파라미터로 `user_id`가 필수입니다(JWT 지원 전까지 레이트 리밋 및 로깅을 권장). `POST /api/credentials`, `POST /api/validate`는 검증 Lambda가 조직을 승인하지 않으면 HTTP 412로 거부하며, 응답 본문에는 `/api/integrate`와 동일한 콘솔 링크/CLI 명령(`aws_profile` 포함 가능)이 포함됩니다.

## S3 CloudFormation 템플릿

CloudFormation 템플릿은 `cloudformation/stack.yaml`에 있습니다. `SUNRIN_TEMPLATE_BUCKET` / `SUNRIN_TEMPLATE_KEY`로 참조되는 파일을 업로드하여 API가 다운로드 링크를 생성할 수 있도록 하세요. 템플릿은 교차 계정 역할(`SunrinPowerUser`)을 배포하고 AWS 관리형 `PowerUserAccess` 정책을 부여하며, 배포 검증을 위한 nested stack도 실행합니다. AssumeRole 세션 지속시간은 3600초입니다.

### 고객 워크로드 스택

고객이 `SunrinPowerUser` 역할을 배포한 뒤에는 해당 역할을 Assume하여 `cloudformation/workload-stack.yaml`에 정의된 워크로드를 롤아웃할 수 있습니다. 이 스택은 VPC, 공용 2개/사설 2개 서브넷, 듀얼 NAT 게이트웨이, 베스천 인스턴스, ALB 앞단 WAS 오토스케일링 그룹, DynamoDB 테이블을 생성합니다. 세부 절차는 `docs/deploy-workload.md`를 참고하세요.

## 테스트 실행

pytest가 포함되어 있으며 Django 관련 테스트는 `tests/` 디렉터리에 추가하면 됩니다.

```bash
poetry run pytest
```

테스트는 fakeredis와 스텁된 AWS 클라이언트를 사용합니다. 네트워크 설치가 불가하다면 PyPI에 접근 가능한 환경에서 패키지를 설치한 뒤 wheel을 복사해 사용하세요.

## 검증 웹훅 HMAC

검증 Lambda는 복호화한 API Key를 HMAC 비밀로 사용해 요청을 서명해야 합니다.

```
signature = HMAC-SHA256(secret=api_key, message=f"{timestamp}|{nonce}|{body}")
headers:
  X-Sig-Signature: <hex digest>
  X-Sig-Timestamp: <unix epoch seconds>
  X-Sig-Nonce: <unique nonce>
```

`POST /api/integrations/validate`는 서명을 검증하고, 페이로드의 API Key가 저장된 값과 일치하는지 확인한 뒤 조직을 검증 완료 상태로 표시하여 STS 자격 증명 흐름을 열어줍니다.

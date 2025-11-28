서버구축 및 운영 REST서비스 프로젝트 계획서

## 서비스 제목(팀 이름)
AWS AssumeRole을 사용한 Cross-Account 리소스 제어

## 팀원(학번 이름)
20512 이주안, 20519 한유찬

## 프로젝트 개발 주제 선정

### 1.1 서비스 이름의 의미와 주제 설명
AWS AssumeRole을 사용한 Cross-Account 리소스 제어는 퍼블릭 클라우드 환경에서 다수의 사용자를 대상으로 서비스를 제공하는 SaaS 형태의 서비스가 사용자의 AWS 계정에 안전하게 접근하고 리소스를 관리할 수 있도록 하는 시스템을 의미한다. 일반적으로 퍼블릭 클라우드 스타트업의 SaaS가 사용자의 AWS 계정 내 리소스를 제어하기 위해서는 Access Key와 Secret Key를 직접 입력받아 사용하는 방식이 많이 사용되고 있다. 그러나 이러한 방식은 키가 유출될 경우, 사용자의 계정이 위험에 노출된다는 보안상의 문제를 가지고 있다.

본 프로젝트는 이러한 문제를 해결하기 위해 AWS IAM의 AssumeRole 기능을 사용할 예정이다. IAM Cross-Account AssumeRole은 서비스가 직접 사용자의 키를 보관하지 않고, 대신 사용자의 계정에 배포된 IAM Role을 Trusted Principal로 설정하여 Session Credential을 발급받는 구조로 작동한다. 결과적으로 퍼블릭 클라우드 기반의 서비스를 제공하는 스타트업이 안전하게 사용자의 AWS 계정을 제어할 수 있도록 하여 보안, 운영 효율성을 동시에 확보하는 시스템을 구현하는 것을 목표로 한다.

### 1.2 주제 선정 과정
다수의 클라우드 SaaS 스타트업이 사용자의 AWS 리소스에 직접 접근해 모니터링, 배포, 관리하는 등의 기능을 제공하고 있다. 그러나, 그러한 서비스의 대부분이 여전히 Root account의 Access Key, Secret Key 방식에 의존하고 있다. 두 키는 AWS에서 유출되지 않도록 가장 조심해야 하는 키이다. 심지어, AWS는 Root account의 ID, Password, TOTP Key를 종이에 출력하여 은행 금고에 보관하는 것을 Best Practice로 해두었을 정도로 Root account는 매우 중요하다. 그러나, 이러한 키가 유출된다면 보안 상의 사고가 발생할 수 있으며, 데이터 유출 등의 가능성이 발생할 수 있다.

본 프로젝트에서는 이러한 문제를 해결하기 위해 AWS의 Best Practice 중 하나인 AssumeRole 기반의 Cross-Account 접근 방식을 채택하였다. 이 방식은 키 유출 위험이 적고, 설령 키가 유출된다 하더라도 짧은 시간 내에 만료되므로 안전하다. 또한 Datadog, Snowflake, Lacework 등 글로벌한 퍼블릭 클라우드 SaaS 기업들이 이미 동일한 구조를 적용하여 안정적인 서비스를 운영하고 있으나, 관련된 상세한 기술 자료나 오픈소스로 구현한 코드가 오래되거나, Go 언어 등 스타트업에서 주로 사용하는 언어로 개발된 경우, 보안적으로 안전하게 접근할 수 있도록 구현된 사례가 많지 않아 실무에 적용하기 위해서는 보안 측면에서 추가적인 연구가 필요한 실정이다.

따라서 퍼블릭 클라우드 SaaS 스타트업들이 자사 서비스에 쉽게 적용할 수 있는 오픈소스 레퍼런스를 제공하기 위해 본 주제를 선정하였다. 이를 통해, 스타트업의 서비스들이 보다 안전한 방식으로 사용자의 클라우드 계정에 접근할 수 있도록 돕고자 한다.

### 1.3 관련 서비스 조사
#### 1.3.1 DatadogHQ
DatadogHQ는 Multi-Account 환경에서 고객 계정 내 IAM Role을 생성하고 External ID 조건을 부여한 후, Datadog 측 계정이 해당 Role을 Assume하여 메트릭 및 로그를 수집하는 Cross-Account 시스템을 다년간 운용 중에 있다. Datadog 공식 가이드에는 “고객 계정에 IAM 정책/Role 생성 → Datadog에서 발급한 External ID 연계 → Datadog가 고객 계정 API를 쿼리” 절차가 명시되어 있고, AWS Organizations를 사용하는 조직을 대상으로 하는 CloudFormation StackSet을 통한 대규모 배포 방법 또한 제공하고 있다. 이를 통해 DatadogHQ는 Access, Secrets Key를 수동으로 배포하지 않고 임시 세션을 발급받아 접근할 수 있도록 하였다.

Fig 1. DatadogHQ 대시보드에서 Single AWS Account를 연동하는 화면
위 사진의 스택 생성 버튼을 클릭할 경우 자동으로 Datadog이 고객의 AWS Account에 접근할 수 있게 된다.

대표적인 OSS 사례로는 uzusan/aws-crossaccount-example이 Python과 STS API를 이용해 계정 A의 주체가 계정 B의 Role을 Assume하여 리소스에 접근하는 예제를 구현하였다. 그러나, 이는 AssumeRole의 구조 이해와 PoC 단계에만 적합하고, 운영 단계에서의 암호화, 권한 최소화 등이 필요하다는 단점이 있다.

### 1.4 서비스 개발 목표
본 프로젝트는 퍼블릭 클라우드 기반 SaaS 스타트업이 사용자의 AWS 계정을 안전하게 제어할 수 있는가라는 질문에서 출발하였다. 상용 서비스들이 채택한 AssumeRole + External ID 접근 제어 방식을 스타트업이 부담 없이 재현하고 자사 서비스에 적용할 수 있도록 개발하는 것이 1차적인 목표이다. 이를 위해 boto3만으로 VPC, EC2, RDS를 프로비저닝하는 기능을 개발하여 실 서비스 적용이 가능함을 증명하고, Session Credential 기반 Cross-Account 리소스 제어가 가능함을 증명할 계획이다. 결과적으로, (1) 영구적인 Access, Secrets 키 없이 임시 세션으로 사용자 계정을 제어하고, (2) 중요 키를 평문으로 저장하지 않아 유출 위험을 낮추고, (3) boto3을 사용하여 리소스 배포를 자동화한다. 결과적으로 퍼블릭 클라우드 SaaS를 제공하는 스타트업이 보안과 운영 효율성을 동시에 확보할 수 있는 OSS를 구현하고 공개할 것이다.

## 활동 개요

### 2.1 개발 목적
여러 클라우드 기반 SaaS를 개발하는 스타트업의 경우, 사용자의 AWS 계정에 접근하기 위한 방법으로, Access, Secrets 키를 직접 서비스에 입력하도록 하고 있다. 이는 매우 위험한 방법으로, 보안 측면에서의 문제가 발생할 가능성이 농후한 방법이다.

이러한 문제를 해결하기 위해서는, 영구적인 키를 사용하는 것이 아닌 임시적인 세션 키를 사용하여야 한다. 그러나, AWS에서는 수동으로 세션 데이터를 생성하는 방법을 지원하고 있지 않을 뿐더러, 리소스를 배포할 때마다 사용자가 세션 데이터를 업데이트 해주는 것은 UX적인 측면에서도 상당히 좋지 않다.

그렇다면, 세션 키를 어떻게 자동으로 발급하고, 사용할 수 있을까? 답은 IAM에 있다. IAM Role은 단순 권한의 그룹, 유저 역할 부여의 기능만 있는 것이 아닌, 신뢰 주체(Trusted Principal)이라는 기능이 있다. IAM Role의 Trusted Principal은 다른 AWS Account의 ID(12자리)를 지정할 수 있다. 만약 156041424727이라는 Account의 IAM Role이 628897991799라는 계정을 Trusted Principal로 지정한다면, 628897991799 계정은 156041424727 계정의 IAM Role에 접근할 수 있게 된다. 그 후, AssumeRole을 통해 세션을 발급받을 수 있다. 이 과정을 자동화하면, 사용자도 불편하지 않고, 안전하게 End user 계정에 접근할 수 있다.

DatadogHQ 등 전문적인 퍼블릭 클라우드 SaaS를 제공하는 기업들은 해당 기법을 이미 사용하고 있지만, 오픈소스로 공개하지 않아 퍼블릭 클라우드 SaaS 스타트업의 부담은 늘어나고 있다. 본 프로젝트를 구현한 후 OSS Team을 통해 오픈소스로 공개하여 퍼블릭 클라우드 SaaS 스타트업 서비스들의 개발 부담을 줄이고, 사용자들이 안전한 퍼블릭 클라우드 SaaS를 이용할 수 있도록 할 것이다.

### 2.2 개발 내용 및 방법
본 프로젝트에서는 아래 3가지 사항을 가장 주로 하여 개발할 계획이다.

1. **서버에서 사용자의 계정에 안전하게 접근**: 사용자 계정에 접근하는 방법에는 여러 가지 방법이 있다. 사용자 계정에서 발급한 Access, Secrets key 사용. 사용자 AWS 계정 내에 배포된 AWS 리소스 내에서 IAM Role을 자격 증명으로 사용. 외부 AWS Account를 Trusted Principal로 하는 IAM Role 생성 후 Assume하여 세션 발급. 첫 번째 방법의 경우, 영구적인 토큰을 사용해야 하는데, 이는 키가 유출될 경우 해커가 자유롭게 사용이 가능하다는 단점이 있다. 또한, 이는 AWS에서 공식적으로 지양하라고 권장되는 방법이다. 두 번째 방법의 경우, End user account에 인스턴스 또는 Lambda 함수를 통해 REST API 서버를 배포한 후, 해당 API를 호출해서 리소스를 배포할 수 있다. 이 방법은 End user의 작업이 필요하고, 사용자가 클라우드에 관련된 지식이 없을 경우 작업에 어려움이 크다는 단점이 있다. 위의 이유들로 인해 서비스에서 사용하는 AWS Account를 Trusted Principal로 하는 IAM Role을 Cloudformation을 사용하여 배포한 후, 해당 Role을 Assume하여 Session을 발급받는 방법을 사용한다. 또한, 이 방법이 보안적인 측면에서도 안전하므로 AWS에서도 공식적으로 권장하고 있다. Cloudformation을 사용하여 스택을 배포할 때는, AWS 계정에 로그인한 후, 서비스에서 제공한 URL에 접속하여 클릭 한번만 하면 끝나기 때문에 사용자 입장에서도 어렵지 않게 AWS 계정에 접근을 허용할 수 있다.

2. **사용자의 Api key, External Id를 안전하게 암호화**: Api key와 External Id는 유출될 경우 Role assume, 서비스 접근 상에서 보안적인 문제가 발생할 수 있으므로, 절대로 평문으로 저장하지 않는다. 모든 데이터는 AES-GCM 암호화 기법을 통해 대칭키 암호화되어 저장되며, 암호화 과정에서 생성된 nonce와 ciphertext를 같이 저장한다. AES-GCM 기법은 무결성과 인증이 보장되므로 데이터 조작, 위변조를 방지할 수 있다. 평문 비교가 필요한 Api key는 PBKDF2 해시 기법을 사용하여 검증하고, 복호화 없이 일치 여부를 판단한다. 외부 통신 시에는 HMAC 서명 검증 기법을 사용하여 각 통신 데이터의 신뢰성을 확보하였다.

3. **사용자의 AWS 계정에 리소스를 배포**: 사용자의 계정에 리소스를 배포할 때는 AWS SDK for Python인 boto3을 사용한다. boto3 배포 시 서비스 계정의 IAM Role based Credential을 사용하면 위험하므로, 반드시 사용자의 계정에 생성된 IAM Role에 Assume하여 세션을 발급한 후, 해당 세션의 Credential을 사용하여 리소스를 배포한다.

### 2.3 서비스 개발 일정 (11월 30일 제출 마감을 기준으로 계획)

| 연번 | 해야할 일 | 10월 5w | 11월 1w | 11월 2w | 11월 3w | 11월 4w |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 아이디어 구상 및 팀 빌딩 |  |  |  |  |  |
| 2 | 기획서 작성 |  |  |  |  |  |
| 3 | Cloudformation Stack 작성 |  |  |  |  |  |
| 4 | Boto3을 사용한 AssumeRole 시스템 구축 |  |  |  |  |  |
| 5 | AssumeRole을 통한 세션 발급 후, 리소스 제어 파트 개발 |  |  |  |  |  |

### 2.4 팀원별 역할 분담 및 역할별 활동 계획
- **팀장 : 이주안**
  - User account AssumeRole을 위한 Cloudformation Stack 작성.
  - Cloudformation Stack deployment validation을 위한 Lambda 코드 및 API 개발
  - Boto3을 사용한 AssumeRole 파트 구현.
  - Api key, External Id 보안을 위한 HMAC, 해시 알고리즘 구현
  - 요청이 여러 번 입력되었을 경우, 이를 1번만 처리하도록 하기 위한 Idempotency-key 도입 및 적용

- **팀원 : 한유찬**
  - Organization, User 파트 API 개발
  - 사용자 계정 Assume 후 AWS STS API 접근 파트 개발
  - Boto3 사용한 end user account에 VPC, EC2 리소스 배포 파트 개발

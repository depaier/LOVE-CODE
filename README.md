# 사주 매칭 서비스

사주와 MBTI를 기반으로 한 연애 매칭 서비스입니다.

## 설치 및 설정

### 1. 환경 준비

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는 venv\Scripts\activate  # Windows

# 패키지 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 환경변수들을 설정하세요:

```bash
# Flask 설정
FLASK_SECRET_KEY=your-secret-key-here-change-this-in-production
FLASK_ENV=development

# Supabase 설정
SUPABASE_URL=your-supabase-url-here
SUPABASE_ANON_KEY=your-supabase-anon-key-here

# Google AI API 키
GOOGLE_API_KEY=your-google-api-key-here

# Web Push VAPID 키 (푸시 알림용)
VAPID_PRIVATE_KEY=your-vapid-private-key-here
VAPID_PUBLIC_KEY=your-vapid-public-key-here
VAPID_EMAIL=your-email@example.com

# 앱 URL (푸시 알림에서 사용)
APP_URL=https://your-app-domain.com
```

### 3. Google AI API 키 발급

1. [Google AI Studio](https://makersuite.google.com/app/apikey) 에 접속
2. 새 API 키 발급
3. `.env` 파일의 `GOOGLE_API_KEY` 값 변경

### 4. VAPID 키 생성 (푸시 알림용)

푸시 알림을 위해 VAPID 키 쌍을 생성해야 합니다:

```bash
# 가상환경 활성화
source venv/bin/activate  # Linux/Mac
# 또는 venv\Scripts\activate  # Windows

# Python에서 VAPID 키 생성 (cryptography 라이브러리 사용)
python3 -c "
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
import base64

# ECDSA P-256 키 쌍 생성 (VAPID 표준)
private_key = ec.generate_private_key(ec.SECP256R1())

# 개인 키를 PEM 형식으로 직렬화
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# 공개 키를 DER 형식으로 직렬화 후 base64url 인코딩
public_key_der = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)

# VAPID용 base64url 인코딩
private_b64 = base64.urlsafe_b64encode(private_pem).decode('utf-8').rstrip('=')
public_b64 = base64.urlsafe_b64encode(public_key_der).decode('utf-8').rstrip('=')

print('VAPID_PRIVATE_KEY=' + private_b64)
print('VAPID_PUBLIC_KEY=' + public_b64)
print('')
print('✅ 올바른 ECDSA P-256 키 쌍이 생성되었습니다!')
"
```

생성된 키들을 `.env` 파일에 설정하세요.

### 5. 데이터베이스 초기화

```bash
python init_db.py
```

### 6. 실행

```bash
python api/index.py
```

### 7. iOS Safari 푸시 알림 설정

iOS Safari에서 푸시 알림을 사용하려면:

1. **iOS 버전 확인**: iOS 16.4 이상이 필요합니다
2. **Safari 권한 설정**:
   - Safari 앱에서 설정 > 개인정보 보호 및 보안 > 알림
   - Safari 토글을 켜세요
3. **웹사이트 권한**:
   - Safari에서 웹사이트 접속
   - 공유 버튼(□) > 알림 권한 요청 허용
4. **알림 수신 확인**:
   - 앱이 백그라운드에 있어도 알림이 도착합니다
   - 알림을 탭하면 자동으로 웹사이트가 열립니다

**주의사항**:

- iOS Safari에서는 HTTPS 연결이 필수적입니다
- 푸시 알림은 Wi-Fi 연결에서 더 안정적입니다
- 알림이 도착하지 않으면 Safari를 완전히 종료하고 다시 시작해보세요

## 보안 주의사항

- `.env` 파일은 Git에 절대 커밋하지 마세요
- API 키는 외부에 노출되지 않도록 주의하세요
- 프로덕션에서는 `FLASK_SECRET_KEY`를 강력한 키로 변경하세요

## 주요 기능

- 사주 계산 및 분석
- MBTI 기반 성격 분석
- AI 기반 매칭 추천
- 푸시 알림 시스템
- 매칭 결과 조회 및 인스타그램 프로필 연동
- 관리자 패널

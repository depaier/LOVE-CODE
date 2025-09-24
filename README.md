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

```bash
# .env 파일 복사
cp .env.example .env

# .env 파일을 열어서 실제 API 키로 변경
nano .env  # 또는 원하는 에디터
```

### 3. Google AI API 키 발급

1. [Google AI Studio](https://makersuite.google.com/app/apikey) 에 접속
2. 새 API 키 발급
3. `.env` 파일의 `GOOGLE_API_KEY` 값 변경

### 4. 데이터베이스 초기화

```bash
python init_db.py
```

### 5. 실행

```bash
python app.py
```

## 보안 주의사항

- `.env` 파일은 Git에 절대 커밋하지 마세요
- API 키는 외부에 노출되지 않도록 주의하세요
- 프로덕션에서는 `FLASK_SECRET_KEY`를 강력한 키로 변경하세요

## 주요 기능

- 사주 계산 및 분석
- MBTI 기반 성격 분석
- AI 기반 매칭 추천
- 관리자 패널

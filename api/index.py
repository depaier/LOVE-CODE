from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import google.generativeai as genai
from supabase import create_client, Client
from dotenv import load_dotenv
import os

# 환경변수 로딩
load_dotenv()

# --- [사주 계산 함수 부분 - 이전과 동일] ---
def calculate_saju_pillars(year, month, day, hour):
    cheon_gan = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
    ji_ji = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]
    year_gan_index = (year - 4) % 10; year_ji_index = (year - 4) % 12
    year_pillar = cheon_gan[year_gan_index] + ji_ji[year_ji_index]
    month_starts = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
    gan_starts = ["병", "정", "무", "기", "경", "신", "임", "계", "갑", "을"]
    ji_starts = ["인", "묘", "진", "사", "오", "미", "신", "유", "술", "해", "자", "축"]
    month_index = month_starts.index(month)
    month_gan_key = cheon_gan[year_gan_index]
    if month_gan_key in ["갑", "기"]: gan_offset = 0
    elif month_gan_key in ["을", "경"]: gan_offset = 2
    elif month_gan_key in ["병", "신"]: gan_offset = 4
    elif month_gan_key in ["정", "임"]: gan_offset = 6
    else: gan_offset = 8
    month_gan_index = (gan_offset + month_index) % 10
    month_pillar = gan_starts[month_gan_index] + ji_starts[month_index]
    total_days = 0
    for y in range(1, year): total_days += 366 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 365
    days_in_month = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0: days_in_month[2] = 29
    for m in range(1, month): total_days += days_in_month[m]
    total_days += day
    day_gan_index = (total_days + 6) % 10; day_ji_index = (total_days + 8) % 12
    day_pillar = cheon_gan[day_gan_index] + ji_ji[day_ji_index]
    time_ji_map = {23:0, 0:0, 1:1, 2:1, 3:2, 4:2, 5:3, 6:3, 7:4, 8:4, 9:5, 10:5, 11:6, 12:6, 13:7, 14:7, 15:8, 16:8, 17:9, 18:9, 19:10, 20:10, 21:11, 22:11}
    time_ji_index = time_ji_map[hour]
    day_gan_key = cheon_gan[day_gan_index]
    if day_gan_key in ["갑", "기"]: gan_offset = 0
    elif day_gan_key in ["을", "경"]: gan_offset = 2
    elif day_gan_key in ["병", "신"]: gan_offset = 4
    elif day_gan_key in ["정", "임"]: gan_offset = 6
    else: gan_offset = 8
    time_gan_index = (gan_offset + time_ji_index) % 10
    time_pillar = cheon_gan[time_gan_index] + ji_ji[time_ji_index]
    return year_pillar, month_pillar, day_pillar, time_pillar
# --- [사주 계산 함수 부분 끝] ---

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here-change-this-in-production')

# Supabase 연결 설정
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')

print(f"🔧 환경변수 확인:")
print(f"   SUPABASE_URL: {'설정됨' if SUPABASE_URL else '없음'}")
print(f"   SUPABASE_ANON_KEY: {'설정됨' if SUPABASE_ANON_KEY else '없음'}")
print(f"   GOOGLE_API_KEY: {'설정됨' if os.getenv('GOOGLE_API_KEY') else '없음'}")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_URL과 SUPABASE_ANON_KEY 환경변수가 설정되지 않았습니다.")

# Supabase 클라이언트 생성
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    print("✅ Supabase 클라이언트 생성 성공")
except Exception as e:
    print(f"❌ Supabase 클라이언트 생성 실패: {e}")
    raise

def init_supabase_tables():
    """Supabase 테이블 초기화 (SQL 에디터에서 수동으로 실행)"""
    print("📝 Supabase SQL 에디터에서 다음 쿼리들을 실행하세요:")
    print("""
-- results 테이블 생성
CREATE TABLE IF NOT EXISTS results (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    mbti TEXT NOT NULL,
    instagram_id TEXT NOT NULL,
    saju_result TEXT NOT NULL,
    ai_analysis TEXT NOT NULL,
    is_matched BOOLEAN DEFAULT FALSE,
    gender TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- matches 테이블 생성
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    user1_id INTEGER NOT NULL REFERENCES results(id) ON DELETE CASCADE,
    user2_id INTEGER NOT NULL REFERENCES results(id) ON DELETE CASCADE,
    compatibility_score INTEGER NOT NULL,
    matching_reason TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user1_id, user2_id)
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_results_student_id ON results(student_id);
CREATE INDEX IF NOT EXISTS idx_results_is_matched ON results(is_matched);
CREATE INDEX IF NOT EXISTS idx_matches_user1_id ON matches(user1_id);
CREATE INDEX IF NOT EXISTS idx_matches_user2_id ON matches(user2_id);
CREATE INDEX IF NOT EXISTS idx_matches_score ON matches(compatibility_score DESC);

-- 시퀀스 재설정 (중복 ID 문제 해결)
SELECT setval('results_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM results), false);
SELECT setval('matches_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM matches), false);
    """)
    print("✅ Supabase 테이블 생성 및 시퀀스 재설정 쿼리가 출력되었습니다.")

# Gemini API 키 설정
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

if GOOGLE_API_KEY == 'YOUR_NEW_API_KEY_HERE' or not GOOGLE_API_KEY:
    print("⚠️  GOOGLE_API_KEY가 설정되지 않았습니다.")
    print("   🔑 Google AI Studio에서 새 API 키를 발급받으세요:")
    print("      https://makersuite.google.com/app/apikey")
    print("   📝 발급받은 키를 아래 방법 중 하나로 설정하세요:")
    print("      1. 환경변수: export GOOGLE_API_KEY='your-api-key'")
    print("      2. 코드에서: GOOGLE_API_KEY = 'your-api-key'")
    GOOGLE_API_KEY = None

# Supabase 테이블 초기화 안내 (실제 초기화는 Supabase 대시보드에서 수동으로 실행)
print("🚀 Supabase 데이터베이스 설정:")
init_supabase_tables()

if GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        print("✅ Google AI API 설정 완료")
    except Exception as e:
        print(f"❌ Google AI API 설정 실패: {e}")
        GOOGLE_API_KEY = None

# API 키 유효성 확인 함수
def test_api_key():
    if not GOOGLE_API_KEY:
        return False, "API 키가 설정되지 않았습니다."

    try:
        # 간단한 모델 리스트로 API 키 테스트
        models = list(genai.list_models())
        return True, f"API 키 유효. {len(models)}개 모델 사용 가능."
    except Exception as e:
        return False, f"API 키 오류: {str(e)}"

# 모델 사용 가능 여부 확인 함수
def test_model(model_name):
    if not GOOGLE_API_KEY:
        return False, "API 키가 설정되지 않았습니다."

    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content('테스트')
        return True, "모델 정상 작동"
    except Exception as e:
        return False, f"모델 오류: {str(e)}"

# 사용 가능한 모델 목록 확인 함수
def get_available_models():
    if not GOOGLE_API_KEY:
        return []

    try:
        models = list(genai.list_models())
        generative_models = []
        for model in models:
            if hasattr(model, 'supported_generation_methods') and 'generateContent' in model.supported_generation_methods:
                generative_models.append(model.name)
        return generative_models
    except Exception as e:
        return []

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"❌ 메인 페이지 렌더링 오류: {e}")
        import traceback
        print("상세 에러:")
        print(traceback.format_exc())
        return f"서버 오류가 발생했습니다: {str(e)}", 500

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        # 로그인 처리
        student_id = request.form.get('student_id')
        password = request.form.get('password')

        # 학번과 비밀번호 확인
        if student_id == '202100672' and password == '정연웅1!':
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('admin_login.html', error='학번 또는 비밀번호가 올바르지 않습니다.')

    # GET 요청 처리 - 로그인 상태 확인
    if not session.get('logged_in'):
        return render_template('admin_login.html')

    # 로그인된 상태 - 관리자 페이지 표시
    try:
        # Supabase에서 데이터 조회
        response = supabase.table('results').select('*').order('created_at', desc=True).execute()
        results = response.data

        return render_template('admin.html', results=results)
    except Exception as e:
        return f"관리자 페이지 로딩 중 오류 발생: {e}"

@app.route('/admin/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin'))

@app.route('/admin/api-test')
def api_test():
    if not session.get('logged_in'):
        return jsonify({'error': '로그인이 필요합니다'}), 401

    try:
        # API 키 테스트
        api_valid, api_message = test_api_key()

        # 사용 가능한 모델 목록
        available_models = get_available_models()

        # 모델 테스트
        model_results = {}
        test_models = ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-pro']
        for model_name in test_models:
            model_valid, model_message = test_model(model_name)
            model_results[model_name] = {
                'valid': model_valid,
                'message': model_message
            }

        return jsonify({
            'api_key': {
                'valid': api_valid,
                'message': api_message
            },
            'available_models': available_models,
            'models': model_results
        })

    except Exception as e:
        return jsonify({'error': f'API 테스트 중 오류 발생: {e}'}), 500

@app.route('/admin/result/<int:result_id>')
def get_result_detail(result_id):
    if not session.get('logged_in'):
        return jsonify({'error': '로그인이 필요합니다'}), 401

    try:
        # Supabase에서 특정 결과 조회
        response = supabase.table('results').select('*').eq('id', result_id).execute()
        result = response.data

        if result and len(result) > 0:
            return jsonify(result[0])
        else:
            return jsonify({'error': '결과를 찾을 수 없습니다'}), 404
    except Exception as e:
        return jsonify({'error': f'데이터 조회 중 오류 발생: {e}'}), 500

@app.route('/admin/result/<int:result_id>', methods=['DELETE'])
def delete_result(result_id):
    if not session.get('logged_in'):
        return jsonify({'error': '로그인이 필요합니다'}), 401

    try:
        # Supabase에서 데이터 삭제
        response = supabase.table('results').delete().eq('id', result_id).execute()
        deleted_count = len(response.data)

        if deleted_count > 0:
            return jsonify({'message': '결과가 성공적으로 삭제되었습니다'})
        else:
            return jsonify({'error': '삭제할 결과를 찾을 수 없습니다'}), 404
    except Exception as e:
        return jsonify({'error': f'삭제 중 오류 발생: {e}'}), 500

@app.route('/admin/matching', methods=['POST'])
def perform_matching():
    # 로컬 개발 환경에서 세션 체크 우회 (디버깅용)
    import os
    if os.getenv('FLASK_ENV') == 'development':
        print("🔧 개발 환경에서 세션 체크 우회")
    elif not session.get('logged_in'):
        return jsonify({'error': '로그인이 필요합니다'}), 401

    try:
        # Supabase에서 데이터 조회
        print("🔍 Supabase에서 사용자 데이터 조회 중...")
        try:
            # 새로운 사용자들 (is_matched = FALSE)
            print("   📡 새로운 사용자 조회 시도...")
            new_users_response = supabase.table('results').select('id, name, mbti, saju_result, ai_analysis, gender').eq('is_matched', False).execute()
            new_users = new_users_response.data if new_users_response.data else []
            print(f"✅ 새로운 사용자 {len(new_users)}명 조회 완료")
        except Exception as db_error:
            print(f"❌ 새로운 사용자 조회 실패: {db_error}")
            raise Exception(f"새로운 사용자 데이터 조회 실패: {db_error}")

        try:
            # 기존 매칭된 사용자들 (is_matched = TRUE)
            print("   📡 기존 매칭된 사용자 조회 시도...")
            existing_users_response = supabase.table('results').select('id, name, mbti, saju_result, ai_analysis, gender').eq('is_matched', True).execute()
            existing_users = existing_users_response.data if existing_users_response.data else []
            print(f"✅ 기존 매칭된 사용자 {len(existing_users)}명 조회 완료")
        except Exception as db_error:
            print(f"❌ 기존 사용자 조회 실패: {db_error}")
            raise Exception(f"기존 사용자 데이터 조회 실패: {db_error}")

        if len(new_users) == 0:
            return jsonify({'error': '매칭할 새로운 사용자가 없습니다'}), 400

        if len(existing_users) == 0 and len(new_users) < 2:
            return jsonify({'error': '매칭을 위해 최소 2명의 사용자가 필요합니다'}), 400

        # Vercel 타임아웃 방지를 위한 사용자 수 제한
        total_users = len(new_users) + len(existing_users)
        if total_users > 20:
            return jsonify({'error': f'한 번에 너무 많은 사용자를 처리할 수 없습니다. 현재 {total_users}명, 최대 20명까지 가능합니다.'}), 400

        print(f"📊 매칭 대상: 새로운 사용자 {len(new_users)}명, 기존 사용자 {len(existing_users)}명 (총 {total_users}명)")

        # 성별에 따라 사용자들을 분류
        def classify_users_by_gender(users):
            males = []
            females = []
            for i, user in enumerate(users):
                # Supabase에서 반환되는 데이터는 딕셔너리 형태
                if not isinstance(user, dict):
                    print(f"⚠️ 사용자 {i}번 데이터가 딕셔너리가 아닙니다. 타입: {type(user)}, 데이터: {user}")
                    continue

                # 필수 필드 확인
                if 'gender' not in user:
                    print(f"⚠️ 사용자 {i}번 데이터에 gender 필드가 없습니다. 데이터: {user}")
                    continue

                gender = user.get('gender', '').strip()
                if gender == 'MALE':
                    males.append(user)
                elif gender == 'FEMALE':
                    females.append(user)
                else:
                    # 성별이 지정되지 않은 경우 기본적으로 남자로 취급
                    print(f"ℹ️ 사용자 {i}번 성별 미지정 (기본: 남자), 데이터: {user}")
                    males.append(user)
            return males, females

        print("👥 사용자 성별 분류 중...")
        # 새로운 사용자들을 성별로 분류
        new_males, new_females = classify_users_by_gender(new_users)
        print(f"✅ 새로운 사용자 - 남자: {len(new_males)}명, 여자: {len(new_females)}명")

        # 기존 사용자들을 성별로 분류
        existing_males, existing_females = classify_users_by_gender(existing_users)
        print(f"✅ 기존 사용자 - 남자: {len(existing_males)}명, 여자: {len(existing_females)}명")

        # 데이터 구조 검증
        print("🔍 데이터 구조 검증 중...")
        for i, user in enumerate(new_users + existing_users):
            print(f"사용자 {i} 데이터: 타입={type(user)}, 길이={len(user) if hasattr(user, '__len__') else 'N/A'}, 내용={user}")
            if not isinstance(user, (list, tuple)) or len(user) < 6:
                print(f"⚠️ 사용자 {i} 데이터 구조 이상: {user}")
                return jsonify({'error': f'사용자 데이터 구조가 올바르지 않습니다. 사용자 {i}: {user}'}), 500

        matches = []
        all_pair_scores = []  # 모든 쌍의 호환성 점수를 저장

        # AI를 사용한 매칭 수행
        print("🤖 AI 매칭 분석 시작...")
        # API 키 확인
        if not GOOGLE_API_KEY:
            return jsonify({'error': 'Google AI API 키가 설정되지 않아 매칭을 수행할 수 없습니다. 관리자에게 문의해주세요.'}), 500

        # Vercel 환경 최적화: 간단한 모델만 사용
        model_names = ['gemini-1.5-flash', 'gemini-1.5-pro']  # 2.0-flash 제외 (더 안정적임)
        model = None
        for model_name in model_names:
            try:
                print(f"🔄 {model_name} 모델 테스트 중...")
                model = genai.GenerativeModel(model_name)
                # 간단한 테스트로만 확인 (Vercel 타임아웃 방지)
                print(f"✅ {model_name} 모델 선택됨")
                break
            except Exception as e:
                print(f"❌ {model_name} 모델 실패: {e}")
                continue

        if model is None:
            return jsonify({'error': '사용 가능한 AI 모델을 찾을 수 없습니다. API 키와 모델 설정을 확인해주세요.'}), 500

        # 1. 성별 기반 매칭 분석 수행
        print("💑 매칭 분석 시작...")
        # 새로운 남자 × 기존 여자 매칭
        print(f"👫 새로운 남자({len(new_males)}명) × 기존 여자({len(existing_females)}명) 매칭 분석 중...")
        for user1 in new_males:
            for user2 in existing_females:
                try:
                    # AI에게 호환성 분석 요청
                    prompt = f"""
                    두 사람의 사주와 MBTI 정보를 바탕으로 연애/커플 매칭 호환성을 분석해주세요.

                    [사용자 1]
                    이름: {user1['name']}
                    MBTI: {user1['mbti']}
                    사주: {user1['saju_result']}
                    AI 분석: {user1['ai_analysis']}

                    [사용자 2]
                    이름: {user2['name']}
                    MBTI: {user2['mbti']}
                    사주: {user2['saju_result']}
                    AI 분석: {user2['ai_analysis']}

                    다음 형식으로만 응답해주세요:
                    호환성 점수: [1-100 사이의 숫자]
                    매칭 이유: [호환성 분석 및 이유 설명]
                    """

                    print(f"🤖 AI 호출 시도: {user1['name']} ↔ {user2['name']}")
                    print(f"📝 Prompt 길이: {len(prompt)} 문자")

                    # Vercel 환경용 타임아웃 설정 및 재시도 로직
                    max_retries = 2
                    retry_delay = 1

                    response = None
                    for attempt in range(max_retries + 1):
                        try:
                            if attempt > 0:
                                print(f"🔄 재시도 {attempt}/{max_retries}...")
                                import time
                                time.sleep(retry_delay)

                            # 타임아웃 설정 (Vercel용으로 짧게)
                            import google.generativeai as genai
                            response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(
                                temperature=0.7,
                                max_output_tokens=500,  # 응답 길이 제한
                            ))
                            break  # 성공하면 루프 탈출

                        except Exception as retry_error:
                            print(f"❌ AI 호출 시도 {attempt + 1} 실패: {retry_error}")
                            if attempt == max_retries:
                                raise Exception(f"AI API 호출 실패 (최대 재시도 횟수 초과): {retry_error}")
                            continue

                    # 응답이 None인지 확인
                    if response is None:
                        raise Exception("AI 응답이 None입니다")

                    ai_result = response.text.strip() if response.text else ""

                    # AI 응답이 비어있는지 확인
                    if not ai_result:
                        raise Exception("AI 응답이 비어있습니다")

                    print(f"✅ AI 응답 받음: 길이 {len(ai_result)} 문자")

                    # HTML 응답인지 확인 (에러 페이지가 반환된 경우)
                    if ai_result.startswith('<!DOCTYPE') or '<html' in ai_result.lower():
                        raise Exception(f"HTML 에러 페이지가 반환되었습니다. API 키나 모델 설정을 확인해주세요. 응답 내용: {ai_result[:200]}...")

                    # AI 응답 파싱
                    lines = ai_result.split('\n')
                    compatibility_score = 50  # 기본값
                    matching_reason = ai_result  # 기본값으로 전체 응답 저장

                    # 더 정확한 파싱을 위해 여러 패턴 시도
                    reason_found = False

                    for line in lines:
                        line = line.strip()
                        if '호환성 점수:' in line:
                            try:
                                score_text = line.split('호환성 점수:')[1].strip()
                                # 숫자만 추출 (더욱 강건하게)
                                import re
                                score_match = re.search(r'\d+', score_text)
                                if score_match:
                                    compatibility_score = int(score_match.group())
                                    compatibility_score = max(1, min(100, compatibility_score))
                                    print(f"✅ 점수 파싱 성공: {compatibility_score}")
                                else:
                                    print(f"⚠️ 점수 추출 실패: '{score_text}'")
                            except Exception as parse_error:
                                print(f"❌ 점수 파싱 오류 ({user1['name']} ↔ {user2['name']}): {parse_error}")
                        elif '매칭 이유:' in line and not reason_found:
                            try:
                                reason_text = line.split('매칭 이유:', 1)[1].strip()
                                if reason_text:  # 빈 문자열이 아닌 경우만
                                    matching_reason = reason_text
                                    reason_found = True
                                    print(f"✅ 매칭 이유 파싱 성공: {reason_text[:50]}...")
                                else:
                                    print(f"⚠️ 매칭 이유가 빈 문자열임")
                            except Exception as parse_error:
                                print(f"❌ 매칭 이유 파싱 오류 ({user1['name']} ↔ {user2['name']}): {parse_error}")

                    # 매칭 이유를 찾지 못한 경우 전체 응답에서 추출 시도
                    if not reason_found and len(ai_result) > 100:
                        # '매칭 이유:' 패턴을 더 유연하게 찾기
                        import re
                        reason_patterns = [
                            r'매칭 이유:\s*(.+?)(?:\n|$)',
                            r'매칭이유:\s*(.+?)(?:\n|$)',
                            r'이유:\s*(.+?)(?:\n|$)',
                            r'분석:\s*(.+?)(?:\n|$)'
                        ]

                        for pattern in reason_patterns:
                            match = re.search(pattern, ai_result, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                            if match:
                                extracted_reason = match.group(1).strip()
                                if len(extracted_reason) > 10:  # 너무 짧지 않은 경우
                                    matching_reason = extracted_reason
                                    reason_found = True
                                    print(f"✅ 정규식으로 매칭 이유 추출 성공: {extracted_reason[:50]}...")
                                    break

                    # 최종 검증
                    if not matching_reason or len(matching_reason.strip()) < 5:
                        matching_reason = f"AI 분석 결과: {ai_result[:200]}..."
                        print(f"⚠️ 매칭 이유가 너무 짧아 전체 응답 사용: {matching_reason[:50]}...")

                    print(f"📊 최종 결과 - 점수: {compatibility_score}, 이유 길이: {len(matching_reason)}")

                    # 모든 매칭 분석 결과를 저장 (중복 포함)
                    all_pair_scores.append({
                        'user1_id': user1['id'],
                        'user2_id': user2['id'],
                        'user1_name': user1['name'],
                        'user2_name': user2['name'],
                        'compatibility_score': compatibility_score,
                        'matching_reason': matching_reason
                    })

                    print(f"✅ 매칭 분석 완료: {user1['name']} ↔ {user2['name']} (점수: {compatibility_score})")

                except Exception as e:
                    error_msg = f"매칭 분석 중 오류 발생 ({user1['name']} ↔ {user2['name']}): {str(e)}"
                    print(f"❌ {error_msg}")
                    print(f"❌ 오류 타입: {type(e).__name__}")
                    import traceback
                    print(f"❌ 상세 오류: {traceback.format_exc()}")

                    # 치명적인 오류인 경우 전체 매칭을 중단
                    if "HTML 에러 페이지" in str(e) or "API 키" in str(e):
                        return jsonify({'error': f'AI API 호출 중 오류가 발생했습니다: {str(e)}'}), 500

                    # 그 외의 오류는 이 쌍만 건너뛰고 계속 진행
                    continue

        # 새로운 여자 × 기존 남자 매칭
        for user1 in new_females:
            for user2 in existing_males:
                try:
                    # AI에게 호환성 분석 요청
                    prompt = f"""
                    두 사람의 사주와 MBTI 정보를 바탕으로 연애/커플 매칭 호환성을 분석해주세요.

                    [사용자 1]
                    이름: {user1['name']}
                    MBTI: {user1['mbti']}
                    사주: {user1['saju_result']}
                    AI 분석: {user1['ai_analysis']}

                    [사용자 2]
                    이름: {user2['name']}
                    MBTI: {user2['mbti']}
                    사주: {user2['saju_result']}
                    AI 분석: {user2['ai_analysis']}

                    다음 형식으로만 응답해주세요:
                    호환성 점수: [1-100 사이의 숫자]
                    매칭 이유: [호환성 분석 및 이유 설명]
                    """

                    response = model.generate_content(prompt)

                    # 응답이 None인지 확인
                    if response is None:
                        raise Exception("AI 응답이 None입니다")

                    ai_result = response.text.strip() if response.text else ""

                    # AI 응답이 비어있는지 확인
                    if not ai_result:
                        raise Exception("AI 응답이 비어있습니다")

                    # HTML 응답인지 확인 (에러 페이지가 반환된 경우)
                    if ai_result.startswith('<!DOCTYPE') or '<html' in ai_result.lower():
                        raise Exception(f"HTML 에러 페이지가 반환되었습니다. API 키나 모델 설정을 확인해주세요. 응답 내용: {ai_result[:200]}...")

                    # AI 응답 파싱
                    lines = ai_result.split('\n')
                    compatibility_score = 50  # 기본값
                    matching_reason = ai_result  # 기본값으로 전체 응답 저장
                    score_found = False
                    reason_found = False

                    # 더 정확한 파싱을 위해 여러 패턴 시도
                    for line in lines:
                        line = line.strip()

                        # 호환성 점수 찾기
                        if not score_found:
                            if '호환성 점수:' in line or '호환성점수:' in line or '점수:' in line:
                                try:
                                    score_text = line.split(':', 1)[1].strip()
                                    # 숫자만 추출 (괄호, 기호 등 제거)
                                    import re
                                    score_match = re.search(r'\d+', score_text)
                                    if score_match:
                                        score = int(score_match.group())
                                        if 1 <= score <= 100:
                                            compatibility_score = score
                                            score_found = True
                                            print(f"✅ 호환성 점수 파싱 성공: {score}")
                                        else:
                                            print(f"⚠️ 호환성 점수가 범위를 벗어남: {score}")
                                    else:
                                        print(f"⚠️ 호환성 점수를 찾을 수 없음: {line}")
                                except Exception as parse_error:
                                    print(f"❌ 호환성 점수 파싱 오류 ({user1['name']} ↔ {user2['name']}): {parse_error}")

                        # 매칭 이유 찾기
                        elif '매칭 이유:' in line and not reason_found:
                            try:
                                reason_text = line.split('매칭 이유:', 1)[1].strip()
                                if reason_text:  # 빈 문자열이 아닌 경우만
                                    matching_reason = reason_text
                                    reason_found = True
                                    print(f"✅ 매칭 이유 파싱 성공: {reason_text[:50]}...")
                                else:
                                    print(f"⚠️ 매칭 이유가 빈 문자열임")
                            except Exception as parse_error:
                                print(f"❌ 매칭 이유 파싱 오류 ({user1['name']} ↔ {user2['name']}): {parse_error}")

                    # 매칭 이유를 찾지 못한 경우 전체 응답에서 추출 시도
                    if not reason_found and len(ai_result) > 100:
                        # '매칭 이유:' 패턴을 더 유연하게 찾기
                        import re
                        reason_patterns = [
                            r'매칭 이유:\s*(.+?)(?:\n|$)',
                            r'매칭이유:\s*(.+?)(?:\n|$)',
                            r'이유:\s*(.+?)(?:\n|$)',
                            r'분석:\s*(.+?)(?:\n|$)'
                        ]

                        for pattern in reason_patterns:
                            match = re.search(pattern, ai_result, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                            if match:
                                extracted_reason = match.group(1).strip()
                                if len(extracted_reason) > 10:  # 너무 짧지 않은 경우
                                    matching_reason = extracted_reason
                                    reason_found = True
                                    print(f"✅ 정규식으로 매칭 이유 추출 성공: {extracted_reason[:50]}...")
                                    break

                    # 최종 검증
                    if not matching_reason or len(matching_reason.strip()) < 5:
                        matching_reason = f"AI 분석 결과: {ai_result[:200]}..."
                        print(f"⚠️ 매칭 이유가 너무 짧아 전체 응답 사용: {matching_reason[:50]}...")

                    print(f"📊 최종 결과 - 점수: {compatibility_score}, 이유 길이: {len(matching_reason)}")

                    # 모든 매칭 분석 결과를 저장 (중복 포함)
                    all_pair_scores.append({
                        'user1_id': user1['id'],
                        'user2_id': user2['id'],
                        'user1_name': user1['name'],
                        'user2_name': user2['name'],
                        'compatibility_score': compatibility_score,
                        'matching_reason': matching_reason
                    })

                    print(f"✅ 매칭 분석 완료: {user1['name']} ↔ {user2['name']} (점수: {compatibility_score})")

                except Exception as e:
                    error_msg = f"매칭 분석 중 오류 발생 ({user1['name']} ↔ {user2['name']}): {str(e)}"
                    print(f"❌ {error_msg}")

                    # 치명적인 오류인 경우 전체 매칭을 중단
                    if "HTML 에러 페이지" in str(e) or "API 키" in str(e):
                        return jsonify({'error': f'AI API 호출 중 오류가 발생했습니다: {str(e)}'}), 500

                    # 그 외의 오류는 이 쌍만 건너뛰고 계속 진행
                    continue

        # 새로운 남자 × 새로운 여자 매칭 (새로운 사용자들끼리의 매칭)
        for user1 in new_males:
            for user2 in new_females:
                try:
                    # AI에게 호환성 분석 요청
                    prompt = f"""
                    두 사람의 사주와 MBTI 정보를 바탕으로 연애/커플 매칭 호환성을 분석해주세요.

                    [사용자 1]
                    이름: {user1['name']}
                    MBTI: {user1['mbti']}
                    사주: {user1['saju_result']}
                    AI 분석: {user1['ai_analysis']}

                    [사용자 2]
                    이름: {user2['name']}
                    MBTI: {user2['mbti']}
                    사주: {user2['saju_result']}
                    AI 분석: {user2['ai_analysis']}

                    다음 형식으로만 응답해주세요:
                    호환성 점수: [1-100 사이의 숫자]
                    매칭 이유: [호환성 분석 및 이유 설명]
                    """

                    response = model.generate_content(prompt)

                    # 응답이 None인지 확인
                    if response is None:
                        raise Exception("AI 응답이 None입니다")

                    ai_result = response.text.strip() if response.text else ""

                    # AI 응답이 비어있는지 확인
                    if not ai_result:
                        raise Exception("AI 응답이 비어있습니다")

                    # HTML 응답인지 확인 (에러 페이지가 반환된 경우)
                    if ai_result.startswith('<!DOCTYPE') or '<html' in ai_result.lower():
                        raise Exception(f"HTML 에러 페이지가 반환되었습니다. API 키나 모델 설정을 확인해주세요. 응답 내용: {ai_result[:200]}...")

                    # AI 응답 파싱
                    lines = ai_result.split('\n')
                    compatibility_score = 50  # 기본값
                    matching_reason = ai_result  # 기본값으로 전체 응답 저장
                    score_found = False
                    reason_found = False

                    # 더 정확한 파싱을 위해 여러 패턴 시도
                    for line in lines:
                        line = line.strip()

                        # 호환성 점수 찾기
                        if not score_found:
                            if '호환성 점수:' in line or '호환성점수:' in line or '점수:' in line:
                                try:
                                    score_text = line.split(':', 1)[1].strip()
                                    # 숫자만 추출 (괄호, 기호 등 제거)
                                    import re
                                    score_match = re.search(r'\d+', score_text)
                                    if score_match:
                                        score = int(score_match.group())
                                        if 1 <= score <= 100:
                                            compatibility_score = score
                                            score_found = True
                                            print(f"✅ 호환성 점수 파싱 성공: {score}")
                                        else:
                                            print(f"⚠️ 호환성 점수가 범위를 벗어남: {score}")
                                    else:
                                        print(f"⚠️ 호환성 점수를 찾을 수 없음: {line}")
                                except Exception as parse_error:
                                    print(f"❌ 호환성 점수 파싱 오류 ({user1['name']} ↔ {user2['name']}): {parse_error}")

                        # 매칭 이유 찾기
                        elif '매칭 이유:' in line and not reason_found:
                            try:
                                reason_text = line.split('매칭 이유:', 1)[1].strip()
                                if reason_text:  # 빈 문자열이 아닌 경우만
                                    matching_reason = reason_text
                                    reason_found = True
                                    print(f"✅ 매칭 이유 파싱 성공: {reason_text[:50]}...")
                                else:
                                    print(f"⚠️ 매칭 이유가 빈 문자열임")
                            except Exception as parse_error:
                                print(f"❌ 매칭 이유 파싱 오류 ({user1['name']} ↔ {user2['name']}): {parse_error}")

                    # 매칭 이유를 찾지 못한 경우 전체 응답에서 추출 시도
                    if not reason_found and len(ai_result) > 100:
                        # '매칭 이유:' 패턴을 더 유연하게 찾기
                        import re
                        reason_patterns = [
                            r'매칭 이유:\s*(.+?)(?:\n|$)',
                            r'매칭이유:\s*(.+?)(?:\n|$)',
                            r'이유:\s*(.+?)(?:\n|$)',
                            r'분석:\s*(.+?)(?:\n|$)'
                        ]

                        for pattern in reason_patterns:
                            match = re.search(pattern, ai_result, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                            if match:
                                extracted_reason = match.group(1).strip()
                                if len(extracted_reason) > 10:  # 너무 짧지 않은 경우
                                    matching_reason = extracted_reason
                                    reason_found = True
                                    print(f"✅ 정규식으로 매칭 이유 추출 성공: {extracted_reason[:50]}...")
                                    break

                    # 최종 검증
                    if not matching_reason or len(matching_reason.strip()) < 5:
                        matching_reason = f"AI 분석 결과: {ai_result[:200]}..."
                        print(f"⚠️ 매칭 이유가 너무 짧아 전체 응답 사용: {matching_reason[:50]}...")

                    print(f"📊 최종 결과 - 점수: {compatibility_score}, 이유 길이: {len(matching_reason)}")

                    # 모든 매칭 분석 결과를 저장 (중복 포함)
                    all_pair_scores.append({
                        'user1_id': user1['id'],
                        'user2_id': user2['id'],
                        'user1_name': user1['name'],
                        'user2_name': user2['name'],
                        'compatibility_score': compatibility_score,
                        'matching_reason': matching_reason
                    })

                    print(f"✅ 매칭 분석 완료: {user1['name']} ↔ {user2['name']} (점수: {compatibility_score})")

                except Exception as e:
                    error_msg = f"매칭 분석 중 오류 발생 ({user1['name']} ↔ {user2['name']}): {str(e)}"
                    print(f"❌ {error_msg}")

                    # 치명적인 오류인 경우 전체 매칭을 중단
                    if "HTML 에러 페이지" in str(e) or "API 키" in str(e):
                        return jsonify({'error': f'AI API 호출 중 오류가 발생했습니다: {str(e)}'}), 500

                    # 그 외의 오류는 이 쌍만 건너뛰고 계속 진행
                    continue

        # 2. 70점 이상인 매칭만 선정 (모든 쌍에 대해 분석한 후 필터링)
        selected_matches = []

        for pair in all_pair_scores:
            # 70점 이상인 매칭만 선정
            if pair['compatibility_score'] >= 70:
                # user_id 쌍을 정규화하여 중복 방지 (항상 작은 ID가 user1_id가 되도록)
                user1_id = min(pair['user1_id'], pair['user2_id'])
                user2_id = max(pair['user1_id'], pair['user2_id'])

                selected_matches.append({
                    'user1_id': user1_id,
                    'user2_id': user2_id,
                    'compatibility_score': pair['compatibility_score'],
                    'matching_reason': pair['matching_reason']
                })

        # 중복 제거 (같은 쌍에 대해 여러 번 저장된 경우 하나만 남김)
        unique_matches = []
        seen_pairs = set()

        for match in selected_matches:
            pair_key = (match['user1_id'], match['user2_id'])
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                unique_matches.append(match)

        # 3. 선정된 매칭 결과들을 Supabase에 저장
        for match in unique_matches:
            supabase.table('matches').upsert({
                'user1_id': match['user1_id'],
                'user2_id': match['user2_id'],
                'compatibility_score': match['compatibility_score'],
                'matching_reason': match['matching_reason']
            }).execute()

            # 매칭 결과를 응답용으로도 저장
            # 모든 사용자들에서 이름 찾기
            all_users_for_lookup = new_users + existing_users
            matches.append({
                'user1': {'id': match['user1_id'], 'name': next(u[1] for u in all_users_for_lookup if u[0] == match['user1_id'])},
                'user2': {'id': match['user2_id'], 'name': next(u[1] for u in all_users_for_lookup if u[0] == match['user2_id'])},
                'compatibility_score': match['compatibility_score'],
                'reason': match['matching_reason']
            })

        # 매칭 분석에 참여한 새로운 사용자들의 is_matched를 TRUE로 업데이트
        # (새로운 사용자만 매칭 분석에 참여했으므로 새로운 사용자들의 상태만 변경)
        new_user_ids = set()
        for user in new_users:  # 새로운 사용자들
            new_user_ids.add(user[0])

        if new_user_ids:
            # 새로운 사용자들의 is_matched를 TRUE로 업데이트
            for user_id in new_user_ids:
                supabase.table('results').update({'is_matched': True}).eq('id', user_id).execute()

        return jsonify({
            'message': f'매칭이 완료되었습니다. 70점 이상인 매칭 결과만 선정하여 총 {len(matches)}개의 매칭 결과를 생성했습니다.',
            'matches_count': len(matches),
            'matches': matches
        })

    except Exception as e:
        error_details = {
            'message': '매칭 처리 중 오류 발생',
            'error_type': type(e).__name__,
            'error_message': str(e),
            'environment': 'vercel'
        }

        print(f"❌ 최종 매칭 처리 중 치명적 오류 발생: {str(e)}")
        print(f"❌ 오류 타입: {type(e).__name__}")
        import traceback
        print(f"❌ 상세 오류: {traceback.format_exc()}")

        # Vercel 환경에서 발생 가능한 일반적인 오류들에 대한 친화적 메시지
        if "timeout" in str(e).lower() or "time" in str(e).lower():
            error_details['user_message'] = '처리 시간이 초과되었습니다. 사용자 수를 줄여서 다시 시도해주세요.'
        elif "quota" in str(e).lower() or "limit" in str(e).lower():
            error_details['user_message'] = 'AI API 사용량 제한에 도달했습니다. 잠시 후 다시 시도해주세요.'
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            error_details['user_message'] = '네트워크 연결에 문제가 있습니다. 다시 시도해주세요.'
        else:
            error_details['user_message'] = '매칭 처리 중 오류가 발생했습니다. 관리자에게 문의해주세요.'

        return jsonify({'error': error_details['user_message']}), 500

@app.route('/admin/matching/results')
def get_matching_results():
    if not session.get('logged_in'):
        return jsonify({'error': '로그인이 필요합니다'}), 401

    try:
        # Supabase에서 매칭 결과 조회
        matches_response = supabase.table('matches').select('*').order('compatibility_score', desc=True).order('created_at', desc=True).execute()
        matches_data = matches_response.data

        results = []
        for match in matches_data:
            # 각 사용자 정보 별도 조회
            user1_response = supabase.table('results').select('name, mbti, instagram_id').eq('id', match['user1_id']).execute()
            user2_response = supabase.table('results').select('name, mbti, instagram_id').eq('id', match['user2_id']).execute()

            user1_data = user1_response.data[0] if user1_response.data else {'name': 'Unknown', 'mbti': '', 'instagram_id': ''}
            user2_data = user2_response.data[0] if user2_response.data else {'name': 'Unknown', 'mbti': '', 'instagram_id': ''}

            results.append({
                'id': match['id'],
                'compatibility_score': match['compatibility_score'],
                'matching_reason': match['matching_reason'],
                'created_at': match['created_at'],
                'user1': {
                    'name': user1_data['name'],
                    'mbti': user1_data['mbti'],
                    'instagram': user1_data['instagram_id']
                },
                'user2': {
                    'name': user2_data['name'],
                    'mbti': user2_data['mbti'],
                    'instagram': user2_data['instagram_id']
                }
            })

        return jsonify({'matches': results})

    except Exception as e:
        return jsonify({'error': f'매칭 결과 조회 중 오류 발생: {e}'}), 500

@app.route('/saju', methods=['POST'])
def analyze_saju():
    try:
        data = request.get_json()
        name = data.get('name', '정보 없음')
        student_id = data.get('studentId', '정보 없음')
        year = int(data['year']); month = int(data['month']); day = int(data['day']); hour = int(data['hour'])
        mbti = data.get('mbti', '정보 없음')
        instagram_id = data.get('instagramId', '')
        gender = data.get('gender', '')
    except Exception as e:
        return jsonify({"error": f"데이터를 받는 중 오류 발생: {e}"}), 400

    try:
        year_p, month_p, day_p, time_p = calculate_saju_pillars(year, month, day, hour)
        saju_text = f"연주(년): {year_p}, 월주(월): {month_p}, 일주(일): {day_p}, 시주(시): {time_p}"
    except Exception as e:
        return jsonify({"error": f"사주를 계산하는 중 오류 발생: {e}"}), 500

    try:
        # API 키 확인
        if not GOOGLE_API_KEY:
            return jsonify({"error": "Google AI API 키가 설정되지 않아 사주 분석을 수행할 수 없습니다. 관리자에게 문의해주세요."}), 500

        # AI 모델 선택 (여러 모델 시도)
        model_names = ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-pro']
        model = None
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name)
                # 간단한 테스트로 모델 확인
                test_response = model.generate_content('test')
                print(f"✅ 사주 분석에 {model_name} 모델 사용 중")
                break
            except Exception as e:
                print(f"❌ {model_name} 모델 실패: {e}")
                continue

        if model is None:
            return jsonify({"error": "사용 가능한 AI 모델을 찾을 수 없습니다. API 키와 모델 설정을 확인해주세요."}), 500

        prompt = f"""
        너는 사주 명리학과 MBTI를 모두 통달한 최고의 운세 및 연애 컨설턴트야.
        아래 정보를 바탕으로 성격, 연애 스타일, 추천 매칭 상대를 친근한 말투로 분석해줘.
        분석 결과는 반드시 아래 포맷에 맞춰서 출력해야 해.

        [분석 정보]
        - 사주팔자: {saju_text}
        - MBTI: {mbti}

        [출력 형식]
        🔮 사주 정보
        연주(년): [연주 정보], 월주(월): [월주 정보], 일주(일): [일주 정보], 시주(시): [시주 정보]

        💬 AI 분석 결과
        [사주와 MBTI를 바탕으로 한 친근한 분석 멘트. 성격적 특징, 연애 스타일, 주의점 등을 구체적으로 설명할 것.]

        🤝 추천 매칭 상대
        * 사주: [어울리는 사주의 기운, 이유]
        * MBTI: [어울리는 MBTI 유형, 이유]

        마지막에는 짧고 긍정적인 조언으로 마무리해줘.
        """

        response = model.generate_content(prompt)

        # 응답 검증
        if response is None:
            raise Exception("AI 응답이 None입니다")

        ai_response = response.text.strip() if response.text else ""

        if not ai_response:
            raise Exception("AI 응답이 비어있습니다")

        # HTML 응답인지 확인 (에러 페이지가 반환된 경우)
        if ai_response.startswith('<!DOCTYPE') or '<html' in ai_response.lower():
            raise Exception(f"HTML 에러 페이지가 반환되었습니다. API 키나 모델 설정을 확인해주세요. 응답 내용: {ai_response[:200]}...")

        # 학번 중복 체크 및 데이터 저장
        try:
            print(f"📝 데이터 저장 시도: 학번 {student_id}, 이름 {name}")

            # Supabase에서 학번 중복 체크 (더 강력하게)
            existing_response = supabase.table('results').select('id, student_id, name').eq('student_id', student_id).execute()
            if existing_response.data and len(existing_response.data) > 0:
                existing_user = existing_response.data[0]
                return jsonify({"error": f"이미 등록된 학번입니다. ({existing_user['name']}님이 등록하셨습니다)"}), 400

            # 중복이 없으면 Supabase에 데이터 저장 (id 필드 명시적 제외)
            data_to_insert = {
                'student_id': student_id,
                'name': name,
                'mbti': mbti,
                'instagram_id': instagram_id,
                'saju_result': saju_text,
                'ai_analysis': ai_response,
                'gender': gender
            }

            print(f"💾 저장할 데이터: {data_to_insert}")

            # 일반 insert 사용 (Supabase auto-increment가 작동해야 함)
            try:
                insert_response = supabase.table('results').insert(data_to_insert).execute()
            except Exception as insert_error:
                # 시퀀스 문제일 수 있으므로 재시도
                print(f"❌ 일반 insert 실패, 시퀀스 문제일 수 있음: {insert_error}")

                # 최대 ID 조회 후 다음 ID로 명시적 지정
                try:
                    max_id_response = supabase.table('results').select('id').order('id', desc=True).limit(1).execute()
                    next_id = (max_id_response.data[0]['id'] + 1) if max_id_response.data else 1

                    data_with_id = data_to_insert.copy()
                    data_with_id['id'] = next_id

                    print(f"🔄 ID 명시적 지정 후 재시도: ID = {next_id}")
                    insert_response = supabase.table('results').insert(data_with_id).execute()

                except Exception as retry_error:
                    print(f"❌ ID 명시적 지정 재시도 실패: {retry_error}")
                    raise insert_error  # 원래 오류 다시 발생

            print("✅ 분석 결과가 Supabase에 성공적으로 저장되었습니다.")
            print(f"   저장된 데이터 ID: {insert_response.data[0]['id'] if insert_response.data else '알 수 없음'}")
        except Exception as e:
            print(f"Supabase 저장 중 오류 발생: {e}")
            return jsonify({"error": f"데이터 저장 중 오류가 발생했습니다: {e}"}), 500
            # DB 저장 끝 
    except Exception as e:
        return jsonify({"error": f"Gemini API 처리 중 오류 발생: {e}"}), 500

    return jsonify({
        "saju_result": saju_text,
        "ai_analysis": ai_response
    })

# Vercel에서 사용할 WSGI 애플리케이션 (파일 끝의 app 객체를 사용)

# 로컬 개발용 코드 (Vercel에서는 실행되지 않음)
if __name__ == '__main__':
    print("🚀 로컬 개발 서버 시작...")
    print(f"📍 FLASK_ENV: {os.getenv('FLASK_ENV', 'production')}")
    print(f"🔗 서버 주소: http://localhost:5000")

    # 시작 시 API 키 상태 확인
    if GOOGLE_API_KEY:
        print("\n🔧 API 키 상태 확인 중...")
        try:
            valid, message = test_api_key()
            if valid:
                print(f"✅ {message}")
                # 사용 가능한 모델들 출력
                available_models = get_available_models()
                if available_models:
                    print(f"📋 사용 가능한 모델들 ({len(available_models)}개):")
                    for model in available_models[:10]:  # 처음 10개만 출력
                        print(f"   - {model}")
                    if len(available_models) > 10:
                        print(f"   ... 외 {len(available_models) - 10}개")
            else:
                print(f"❌ {message}")
        except Exception as e:
            print(f"❌ API 키 테스트 실패: {e}")
    else:
        print("\n⚠️  GOOGLE_API_KEY가 설정되지 않았습니다.")
        print("   🔑 Google AI Studio에서 새 API 키를 발급받으세요:")
        print("      https://makersuite.google.com/app/apikey")
        print("   📝 .env 파일에 GOOGLE_API_KEY를 설정하세요.")

    # Supabase 연결 상태 확인
    try:
        test_response = supabase.table('results').select('count').limit(1).execute()
        print("✅ Supabase 연결 성공")
    except Exception as e:
        print(f"❌ Supabase 연결 실패: {e}")

    app.run(debug=True, host='0.0.0.0', port=5000)



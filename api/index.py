from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import google.generativeai as genai
import sqlite3
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

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here-change-this-in-production')

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
    return render_template('index.html')

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
        conn = sqlite3.connect('saju_results.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, student_id, name, mbti, instagram_id, gender, saju_result, ai_analysis, is_matched, created_at FROM results ORDER BY created_at DESC")
        results = cursor.fetchall()
        conn.close()

        # 결과를 템플릿에 전달할 수 있도록 리스트로 변환
        admin_data = []
        for row in results:
            admin_data.append({
                'id': row[0],
                'student_id': row[1],
                'name': row[2],
                'mbti': row[3],
                'instagram_id': row[4],
                'gender': row[5],
                'saju_result': row[6],
                'ai_analysis': row[7],
                'is_matched': row[8],
                'created_at': row[9]
            })

        return render_template('admin.html', results=admin_data)
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
        conn = sqlite3.connect('saju_results.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM results WHERE id = ?", (result_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return jsonify({
                'id': result[0],
                'student_id': result[1],
                'name': result[2],
                'mbti': result[3],
                'instagram_id': result[4],
                'saju_result': result[5],
                'ai_analysis': result[6],
                'created_at': result[7]
            })
        else:
            return jsonify({'error': '결과를 찾을 수 없습니다'}), 404
    except Exception as e:
        return jsonify({'error': f'데이터 조회 중 오류 발생: {e}'}), 500

@app.route('/admin/result/<int:result_id>', methods=['DELETE'])
def delete_result(result_id):
    if not session.get('logged_in'):
        return jsonify({'error': '로그인이 필요합니다'}), 401

    try:
        conn = sqlite3.connect('saju_results.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM results WHERE id = ?", (result_id,))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()

        if deleted > 0:
            return jsonify({'message': '결과가 성공적으로 삭제되었습니다'})
        else:
            return jsonify({'error': '삭제할 결과를 찾을 수 없습니다'}), 404
    except Exception as e:
        return jsonify({'error': f'삭제 중 오류 발생: {e}'}), 500

@app.route('/admin/matching', methods=['POST'])
def perform_matching():
    if not session.get('logged_in'):
        return jsonify({'error': '로그인이 필요합니다'}), 401

    try:
        # 새로운 사용자와 기존 매칭된 사용자 모두 가져오기
        conn = sqlite3.connect('saju_results.db')
        cursor = conn.cursor()

        # 새로운 사용자들 (is_matched = FALSE)
        cursor.execute("SELECT id, name, mbti, saju_result, ai_analysis, gender FROM results WHERE is_matched = FALSE")
        new_users = cursor.fetchall()

        # 기존 매칭된 사용자들 (is_matched = TRUE)
        cursor.execute("SELECT id, name, mbti, saju_result, ai_analysis, gender FROM results WHERE is_matched = TRUE")
        existing_users = cursor.fetchall()

        if len(new_users) == 0:
            return jsonify({'error': '매칭할 새로운 사용자가 없습니다'}), 400

        if len(existing_users) == 0 and len(new_users) < 2:
            return jsonify({'error': '매칭을 위해 최소 2명의 사용자가 필요합니다'}), 400

        # 성별에 따라 사용자들을 분류
        def classify_users_by_gender(users):
            males = []
            females = []
            for user in users:
                gender = user[5] if len(user) > 5 else ''  # gender는 6번째 필드
                if gender == 'MALE':
                    males.append(user)
                elif gender == 'FEMALE':
                    females.append(user)
                else:
                    # 성별이 지정되지 않은 경우 기본적으로 남자로 취급 (필요시 수정)
                    males.append(user)
            return males, females

        # 새로운 사용자들을 성별로 분류
        new_males, new_females = classify_users_by_gender(new_users)
        # 기존 사용자들을 성별로 분류
        existing_males, existing_females = classify_users_by_gender(existing_users)

        matches = []
        all_pair_scores = []  # 모든 쌍의 호환성 점수를 저장

        # AI를 사용한 매칭 수행
        # API 키 확인
        if not GOOGLE_API_KEY:
            return jsonify({'error': 'Google AI API 키가 설정되지 않아 매칭을 수행할 수 없습니다. 관리자에게 문의해주세요.'}), 500

        # 여러 모델을 시도해보고 가능한 것을 사용
        model_names = ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-pro']
        model = None
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name)
                # 테스트 호출로 모델이 작동하는지 확인
                test_response = model.generate_content('test')
                print(f"✅ {model_name} 모델 사용 중")
                break
            except Exception as e:
                print(f"❌ {model_name} 모델 실패: {e}")
                continue

        if model is None:
            return jsonify({'error': '사용 가능한 AI 모델을 찾을 수 없습니다. API 키와 모델 설정을 확인해주세요.'}), 500

        # 1. 성별 기반 매칭 분석 수행
        # 새로운 남자 × 기존 여자 매칭
        for user1 in new_males:
            for user2 in existing_females:
                try:
                    # AI에게 호환성 분석 요청
                    prompt = f"""
                    두 사람의 사주와 MBTI 정보를 바탕으로 연애/커플 매칭 호환성을 분석해주세요.

                    [사용자 1]
                    이름: {user1[1]}
                    MBTI: {user1[2]}
                    사주: {user1[3]}
                    AI 분석: {user1[4]}

                    [사용자 2]
                    이름: {user2[1]}
                    MBTI: {user2[2]}
                    사주: {user2[3]}
                    AI 분석: {user2[4]}

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
                                print(f"❌ 점수 파싱 오류 ({user1[1]} ↔ {user2[1]}): {parse_error}")
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
                                print(f"❌ 매칭 이유 파싱 오류 ({user1[1]} ↔ {user2[1]}): {parse_error}")

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
                        'user1_id': user1[0],
                        'user2_id': user2[0],
                        'user1_name': user1[1],
                        'user2_name': user2[1],
                        'compatibility_score': compatibility_score,
                        'matching_reason': matching_reason
                    })

                    print(f"✅ 매칭 분석 완료: {user1[1]} ↔ {user2[1]} (점수: {compatibility_score})")

                except Exception as e:
                    error_msg = f"매칭 분석 중 오류 발생 ({user1[1]} ↔ {user2[1]}): {str(e)}"
                    print(f"❌ {error_msg}")

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
                    이름: {user1[1]}
                    MBTI: {user1[2]}
                    사주: {user1[3]}
                    AI 분석: {user1[4]}

                    [사용자 2]
                    이름: {user2[1]}
                    MBTI: {user2[2]}
                    사주: {user2[3]}
                    AI 분석: {user2[4]}

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
                                    print(f"❌ 호환성 점수 파싱 오류 ({user1[1]} ↔ {user2[1]}): {parse_error}")

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
                                print(f"❌ 매칭 이유 파싱 오류 ({user1[1]} ↔ {user2[1]}): {parse_error}")

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
                        'user1_id': user1[0],
                        'user2_id': user2[0],
                        'user1_name': user1[1],
                        'user2_name': user2[1],
                        'compatibility_score': compatibility_score,
                        'matching_reason': matching_reason
                    })

                    print(f"✅ 매칭 분석 완료: {user1[1]} ↔ {user2[1]} (점수: {compatibility_score})")

                except Exception as e:
                    error_msg = f"매칭 분석 중 오류 발생 ({user1[1]} ↔ {user2[1]}): {str(e)}"
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
                    이름: {user1[1]}
                    MBTI: {user1[2]}
                    사주: {user1[3]}
                    AI 분석: {user1[4]}

                    [사용자 2]
                    이름: {user2[1]}
                    MBTI: {user2[2]}
                    사주: {user2[3]}
                    AI 분석: {user2[4]}

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
                                    print(f"❌ 호환성 점수 파싱 오류 ({user1[1]} ↔ {user2[1]}): {parse_error}")

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
                                print(f"❌ 매칭 이유 파싱 오류 ({user1[1]} ↔ {user2[1]}): {parse_error}")

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
                        'user1_id': user1[0],
                        'user2_id': user2[0],
                        'user1_name': user1[1],
                        'user2_name': user2[1],
                        'compatibility_score': compatibility_score,
                        'matching_reason': matching_reason
                    })

                    print(f"✅ 매칭 분석 완료: {user1[1]} ↔ {user2[1]} (점수: {compatibility_score})")

                except Exception as e:
                    error_msg = f"매칭 분석 중 오류 발생 ({user1[1]} ↔ {user2[1]}): {str(e)}"
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

        # 3. 선정된 매칭 결과들을 데이터베이스에 저장
        for match in unique_matches:
            cursor.execute("""
                INSERT OR REPLACE INTO matches (user1_id, user2_id, compatibility_score, matching_reason)
                VALUES (?, ?, ?, ?)
            """, (match['user1_id'], match['user2_id'], match['compatibility_score'], match['matching_reason']))

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
            cursor.executemany(
                "UPDATE results SET is_matched = TRUE WHERE id = ?",
                [(user_id,) for user_id in new_user_ids]
            )

        conn.commit()
        conn.close()

        return jsonify({
            'message': f'매칭이 완료되었습니다. 70점 이상인 매칭 결과만 선정하여 총 {len(matches)}개의 매칭 결과를 생성했습니다.',
            'matches_count': len(matches),
            'matches': matches
        })

    except Exception as e:
        return jsonify({'error': f'매칭 처리 중 오류 발생: {e}'}), 500

@app.route('/admin/matching/results')
def get_matching_results():
    if not session.get('logged_in'):
        return jsonify({'error': '로그인이 필요합니다'}), 401

    try:
        conn = sqlite3.connect('saju_results.db')
        cursor = conn.cursor()

        # 매칭 결과 조회 (사용자 정보와 함께)
        cursor.execute("""
            SELECT
                m.id,
                m.compatibility_score,
                m.matching_reason,
                m.created_at,
                u1.name as user1_name,
                u1.mbti as user1_mbti,
                u1.instagram_id as user1_instagram,
                u2.name as user2_name,
                u2.mbti as user2_mbti,
                u2.instagram_id as user2_instagram
            FROM matches m
            JOIN results u1 ON m.user1_id = u1.id
            JOIN results u2 ON m.user2_id = u2.id
            ORDER BY m.compatibility_score DESC, m.created_at DESC
        """)

        matches = cursor.fetchall()
        conn.close()

        results = []
        for match in matches:
            results.append({
                'id': match[0],
                'compatibility_score': match[1],
                'matching_reason': match[2],
                'created_at': match[3],
                'user1': {
                    'name': match[4],
                    'mbti': match[5],
                    'instagram': match[6]
                },
                'user2': {
                    'name': match[7],
                    'mbti': match[8],
                    'instagram': match[9]
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

        # 학번 중복 체크
        try:
            conn = sqlite3.connect('saju_results.db')
            cursor = conn.cursor()

            # 동일한 학번이 이미 존재하는지 확인
            cursor.execute("SELECT COUNT(*) FROM results WHERE student_id = ?", (student_id,))
            existing_count = cursor.fetchone()[0]

            if existing_count > 0:
                conn.close()
                return jsonify({"error": "이미 등록된 학번입니다. 동일한 학번으로 중복 등록할 수 없습니다."}), 400

            # 중복이 없으면 데이터 저장
            cursor.execute(
                "INSERT INTO results (student_id, name, mbti, instagram_id, saju_result, ai_analysis, gender) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (student_id, name, mbti, instagram_id, saju_text, ai_response, gender)
            )
            conn.commit()
            conn.close()
            print("분석 결과가 데이터베이스에 성공적으로 저장되었습니다.")
        except Exception as e:
            print(f"데이터베이스 저장 중 오류 발생: {e}")
            # DB 저장 끝 
    except Exception as e:
        return jsonify({"error": f"Gemini API 처리 중 오류 발생: {e}"}), 500

    return jsonify({
        "saju_result": saju_text,
        "ai_analysis": ai_response
    })

if __name__ == '__main__':
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
        print("   📝 발급받은 키를 코드에서 GOOGLE_API_KEY 변수에 입력하세요.")

    app.run(debug=True)



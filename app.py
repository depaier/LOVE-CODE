from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
import sqlite3


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

# Gemini API 키 설정
GOOGLE_API_KEY = 'AIzaSyATZxIdQuouCzerfvtgnlpod0rJqiIEDNY'
genai.configure(api_key=GOOGLE_API_KEY)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/saju', methods=['POST'])
def analyze_saju():
    try:
        data = request.get_json()
        name = data.get('name', '정보 없음')
        student_id = data.get('studentId', '정보 없음')
        year = int(data['year']); month = int(data['month']); day = int(data['day']); hour = int(data['hour'])
        mbti = data.get('mbti', '정보 없음')
    except Exception as e:
        return jsonify({"error": f"데이터를 받는 중 오류 발생: {e}"}), 400

    try:
        year_p, month_p, day_p, time_p = calculate_saju_pillars(year, month, day, hour)
        saju_text = f"연주(년): {year_p}, 월주(월): {month_p}, 일주(일): {day_p}, 시주(시): {time_p}"
    except Exception as e:
        return jsonify({"error": f"사주를 계산하는 중 오류 발생: {e}"}), 500

    try:
        # 수정: 최신 모델 이름으로 변경
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"너는 사주 명리학과 MBTI를 모두 통달한 최고의 운세 및 연애 컨설턴트야. 아래 정보를 바탕으로 성격, 연애 스타일, 추천 매칭 상대를 친근한 말투로 분석해줘.\n\n[분석 정보]\n- 사주팔자: {saju_text}\n- MBTI: {mbti}"
        
        response = model.generate_content(prompt)
        ai_response = response.text
        # 새로 추가된 DB 저장 부분
        try:
            conn = sqlite3.connect('saju_results.db')
            cursor = conn.cursor()
            # SQL ?는 보안을 위해 사용
            cursor.execute(
                "INSERT INTO results (student_id, name, mbti, saju_result, ai_analysis) VALUES (?, ?, ?, ?, ?)",
                (student_id, name, mbti, saju_text, ai_response)
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
    app.run(debug=True)



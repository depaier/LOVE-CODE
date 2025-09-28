import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

# 환경변수 로딩
load_dotenv()

# Supabase 연결 설정
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_URL과 SUPABASE_ANON_KEY 환경변수가 설정되지 않았습니다.")

# Supabase 클라이언트 생성
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# 사주 계산 함수 (api/index.py에서 복사)
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

# 테스트 데이터 생성 함수
def generate_test_data():
    # 한국 여성 이름 리스트
    female_names = [
        "김지현", "이지은", "박서연", "최수진", "정민지",
        "강예린", "윤하늘", "임소라", "한지민", "오나래"
    ]

    # 한국 남성 이름 리스트
    male_names = [
        "김민준", "이지훈", "박준혁", "최현우", "정우진",
        "강민재", "윤지호", "임서준", "한도윤"
    ]

    # 다양한 MBTI 유형들
    mbti_types = [
        "ENFP", "INFP", "ENFJ", "INFJ",
        "ENTP", "INTP", "ENTJ", "INTJ",
        "ESFP", "ISFP", "ESFJ", "ISFJ",
        "ESTP", "ISTP", "ESTJ", "ISTJ"
    ]

    # 인스타그램 ID용 접미사들
    instagram_suffixes = [
        "_love", "_sweet", "_cute", "_pretty", "_beautiful",
        "_angel", "_dream", "_star", "_moon", "_sun",
        "_heart", "_smile", "_joy", "_peace", "_happy",
        "_cool", "_hot", "_king", "_master", "_pro"
    ]

    test_data = []

    # 기존 데이터의 최대 ID를 확인해서 학번 시작 번호 결정
    try:
        existing_data = supabase.table('results').select('student_id').order('student_id', desc=True).limit(1).execute()
        start_student_id = existing_data.data[0]['student_id'] + 1 if existing_data.data else 2025001
    except:
        start_student_id = 2025001

    # 여성 계정 10개 생성
    for i in range(10):
        # 학번 생성 (고유하게)
        student_id = start_student_id + i

        # 이름 선택
        name = female_names[i]

        # MBTI 랜덤 선택
        mbti = random.choice(mbti_types)

        # 인스타그램 ID 생성
        base_name = name.replace(" ", "").lower()
        instagram_suffix = random.choice(instagram_suffixes[:15])  # 여성용 접미사만 사용
        instagram_id = f"{base_name}{instagram_suffix}"

        # 랜덤 생년월일시 생성 (1995-2005년 사이)
        year = random.randint(1995, 2005)
        month = random.randint(1, 12)
        day = random.randint(1, 28)  # 간단하게 28일로 통일
        hour = random.randint(0, 23)

        # 사주 계산
        year_p, month_p, day_p, time_p = calculate_saju_pillars(year, month, day, hour)
        saju_result = f"연주(년): {year_p}, 월주(월): {month_p}, 일주(일): {day_p}, 시주(시): {time_p}"

        # AI 분석 결과 (여성용)
        ai_analysis = f"""🔮 사주 정보
연주(년): {year_p}, 월주(월): {month_p}, 일주(일): {day_p}, 시주(시): {time_p}

💬 AI 분석 결과
{name}님은 밝고 따뜻한 성격을 가지고 계시네요. MBTI {mbti} 유형답게 창의적이고 사람들과의 소통을 좋아하는 스타일입니다. 연애에서는 진심 어린 마음으로 상대방을 대하는 타입이에요.

🤝 추천 매칭 상대
* 사주: {year_p}의 기운과 잘 어울리는 사주를 가진 분
* MBTI: {mbti}와 잘 맞는 유형들

행복한 연애 하시길 바래요! 💕"""

        test_data.append({
            'student_id': student_id,
            'name': name,
            'mbti': mbti,
            'instagram_id': instagram_id,
            'saju_result': saju_result,
            'ai_analysis': ai_analysis,
            'gender': 'FEMALE'
        })

    # 남성 계정 9개 생성
    for i in range(9):
        # 학번 생성 (여성 다음부터 이어서)
        student_id = start_student_id + 10 + i

        # 이름 선택
        name = male_names[i]

        # MBTI 랜덤 선택
        mbti = random.choice(mbti_types)

        # 인스타그램 ID 생성
        base_name = name.replace(" ", "").lower()
        instagram_suffix = random.choice(instagram_suffixes[10:])  # 남성용 접미사 사용
        instagram_id = f"{base_name}{instagram_suffix}"

        # 랜덤 생년월일시 생성 (1995-2005년 사이)
        year = random.randint(1995, 2005)
        month = random.randint(1, 12)
        day = random.randint(1, 28)  # 간단하게 28일로 통일
        hour = random.randint(0, 23)

        # 사주 계산
        year_p, month_p, day_p, time_p = calculate_saju_pillars(year, month, day, hour)
        saju_result = f"연주(년): {year_p}, 월주(월): {month_p}, 일주(일): {day_p}, 시주(시): {time_p}"

        # AI 분석 결과 (남성용)
        ai_analysis = f"""🔮 사주 정보
연주(년): {year_p}, 월주(월): {month_p}, 일주(일): {day_p}, 시주(시): {time_p}

💬 AI 분석 결과
{name}님은 차분하고 신뢰할 수 있는 성격을 가지고 계시네요. MBTI {mbti} 유형답게 분석적이고 계획적인 스타일입니다. 연애에서는 책임감 있게 상대방을 챙기는 타입이에요.

🤝 추천 매칭 상대
* 사주: {year_p}의 기운과 조화를 이루는 사주를 가진 분
* MBTI: {mbti}와 잘 어울리는 유형들

좋은 인연 만나시길 바래요! 💪"""

        test_data.append({
            'student_id': student_id,
            'name': name,
            'mbti': mbti,
            'instagram_id': instagram_id,
            'saju_result': saju_result,
            'ai_analysis': ai_analysis,
            'gender': 'MALE'
        })

    return test_data

def main():
    try:
        print("🧪 테스트 계정 생성 중 (여성 10명 + 남성 9명)...")

        # 테스트 데이터 생성
        test_accounts = generate_test_data()

        print("\n📋 생성할 테스트 계정 목록:")
        female_count = sum(1 for account in test_accounts if account['gender'] == 'FEMALE')
        male_count = sum(1 for account in test_accounts if account['gender'] == 'MALE')
        print(f"여성: {female_count}명, 남성: {male_count}명")

        for i, account in enumerate(test_accounts, 1):
            gender_kor = "여성" if account['gender'] == 'FEMALE' else "남성"
            print(f"{i}. {account['name']} ({gender_kor}, 학번: {account['student_id']}, MBTI: {account['mbti']}, 인스타: {account['instagram_id']})")

        # Supabase에 데이터 삽입
        inserted_count = 0
        female_inserted = 0
        male_inserted = 0

        for account in test_accounts:
            try:
                # 학번 중복 체크
                existing = supabase.table('results').select('id').eq('student_id', account['student_id']).execute()
                if existing.data:
                    print(f"⚠️ 학번 {account['student_id']} 이미 존재 - 건너뜀")
                    continue

                # 데이터 삽입
                response = supabase.table('results').insert(account).execute()
                if response.data:
                    inserted_count += 1
                    if account['gender'] == 'FEMALE':
                        female_inserted += 1
                    else:
                        male_inserted += 1
                    print(f"✅ {account['name']} ({account['gender']}) 계정 추가 완료 (ID: {response.data[0]['id']})")
                else:
                    print(f"❌ {account['name']} ({account['gender']}) 계정 추가 실패")

            except Exception as e:
                print(f"❌ {account['name']} ({account['gender']}) 계정 추가 중 오류: {e}")

        print(f"\n🎉 총 {inserted_count}개의 테스트 계정이 성공적으로 추가되었습니다!")
        print(f"   - 여성: {female_inserted}명")
        print(f"   - 남성: {male_inserted}명")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        raise

if __name__ == '__main__':
    main()


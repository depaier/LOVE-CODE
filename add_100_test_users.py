#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv
import os

# 환경변수 로딩
load_dotenv()

# Supabase 연결
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# 여자 이름 50개
female_names = [
    "김서현", "이지우", "박예은", "최서연", "정유진", "강민정", "윤하은", "임채영", "한소영", "오나연",
    "송지민", "배수진", "류하나", "신예린", "문지혜", "조아영", "권서영", "홍유리", "고민지", "백지수",
    "서다은", "남예지", "양지원", "안서윤", "장민서", "전소연", "황예나", "노지영", "도하린", "마유진",
    "유서아", "구지현", "변소희", "심예진", "원지원", "공서은", "탁민주", "석지혜", "곽나영", "복서진",
    "진유나", "남궁예린", "선우지은", "독고민정", "사공서연", "제갈유진", "황보지민", "연수진", "어지원", "음서현"
]

# 남자 이름 50개
male_names = [
    "김준서", "이도현", "박시우", "최준혁", "정민준", "강태윤", "윤서준", "임건우", "한지호", "오준영",
    "송현우", "배태민", "류성민", "신동현", "문준호", "조시현", "권태현", "홍민수", "고준우", "백도윤",
    "서민성", "남주원", "양현준", "안태영", "장준서", "전시형", "황성훈", "노태준", "도현민", "마준혁",
    "유성준", "구태윤", "변준호", "심현우", "원도현", "공성민", "탁준영", "석태현", "곽민준", "복성우",
    "진도윤", "남궁준서", "선우태민", "독고현준", "사공민성", "제갈준혁", "황보성훈", "연태윤", "어준호", "음도현"
]

# MBTI 유형 16개
mbti_types = ["ENFP", "INFP", "ENFJ", "INFJ", "ENTP", "INTP", "ENTJ", "INTJ", 
              "ESFP", "ISFP", "ESFJ", "ISFJ", "ESTP", "ISTP", "ESTJ", "ISTJ"]

def calculate_saju_pillars(year, month, day, hour):
    """사주 계산 함수"""
    cheon_gan = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
    ji_ji = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]

    # 연주 계산
    year_gan_index = (year - 4) % 10
    year_ji_index = (year - 4) % 12
    year_pillar = cheon_gan[year_gan_index] + ji_ji[year_ji_index]

    # 월주 계산 (간단 버전)
    month_gan_index = (year_gan_index * 2 + month) % 10
    month_ji_index = (month + 1) % 12
    month_pillar = cheon_gan[month_gan_index] + ji_ji[month_ji_index]

    # 일주 계산 (간단 버전)
    total_days = (year - 2000) * 365 + month * 30 + day
    day_gan_index = (total_days + 6) % 10
    day_ji_index = (total_days + 8) % 12
    day_pillar = cheon_gan[day_gan_index] + ji_ji[day_ji_index]

    # 시주 계산
    time_ji_index = hour // 2 % 12
    time_gan_index = (day_gan_index * 2 + time_ji_index) % 10
    time_pillar = cheon_gan[time_gan_index] + ji_ji[time_ji_index]

    return year_pillar, month_pillar, day_pillar, time_pillar

def generate_ai_analysis(name, mbti, year_p, month_p, day_p, time_p, gender):
    """AI 분석 텍스트 생성"""
    if gender == "FEMALE":
        personality_traits = [
            "밝고 따뜻한", "섬세하고 공감능력이 뛰어난", "창의적이고 상상력이 풍부한",
            "친근하고 사교적인", "신중하고 계획적인", "열정적이고 에너지 넘치는"
        ]
        career_traits = [
            "사람들과의 소통을 좋아하는", "예술적 감성이 뛰어난", "배려심이 많은",
            "리더십이 있는", "분석적이고 논리적인", "감정적 지지를 잘 하는"
        ]
    else:
        personality_traits = [
            "차분하고 신뢰할 수 있는", "분석적이고 논리적인", "결단력이 있고 추진력이 강한",
            "사교적이고 유머감각이 있는", "책임감이 강하고 성실한", "창의적이고 혁신적인"
        ]
        career_traits = [
            "계획적이고 체계적인", "도전적이고 모험을 좋아하는", "사람들을 이끄는",
            "문제 해결능력이 뛰어난", "꼼꼼하고 정확한", "팀워크를 중시하는"
        ]
    
    personality = random.choice(personality_traits)
    career = random.choice(career_traits)
    
    return f"""🔮 사주 정보
연주(년): {year_p}, 월주(월): {month_p}, 일주(일): {day_p}, 시주(시): {time_p}

💬 AI 분석 결과
{name}님은 {personality} 성격을 가지고 계시네요. MBTI {mbti} 유형답게 {career} 스타일입니다. 연애에서는 진심 어린 마음으로 상대방을 대하는 타입이에요.

🤝 추천 매칭 상대
* 사주: {year_p}의 기운과 잘 어울리는 사주를 가진 분
* MBTI: {mbti}와 잘 맞는 유형들

행복한 연애 하시길 바래요! 💕"""

def generate_test_users():
    """테스트 유저 100명 생성"""
    users = []
    base_student_id = 300000  # 기존 사용자와 겹치지 않는 학번 시작
    
    # 여자 50명 생성
    for i in range(50):
        name = female_names[i]
        student_id = base_student_id + i + 1
        mbti = random.choice(mbti_types)
        instagram_id = f"{name.replace(' ', '')}_insta{i+1:02d}"
        
        # 랜덤 생년월일시 (1995-2005년생)
        year = random.randint(1995, 2005)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        hour = random.randint(0, 23)
        
        # 사주 계산
        year_p, month_p, day_p, time_p = calculate_saju_pillars(year, month, day, hour)
        saju_result = f"{year_p}/{month_p}/{day_p}/{time_p}"
        
        # AI 분석 생성
        ai_analysis = generate_ai_analysis(name, mbti, year_p, month_p, day_p, time_p, "FEMALE")
        
        users.append({
            'student_id': student_id,
            'name': name,
            'mbti': mbti,
            'instagram_id': instagram_id,
            'saju_result': saju_result,
            'ai_analysis': ai_analysis,
            'gender': 'FEMALE'
        })
    
    # 남자 50명 생성
    for i in range(50):
        name = male_names[i]
        student_id = base_student_id + 50 + i + 1
        mbti = random.choice(mbti_types)
        instagram_id = f"{name.replace(' ', '')}_insta{i+51:02d}"
        
        # 랜덤 생년월일시 (1995-2005년생)
        year = random.randint(1995, 2005)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        hour = random.randint(0, 23)
        
        # 사주 계산
        year_p, month_p, day_p, time_p = calculate_saju_pillars(year, month, day, hour)
        saju_result = f"{year_p}/{month_p}/{day_p}/{time_p}"
        
        # AI 분석 생성
        ai_analysis = generate_ai_analysis(name, mbti, year_p, month_p, day_p, time_p, "MALE")
        
        users.append({
            'student_id': student_id,
            'name': name,
            'mbti': mbti,
            'instagram_id': instagram_id,
            'saju_result': saju_result,
            'ai_analysis': ai_analysis,
            'gender': 'MALE'
        })
    
    return users

def main():
    print("👥 100명 테스트 유저 생성 중...")
    print("=" * 50)
    
    # 테스트 유저 생성
    test_users = generate_test_users()
    
    print(f"📊 생성된 유저:")
    print(f"   여자: 50명")
    print(f"   남자: 50명")
    print(f"   총계: {len(test_users)}명")
    print()
    
    # 일부 유저 미리보기
    print("👀 생성된 유저 미리보기:")
    for i, user in enumerate(test_users[:5]):
        gender_icon = "👩" if user['gender'] == 'FEMALE' else "👨"
        print(f"   {gender_icon} {user['name']} (학번: {user['student_id']}, MBTI: {user['mbti']})")
    print("   ...")
    print()
    
    # 자동으로 진행 (확인 없이)
    print("✅ 자동으로 데이터베이스에 추가를 진행합니다.")
    
    print("💾 데이터베이스에 유저 추가 중...")
    
    # 배치 삽입 (10명씩)
    batch_size = 10
    success_count = 0
    error_count = 0
    
    for i in range(0, len(test_users), batch_size):
        batch = test_users[i:i+batch_size]
        
        try:
            # Supabase에 배치 삽입
            response = supabase.table('results').insert(batch).execute()
            
            if response.data:
                success_count += len(batch)
                print(f"✅ 배치 {i//batch_size + 1}: {len(batch)}명 추가 성공")
            else:
                error_count += len(batch)
                print(f"❌ 배치 {i//batch_size + 1}: 삽입 실패")
                
        except Exception as e:
            error_count += len(batch)
            print(f"❌ 배치 {i//batch_size + 1} 오류: {e}")
    
    print()
    print("📊 최종 결과:")
    print(f"   ✅ 성공: {success_count}명")
    print(f"   ❌ 실패: {error_count}명")
    print(f"   📊 성공률: {success_count/(success_count+error_count)*100:.1f}%")
    
    if success_count > 0:
        print("🎉 테스트 유저 추가가 완료되었습니다!")
        print("💡 이제 매칭 시스템을 테스트할 수 있습니다.")

if __name__ == "__main__":
    main()

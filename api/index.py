from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import google.generativeai as genai
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from pywebpush import webpush
import json
import uuid
import re
import time
import gc  # 가비지 컬렉션용
from datetime import datetime

# 환경변수 로딩
load_dotenv()

# --- [사주 계산 함수 초고속 최적화 버전 + 캐싱] ---
# 사주 계산 결과 캐시 (메모리 캐싱으로 동일 데이터 반복 계산 방지)
saju_cache = {}

# --- [사주 분석 결과 캐시] ---
# 동일한 사주 + MBTI 조합에 대한 AI 분석 결과를 캐싱 (파일 기반)
import json
import os

SAJU_CACHE_FILE = os.path.join(os.path.dirname(__file__), 'saju_cache.json')
MATCHING_CACHE_FILE = os.path.join(os.path.dirname(__file__), 'matching_cache.json')

# 전역 메모리 캐시 (파일 I/O 최소화)
_global_matching_cache = None
_cache_save_counter = 0

def load_saju_cache():
    """캐시 파일에서 사주 분석 캐시 로드"""
    try:
        if os.path.exists(SAJU_CACHE_FILE):
            with open(SAJU_CACHE_FILE, 'r', encoding='utf-8') as f:
                # MBTI별 캐시 로드 (키는 MBTI 문자열)
                cache_data = json.load(f)
                print(f"✅ 캐시 파일 로드 완료: {len(cache_data)}개 항목")
                if 'ENFP' in cache_data:
                    preview = cache_data['ENFP'][:100] + "..."
                    print(f"📋 ENFP 템플릿 미리보기: {preview}")
                return cache_data  # 그대로 반환
    except Exception as e:
        print(f"❌ 캐시 파일 로드 오류: {e}")
    return {}

def save_saju_cache(cache):
    """사주 분석 캐시를 파일에 저장"""
    try:
        # MBTI별 캐시 저장 (키는 MBTI 문자열 그대로)
        with open(SAJU_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"캐시 파일 저장 오류: {e}")

def load_matching_cache():
    """매칭 호환성 캐시 로드 (크기 제한 및 검증 포함)"""
    try:
        if os.path.exists(MATCHING_CACHE_FILE):
            # 파일 크기 확인 (10MB 제한)
            file_size = os.path.getsize(MATCHING_CACHE_FILE)
            if file_size > 10 * 1024 * 1024:  # 10MB
                print(f"⚠️ 매칭 캐시 파일이 너무 큽니다 ({file_size/1024/1024:.1f}MB). 백업 후 초기화합니다.")
                # 백업 생성
                backup_file = f"{MATCHING_CACHE_FILE}.backup_{int(time.time())}"
                os.rename(MATCHING_CACHE_FILE, backup_file)
                return {}
            
            with open(MATCHING_CACHE_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # JSON 유효성 사전 검증
                if not content.strip():
                    return {}
                
                # 기본적인 JSON 형식 검증
                if not (content.strip().startswith('{') and content.strip().endswith('}')):
                    print("⚠️ 매칭 캐시 파일 형식이 잘못되었습니다. 초기화합니다.")
                    return {}
                
                cache = json.loads(content)
                print(f"📖 매칭 캐시 로드: {len(cache)}개 항목 ({file_size/1024:.1f}KB)")
                return cache
                
    except json.JSONDecodeError as e:
        print(f"⚠️ 매칭 캐시 JSON 파싱 오류: {e}")
        # 손상된 파일 백업 후 초기화
        if os.path.exists(MATCHING_CACHE_FILE):
            backup_file = f"{MATCHING_CACHE_FILE}.error_backup_{int(time.time())}"
            os.rename(MATCHING_CACHE_FILE, backup_file)
            print(f"📁 손상된 캐시 파일을 {backup_file}로 백업했습니다.")
        return {}
    except Exception as e:
        print(f"매칭 캐시 로드 오류: {e}")
        return {}

def save_matching_cache(cache):
    """매칭 호환성 캐시 저장 (메모리 최적화)"""
    try:
        # 캐시 크기 제한 (1500개 항목으로 더 엄격하게)
        if len(cache) > 1500:
            print(f"⚠️ 매칭 캐시가 너무 큽니다 ({len(cache)}개). 최신 1000개만 유지합니다.")
            # 최신 1000개만 유지 (키를 정렬해서)
            sorted_keys = sorted(cache.keys())[-1000:]
            cache = {k: cache[k] for k in sorted_keys}
        
        # 임시 파일에 먼저 저장 (원자적 쓰기, compact format)
        temp_file = f"{MATCHING_CACHE_FILE}.tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, separators=(',', ':'))  # compact format
        
        # 성공적으로 저장되면 원본 파일로 이동
        os.rename(temp_file, MATCHING_CACHE_FILE)
        
    except Exception as e:
        print(f"매칭 캐시 저장 오류: {e}")
        # 임시 파일 정리
        temp_file = f"{MATCHING_CACHE_FILE}.tmp"
        if os.path.exists(temp_file):
            os.remove(temp_file)

def calculate_mbti_compatibility_score(mbti1, mbti2):
    """MBTI 기반 호환성 점수 계산 (룰 기반)"""
    score = 50  # 기본 호환성 점수

    # 각 차원별 호환성 가산점
    dimensions = [
        (mbti1[0], mbti2[0], 15),  # I/E (외향성/내향성)
        (mbti1[1], mbti2[1], 15),  # S/N (감각/직관)
        (mbti1[2], mbti2[2], 10),  # T/F (사고/감정)
        (mbti1[3], mbti2[3], 10),  # J/P (판단/인식)
    ]

    for dim1, dim2, points in dimensions:
        if dim1 == dim2:
            score += points

    return max(20, min(100, score))

def calculate_saju_compatibility_score(saju1, saju2):
    """사주 기반 호환성 점수 계산 (룰 기반)"""
    score = 60  # 기본 사주 호환성

    try:
        # 간단한 사주 요소 추출 및 비교
        elements = ['목', '화', '토', '금', '수']

        # 같은 오행 기운이 있는지 확인
        common_elements = 0
        for element in elements:
            if element in saju1 and element in saju2:
                common_elements += 1

        # 상생/상극 관계 고려 (단순화)
        if common_elements > 0:
            score += common_elements * 8
        else:
            score -= 10  # 다른 기운은 약간 감점

    except Exception:
        pass  # 오류 시 기본 점수 유지

    return max(30, min(100, score))

def get_cached_matching_result(user1, user2):
    """메모리 캐시에서 매칭 결과 조회 (파일 I/O 최소화)"""
    global _global_matching_cache
    
    try:
        # 첫 번째 호출시에만 파일에서 로드
        if _global_matching_cache is None:
            print("📖 매칭 캐시 초기 로드...")
            _global_matching_cache = load_matching_cache()
            print(f"✅ 캐시 로드 완료: {len(_global_matching_cache)}개 항목")
        
        # 정규화된 키 생성 (항상 ID 순으로 정렬)
        key_parts = sorted([str(user1['id']), str(user2['id'])])
        cache_key = f"{key_parts[0]}_{key_parts[1]}"
        
        # 캐시 확인
        if cache_key in _global_matching_cache:
            cached_result = _global_matching_cache[cache_key]
            return cached_result['score'], cached_result['reason']
            
        return None
    except Exception as e:
        print(f"메모리 캐시 조회 오류: {e}")
        return None

def save_matching_result_to_cache(user1, user2, score, reason):
    """메모리 캐시에 매칭 결과 저장 (주기적으로만 파일 저장)"""
    global _global_matching_cache, _cache_save_counter
    
    try:
        if _global_matching_cache is None:
            _global_matching_cache = {}
        
        # 정규화된 키 생성
        key_parts = sorted([str(user1['id']), str(user2['id'])])
        cache_key = f"{key_parts[0]}_{key_parts[1]}"
        
        # 메모리 캐시에 저장
        _global_matching_cache[cache_key] = {'score': score, 'reason': reason}
        
        # 카운터 증가 및 주기적 파일 저장 (100개마다)
        _cache_save_counter += 1
        if _cache_save_counter % 100 == 0:
            save_matching_cache(_global_matching_cache)
            print(f"💾 메모리 캐시 파일 저장: {len(_global_matching_cache)}개 항목")
            
    except Exception as e:
        print(f"메모리 캐시 저장 오류: {e}")

def calculate_rule_based_matching(user1, user2):
    """룰 기반 매칭 계산"""
    try:
        # MBTI 호환성 계산
        mbti_score = calculate_mbti_compatibility_score(user1['mbti'], user2['mbti'])

        # 사주 호환성 계산
        saju_score = calculate_saju_compatibility_score(user1['saju_result'], user2['saju_result'])

        # 최종 점수 계산 (가중치 적용)
        final_score = int((mbti_score * 0.6) + (saju_score * 0.4))
        final_score = max(20, min(100, final_score))

        # MBTI와 사주를 종합한 매칭 이유 생성 (140자 제한)
        if final_score >= 85:
            reason = f"{user1['mbti']}와 {user2['mbti']}는 성격적으로 완벽한 조화를 이루며, 사주상 오행의 기운도 서로 보완하여 천생연분의 인연을 만들어갑니다. 깊은 정신적 교감과 운명적 만남이 기대됩니다."
        elif final_score >= 75:
            reason = f"{user1['mbti']}와 {user2['mbti']}는 성격적으로 잘 어울리며, 사주상 기운의 흐름도 긍정적으로 상호작용합니다. 서로를 이해하고 지지하는 안정적이고 조화로운 관계를 만들어갈 수 있어요."
        elif final_score >= 65:
            reason = f"{user1['mbti']}와 {user2['mbti']}는 성격적 특성이 적절히 조화되며, 사주상 오행의 균형도 나쁘지 않은 궁합입니다. 서로 노력한다면 좋은 파트너십을 형성할 수 있습니다."
        elif final_score >= 55:
            reason = f"{user1['mbti']}와 {user2['mbti']}는 기본적인 호환성을 가지고 있으며, 사주상 큰 충돌은 없는 관계입니다. 서로를 이해하려 노력한다면 안정적인 관계 발전이 가능해요."
        else:
            reason = f"{user1['mbti']}와 {user2['mbti']}는 성격적 차이가 있지만, 사주상 서로 다른 기운이 때로는 새로운 시너지를 만들 수 있습니다. 차이점을 존중하며 소통하는 것이 중요합니다."

        return final_score, reason

    except Exception as e:
        print(f"❌ 룰 기반 매칭 계산 오류: {e}")
        return 50, "MBTI 성격 분석과 사주상 기운을 종합해보니 기본적인 호환성을 가진 관계로, 서로를 이해하고 배려한다면 안정적인 관계를 만들어갈 수 있습니다."

def should_use_ai_matching(user1, user2, quick_score):
    """AI 심층 분석을 사용할지 결정"""
    # 70점 이상 쌍들에 대해 AI 분석 진행 (매칭 대상이므로)
    if quick_score >= 70:
        print(f"🤖 AI 심층 분석 진행: {user1['name']} ↔ {user2['name']} (룰 기반: {quick_score}점)")
        return True
    else:
        print(f"⚡ 룰 기반 결과 사용: {user1['name']} ↔ {user2['name']} (점수: {quick_score}점)")
        return False

def perform_ai_matching_analysis(user1, user2, quick_score, model):
    """AI를 활용한 심층 매칭 분석"""
    try:
        # MBTI와 사주 종합 분석 (강제 패턴)
        prompt = f"""
{user1['mbti']}와 {user2['mbti']} 두 사람의 궁합을 분석해주세요.

⚠️ 반드시 이 패턴으로 답변하세요:
"{user1['mbti']}와 {user2['mbti']}는 [MBTI특성]. 사주상 [기운분석]."

⚠️ "사주상"이라는 단어를 반드시 포함해야 합니다.
⚠️ 140자 이하로 작성하세요.

출력 형식:
점수: [70-90점 사이]
이유: {user1['mbti']}와 {user2['mbti']}는 성격적으로 잘 맞습니다. 사주상 오행의 기운이 조화롭게 어울려 좋은 인연을 만들어갈 수 있어요.
"""

        # AI 호출 전 딜레이 (API 한도 방지)
        time.sleep(0.3)  # 더 긴 딜레이로 안정성 확보
        
        print(f"🤖 AI 분석 시작: {user1['name']} ↔ {user2['name']}")
        print(f"📝 전송 프롬프트: {prompt[:100]}...")
        ai_start_time = time.time()
        
        # 타임아웃 강제 설정 (10초)
        import threading
        import queue
        
        # 결과를 담을 큐
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def ai_call_with_timeout():
            try:
                # 안전 필터 완전 비활성화
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
                
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.3,  # 더 창의적인 응답을 위해 약간 증가
                        max_output_tokens=1000,  # 토큰 제한 해결을 위해 감소
                    ),
                    safety_settings=safety_settings
                )
                result_queue.put(response)
            except Exception as e:
                exception_queue.put(e)
        
        # 스레드로 AI 호출 실행
        ai_thread = threading.Thread(target=ai_call_with_timeout)
        ai_thread.daemon = True
        ai_thread.start()
        
        # 10초 타임아웃으로 결과 대기
        ai_thread.join(timeout=10.0)
        
        if ai_thread.is_alive():
            ai_elapsed = time.time() - ai_start_time
            print(f"⏰ AI 호출 타임아웃 ({ai_elapsed:.2f}초) - 강제 중단")
            return quick_score, f"{user1['mbti']}와 {user2['mbti']}는 성격적으로 조화를 이루며, 사주상 기운의 흐름도 긍정적입니다. 서로의 특성이 잘 어울려 좋은 파트너십을 형성할 수 있는 인연이에요."
        
        # 예외 확인
        if not exception_queue.empty():
            raise exception_queue.get()
        
        # 결과 확인
        if result_queue.empty():
            print(f"⚠️ AI 응답 없음 - 알 수 없는 오류")
            return quick_score, f"{user1['mbti']}와 {user2['mbti']}는 성격적으로 조화를 이루며, 사주상 기운의 흐름도 긍정적입니다. 서로의 특성이 잘 어울려 좋은 파트너십을 형성할 수 있는 인연이에요."
        
        response = result_queue.get()
        
        ai_elapsed = time.time() - ai_start_time
        print(f"🤖 AI 응답 완료: {ai_elapsed:.2f}초")
        print(f"🔍 AI 원본 응답: {response.text[:150]}...")
        
        # 토큰 사용량 확인
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            print(f"📊 토큰 사용량 - 입력: {usage.prompt_token_count}, 출력: {usage.candidates_token_count}, 총: {usage.total_token_count}")
        
        # 안전성 검사
        if not response.candidates or len(response.candidates) == 0:
            print(f"⚠️ AI 응답 없음: 안전 필터 차단")
            return quick_score, f"{user1['mbti']}와 {user2['mbti']}는 성격적으로 조화를 이루며, 사주상 기운의 흐름도 긍정적입니다. 서로의 특성이 잘 어울려 좋은 파트너십을 형성할 수 있는 인연이에요."

        candidate = response.candidates[0]
        if candidate.finish_reason != 1:  # 1 = STOP (정상 완료)
            print(f"⚠️ AI 응답 차단됨: finish_reason={candidate.finish_reason}")
            if candidate.finish_reason == 2:
                print(f"🚫 토큰 한도 초과 또는 안전 필터 차단")
            elif candidate.finish_reason == 3:
                print(f"🚫 최대 토큰 길이 초과")
            return quick_score, f"{user1['mbti']}와 {user2['mbti']}는 성격적으로 조화를 이루며, 사주상 기운의 흐름도 긍정적입니다. 서로의 특성이 잘 어울려 좋은 파트너십을 형성할 수 있는 인연이에요."
            

        try:
            ai_response = response.text.strip()
        except:
            print(f"⚠️ AI 응답 텍스트 추출 실패")
            return quick_score, f"{user1['mbti']}와 {user2['mbti']}는 성격적으로 조화를 이루며, 사주상 기운의 흐름도 긍정적입니다. 서로의 특성이 잘 어울려 좋은 파트너십을 형성할 수 있는 인연이에요."

        # AI 응답에서 점수와 이유 추출 (한국어 복원, 멀티라인 처리)
        score_match = re.search(r'점수:\s*(\d+)', ai_response)
        reason_match = re.search(r'이유:\s*(.+?)(?:\n\n|\n\*\*|\*\*|$)', ai_response, re.DOTALL)

        if score_match and reason_match:
            ai_score = int(score_match.group(1))
            ai_reason = reason_match.group(1).strip()

            # 룰 기반과 AI 결과 조합
            final_score = int((quick_score * 0.7) + (ai_score * 0.3))
            final_score = max(20, min(100, final_score))

            # 마크다운 제거 및 자연스러운 문장 단위로 자르기
            clean_reason = ai_reason.replace('**', '').replace('*', '').replace('#', '').strip()
            
            # 사주 키워드가 없으면 강제로 추가
            if '사주상' not in clean_reason and '오행' not in clean_reason:
                print("⚠️ AI가 사주 분석을 누락함 - 강제 추가")
                # MBTI 분석 뒤에 사주 내용 추가
                if '. ' in clean_reason:
                    parts = clean_reason.split('. ', 1)
                    clean_reason = f"{parts[0]}. 사주상 오행의 기운도 조화롭게 어울려 좋은 인연을 만들어갈 수 있어요."
                else:
                    # 마지막에 사주 내용 추가
                    clean_reason = clean_reason.rstrip('.') + ". 사주상 기운의 조화도 긍정적입니다."
            
            if len(clean_reason) <= 140:
                final_reason = clean_reason
            else:
                # 140자 근처에서 자연스러운 문장 끝을 찾기
                truncated = clean_reason[:140]
                # 마지막 완전한 문장 찾기 (마침표, 느낌표, 물음표, '요', '다' 등으로 끝나는)
                sentence_endings = ['.', '!', '?', '요', '다', '음', '네', '죠']
                last_sentence_end = -1
                
                for ending in sentence_endings:
                    pos = truncated.rfind(ending)
                    if pos > last_sentence_end:
                        last_sentence_end = pos
                
                if last_sentence_end > 80:  # 너무 짧지 않으면 문장 단위로 자르기
                    final_reason = clean_reason[:last_sentence_end + 1]
                else:
                    # 문장 끝을 찾지 못하면 140자로 자르고 마침표 추가
                    final_reason = clean_reason[:135] + '요.'
            
            print(f"✂️ 최종 결과: '{final_reason}' (길이: {len(final_reason)}자)")

            print(f"✅ AI 매칭 분석 완료: {user1['name']} ↔ {user2['name']} (최종 점수: {final_score})")
            return final_score, final_reason
        else:
            # AI 분석 실패 시 룰 기반 결과 사용
            print(f"⚠️ AI 분석 결과 파싱 실패, 룰 기반 결과 사용")
            return quick_score, f"{user1['mbti']}와 {user2['mbti']}는 성격적으로 조화를 이루며, 사주상 기운의 흐름도 긍정적입니다. 서로의 특성이 잘 어울려 좋은 파트너십을 형성할 수 있는 인연이에요."

    except Exception as e:
        error_msg = str(e).lower()
        if "quota" in error_msg or "limit" in error_msg:
            print(f"⚠️ AI API 할당량 초과, 룰 기반 결과 사용")
        elif "timeout" in error_msg:
            print(f"⚠️ AI API 타임아웃, 룰 기반 결과 사용")
        else:
            print(f"❌ AI 매칭 분석 오류: {e}")
        return quick_score, "사주의 기운과 성격을 살펴보니 기본적인 조화는 이루고 있는 인연입니다"

# 캐시 초기화
# 캐시를 강제로 빈 상태로 시작 (구 형식 문제 해결)
saju_analysis_cache = {}
# saju_analysis_cache = load_saju_cache()  # 임시로 비활성화
matching_cache = load_matching_cache()

def calculate_saju_pillars(year, month, day, hour):
    # 캐시 키 생성
    cache_key = (year, month, day, hour)

    # 캐시 확인 (이미 계산된 결과가 있으면 즉시 반환)
    if cache_key in saju_cache:
        return saju_cache[cache_key]
    # 천간과 지지 상수 (최적화된 배열)
    cheon_gan = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
    ji_ji = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]

    # 연주 계산 (수학적 계산으로 즉시 완료)
    year_gan_index = (year - 4) % 10
    year_ji_index = (year - 4) % 12
    year_pillar = cheon_gan[year_gan_index] + ji_ji[year_ji_index]

    # 월주 계산 (lookup table로 즉시 완료)
    month_starts = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
    month_index = month_starts.index(month)
    month_gan_key = cheon_gan[year_gan_index]

    # 초고속 간지 오프셋 매핑
    gan_offset_map = {
        "갑": 0, "기": 0,
        "을": 2, "경": 2,
        "병": 4, "신": 4,
        "정": 6, "임": 6,
        "무": 8, "계": 8
    }
    gan_offset = gan_offset_map.get(month_gan_key, 8)

    # 월주 lookup table (미리 계산된 값들)
    month_pillars = [
        "병인", "정묘", "무진", "기사", "경오", "신미", "임신", "계유", "갑술", "을해", "병자", "정축",
        "무인", "기묘", "경진", "신사", "임오", "계미", "갑신", "을유", "병술", "정해", "무자", "기축",
        "경인", "신묘", "임진", "계사", "갑오", "을미", "병신", "정유", "무술", "기해", "경자", "신축",
        "임인", "계묘", "갑진", "을사", "병오", "정미", "무신", "기유", "경술", "신해", "임자", "계축",
        "갑인", "을묘", "병진", "정사", "무오", "기미", "경신", "신유", "임술", "계해", "갑자", "을축"
    ]

    # 월주 인덱스 계산 및 lookup
    month_pillar_index = (year_gan_index * 12 + month_index) % 60
    month_pillar = month_pillars[month_pillar_index]

    # 일주 계산 (수학적 공식으로 즉시 계산 - 초고속)
    # 2000년 1월 1일 (토요일) 기준으로 총 일수 계산
    base_year = 2000
    base_month = 1
    base_day = 1

    # 연도별 일수 계산 (윤년 고려)
    total_days = (year - base_year) * 365 + (year - base_year) // 4 - (year - base_year) // 100 + (year - base_year) // 400

    # 월별 누적 일수 (미리 계산된 값 사용)
    cumulative_days = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]

    # 윤년 보정
    leap_year_adjust = 1 if ((year % 4 == 0 and year % 100 != 0) or year % 400 == 0) and month > 2 else 0

    total_days += cumulative_days[month - 1] + leap_year_adjust + (day - 1)

    # 간지 계산 (수학적 공식)
    day_gan_index = (total_days + 6) % 10  # 갑자일 기준
    day_ji_index = (total_days + 8) % 12   # 자일 기준

    day_pillar = cheon_gan[day_gan_index] + ji_ji[day_ji_index]

    # 시주 계산 (lookup table로 즉시 완료)
    # 시간별 지지 매핑 (더욱 효율적인 버전)
    time_ji_indices = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11]
    time_ji_index = time_ji_indices[hour]

    # 시주 간지 오프셋
    day_gan_key = cheon_gan[day_gan_index]
    time_gan_offset = gan_offset_map.get(day_gan_key, 8)
    time_gan_index = (time_gan_offset + time_ji_index) % 10

    time_pillar = cheon_gan[time_gan_index] + ji_ji[time_ji_index]

    # 계산 결과 캐시에 저장 (다음 호출 시 즉시 반환)
    result = (year_pillar, month_pillar, day_pillar, time_pillar)
    saju_cache[cache_key] = result

    return result
# --- [사주 계산 함수 부분 끝] ---

# 프로젝트 루트 경로 계산 (api 폴더에서 한 단계 위로)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__,
            template_folder=os.path.join(PROJECT_ROOT, 'templates'),
            static_folder=os.path.join(PROJECT_ROOT, 'static'))
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here-change-this-in-production')

# Supabase 연결 설정
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')

# Web Push VAPID 설정
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY')
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY')
VAPID_EMAIL = os.getenv('VAPID_EMAIL')
APP_URL = os.getenv('APP_URL', 'http://localhost:5000')

print(f"🔧 환경변수 확인:")
print(f"   SUPABASE_URL: {'설정됨' if SUPABASE_URL else '없음'}")
print(f"   SUPABASE_ANON_KEY: {'설정됨' if SUPABASE_ANON_KEY else '없음'}")
print(f"   GOOGLE_API_KEY: {'설정됨' if os.getenv('GOOGLE_API_KEY') else '없음'}")
print(f"   VAPID_PRIVATE_KEY: {'설정됨' if VAPID_PRIVATE_KEY else '없음'}")
print(f"   VAPID_PUBLIC_KEY: {'설정됨' if VAPID_PUBLIC_KEY else '없음'}")
print(f"   VAPID_EMAIL: {'설정됨' if VAPID_EMAIL else '없음'}")

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

-- push_subscriptions 테이블 생성 (푸시 알림용)
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id SERIAL PRIMARY KEY,
    device_token TEXT NOT NULL UNIQUE,
    endpoint TEXT NOT NULL,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    user_id INTEGER REFERENCES results(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- user_notifications 테이블 생성 (알림 기록용)
CREATE TABLE IF NOT EXISTS user_notifications (
    id SERIAL PRIMARY KEY,
    device_token TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    data JSONB DEFAULT '{}',
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    read_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (device_token) REFERENCES push_subscriptions(device_token) ON DELETE CASCADE
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_results_student_id ON results(student_id);
CREATE INDEX IF NOT EXISTS idx_results_is_matched ON results(is_matched);
CREATE INDEX IF NOT EXISTS idx_matches_user1_id ON matches(user1_id);
CREATE INDEX IF NOT EXISTS idx_matches_user2_id ON matches(user2_id);
CREATE INDEX IF NOT EXISTS idx_matches_score ON matches(compatibility_score DESC);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_device_token ON push_subscriptions(device_token);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user_id ON push_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_notifications_device_token ON user_notifications(device_token);

-- 시퀀스 재설정 (중복 ID 문제 해결)
SELECT setval('results_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM results), false);
SELECT setval('matches_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM matches), false);
SELECT setval('push_subscriptions_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM push_subscriptions), false);
SELECT setval('user_notifications_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM user_notifications), false);
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

# --- [푸시 알림 관련 함수들] ---

def generate_device_token():
    """고유한 디바이스 토큰 생성"""
    return str(uuid.uuid4())

def get_saju_element_analysis(year_p, month_p, day_p, time_p):
    """사주 원소 분석 및 해석"""
    
    # 천간과 지지의 오행 분석
    def get_heavenly_stem_element(stem):
        elements = {
            '갑': '목', '을': '목',
            '병': '화', '정': '화', 
            '무': '토', '기': '토',
            '경': '금', '신': '금',
            '임': '수', '계': '수'
        }
        return elements.get(stem, '토')
    
    def get_earthly_branch_element(branch):
        elements = {
            '자': '수', '축': '토', '인': '목', '묘': '목',
            '진': '토', '사': '화', '오': '화', '미': '토',
            '신': '금', '유': '금', '술': '토', '해': '수'
        }
        return elements.get(branch, '토')
    
    # 각 주의 천간과 지지 분리
    year_stem, year_branch = year_p[0], year_p[1]
    month_stem, month_branch = month_p[0], month_p[1]
    day_stem, day_branch = day_p[0], day_p[1]
    time_stem, time_branch = time_p[0], time_p[1]
    
    # 오행 분석
    elements = [
        get_heavenly_stem_element(year_stem), get_earthly_branch_element(year_branch),
        get_heavenly_stem_element(month_stem), get_earthly_branch_element(month_branch),
        get_heavenly_stem_element(day_stem), get_earthly_branch_element(day_branch),
        get_heavenly_stem_element(time_stem), get_earthly_branch_element(time_branch)
    ]
    
    # 오행별 개수 계산
    element_count = {'목': 0, '화': 0, '토': 0, '금': 0, '수': 0}
    for element in elements:
        element_count[element] += 1
    
    # 가장 강한 오행과 부족한 오행 찾기
    strongest_element = max(element_count, key=element_count.get)
    weakest_element = min(element_count, key=element_count.get)
    
    # 일간(본인의 기본 성향) 분석
    day_element = get_heavenly_stem_element(day_stem)
    
    # 성향 분석
    element_traits = {
        '목': '성장지향적이고 창의적이며, 유연성과 포용력이 뛰어남',
        '화': '열정적이고 활동적이며, 리더십과 추진력이 강함',
        '토': '안정적이고 신뢰할 수 있으며, 포용력과 인내심이 뛰어남',
        '금': '의지가 강하고 정의로우며, 결단력과 실행력이 뛰어남',
        '수': '지혜롭고 유연하며, 적응력과 통찰력이 뛰어남'
    }
    
    # 궁합 분석
    element_compatibility = {
        '목': '화(상생), 수(상생) 기운과 조화로움',
        '화': '토(상생), 목(상생) 기운과 조화로움',
        '토': '금(상생), 화(상생) 기운과 조화로움',
        '금': '수(상생), 토(상생) 기운과 조화로움',
        '수': '목(상생), 금(상생) 기운과 조화로움'
    }
    
    # 계절 영향 분석 (월지 기준)
    season_analysis = {
        '인': '봄 기운 - 새로운 시작과 성장의 에너지',
        '묘': '봄 기운 - 창의성과 활력이 넘치는 성향',
        '진': '늦봄 기운 - 안정적이면서도 변화를 추구',
        '사': '여름 기운 - 열정적이고 활발한 성격',
        '오': '여름 기운 - 리더십과 카리스마가 뛰어남',
        '미': '늦여름 기운 - 따뜻하고 포용력이 있음',
        '신': '가을 기운 - 차분하고 분석적인 성향',
        '유': '가을 기운 - 완벽주의적이고 섬세함',
        '술': '늦가을 기운 - 신중하고 계획적인 성격',
        '자': '겨울 기운 - 깊이 있고 지혜로운 성향',
        '축': '겨울 기운 - 인내심이 강하고 현실적',
        '해': '늦겨울 기운 - 유연하고 적응력이 뛰어남'
    }
    
    season_info = season_analysis.get(month_branch, '균형 잡힌 기운')
    
    # 특별한 조합 분석
    special_combinations = []
    if year_stem == day_stem:
        special_combinations.append("연일 비견 - 자주성이 강하고 독립적인 성향")
    if month_stem == day_stem:
        special_combinations.append("월일 비견 - 사회성이 뛰어나고 활동적")
    if time_stem == day_stem:
        special_combinations.append("일시 비견 - 목표 달성 능력이 뛰어남")
    
    special_info = "\n• 특별한 조합: " + ", ".join(special_combinations) if special_combinations else ""
    
    analysis = f"""📊 사주 오행 분석
• 일간(본성): {day_stem}({day_element}) - {element_traits[day_element]}
• 월지 기운: {month_branch} - {season_info}
• 강한 기운: {strongest_element}({element_count[strongest_element]}개) - 이 기운의 특성이 두드러짐
• 보완할 기운: {weakest_element}({element_count[weakest_element]}개) - {element_traits[weakest_element]} 특성을 기르면 좋음{special_info}
• 궁합 기운: {element_compatibility[day_element]}"""
    
    return analysis

def send_push_notification(subscription_info, title, body, data=None):
    """푸시 알림 전송 - Python pywebpush 라이브러리 사용"""
    try:
        print(f"🔔 푸시 알림 전송 시도: {title}")
        print(f"📄 Body: {body}")
        
        # 환경변수에서 VAPID 키 가져오기
        VAPID_EMAIL = os.getenv('VAPID_EMAIL')
        VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY')
        VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY')
        APP_URL = os.getenv('APP_URL', 'https://love-code-eta.vercel.app/')
        
        if not all([VAPID_EMAIL, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY]):
            print("❌ VAPID 키가 설정되지 않았습니다.")
            print(f"Email: {bool(VAPID_EMAIL)}, Public: {bool(VAPID_PUBLIC_KEY)}, Private: {bool(VAPID_PRIVATE_KEY)}")
            return False
        
        print(f"🔑 VAPID 이메일: {VAPID_EMAIL}")
        print(f"🔑 VAPID 공개키: {VAPID_PUBLIC_KEY[:20]}...")
        
        # 구독 정보 검증
        endpoint = subscription_info.get('endpoint', '')
        p256dh = subscription_info.get('keys', {}).get('p256dh', '')
        auth = subscription_info.get('keys', {}).get('auth', '')

        if not all([endpoint, p256dh, auth]):
            print("❌ 구독 정보가 불완전합니다")
            print(f"Endpoint: {bool(endpoint)}, p256dh: {bool(p256dh)}, auth: {bool(auth)}")
            return False

        print(f"📤 푸시 알림 전송 시도: {endpoint[:50]}...")
        
        # 알림 페이로드 생성
        payload = json.dumps({
            "title": title,
            "body": body,
            "icon": f"{APP_URL}/static/img/LOVECODE_ICON.png",
            "badge": f"{APP_URL}/static/img/LOVECODE_ICON.png",
            "data": data or {},
            "requireInteraction": True,
            "tag": "match-notification"
        })
        
        # VAPID 클레임 설정
        vapid_claims = {
            "sub": f"mailto:{VAPID_EMAIL}" if not VAPID_EMAIL.startswith('mailto:') else VAPID_EMAIL
        }
        
        print("📤 Python pywebpush로 푸시 알림 전송 시도...")
        print(f"📝 Payload: {payload}")
        
        # 푸시 알림 전송
        response = webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=vapid_claims,
            ttl=43200  # 12시간
        )
        
        print(f"✅ 푸시 알림 전송 성공! 응답 코드: {response.status_code}")
        return True
        
    except Exception as e:
        print(f"❌ 푸시 알림 전송 중 오류: {e}")
        print(f"오류 타입: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

def save_push_subscription(device_token, subscription_data, user_id=None):
    """푸시 구독 정보 저장"""
    try:
        supabase.table('push_subscriptions').upsert({
            'device_token': device_token,
            'endpoint': subscription_data['endpoint'],
            'p256dh': subscription_data['keys']['p256dh'],
            'auth': subscription_data['keys']['auth'],
            'user_id': user_id
        }).execute()
        return True
    except Exception as e:
        print(f"❌ 푸시 구독 저장 실패: {e}")
        return False

def get_push_subscription(device_token):
    """푸시 구독 정보 조회"""
    try:
        response = supabase.table('push_subscriptions').select('*').eq('device_token', device_token).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"❌ 푸시 구독 조회 실패: {e}")
        return None

def send_matching_notification(user_id):
    """매칭 완료 알림 전송"""
    try:
        print(f"🔔 사용자 {user_id}에게 매칭 알림 전송 시도")

        # 사용자의 푸시 구독 정보 조회
        subscriptions = supabase.table('push_subscriptions').select('*').eq('user_id', user_id).execute()
        print(f"📊 조회된 구독 정보: {len(subscriptions.data) if subscriptions.data else 0}개")

        if not subscriptions.data:
            print(f"⚠️ 사용자 {user_id}의 푸시 구독 정보가 없습니다.")
            return False

        # 매칭 결과 조회
        matches = supabase.table('matches').select('*').or_(
            f'user1_id.eq.{user_id},user2_id.eq.{user_id}'
        ).order('compatibility_score', desc=True).limit(5).execute()
        print(f"📊 매칭 결과: {len(matches.data) if matches.data else 0}개")

        if not matches.data:
            print(f"⚠️ 사용자 {user_id}의 매칭 결과가 없습니다. 대기 알림을 전송합니다.")
            
            # 매칭 결과가 없을 때는 대기 알림 전송
            title = "⏳ 매칭 진행 중입니다"
            body = "아직 매칭이 완료되지 않았어요. 조금 더 기다려주세요!"
            
            success_count = 0
            for i, subscription in enumerate(subscriptions.data):
                subscription_info = {
                    'endpoint': subscription['endpoint'],
                    'keys': {
                        'p256dh': subscription['p256dh'],
                        'auth': subscription['auth']
                    }
                }
                
                try:
                    result = send_push_notification(
                        subscription_info,
                        title,
                        body,
                        data={'action': 'view_home', 'user_id': user_id}
                    )
                    
                    if result:
                        success_count += 1
                        print(f"✅ 대기 알림 {i+1}번 전송 성공")
                except Exception as sub_error:
                    print(f"❌ 대기 알림 {i+1}번 전송 중 오류: {sub_error}")
            
            return success_count > 0

        # 알림 전송
        title = "🎉 사주 매칭이 완료되었습니다!"
        body = f"총 {len(matches.data)}명의 매칭 상대를 찾았어요. 확인해보세요!"

        success_count = 0
        for i, subscription in enumerate(subscriptions.data):
            print(f"📤 구독 {i+1}번 전송 시도: {subscription['device_token'][:8]}...")

            subscription_info = {
                'endpoint': subscription['endpoint'],
                'keys': {
                    'p256dh': subscription['p256dh'],
                    'auth': subscription['auth']
                }
            }

            try:
                result = send_push_notification(
                    subscription_info,
                    title,
                    body,
                    data={'action': 'view_matches', 'user_id': user_id}
                )

                if result:
                    success_count += 1
                    print(f"✅ 구독 {i+1}번 전송 성공")

                    # 알림 기록 저장
                    supabase.table('user_notifications').insert({
                        'device_token': subscription['device_token'],
                        'title': title,
                        'body': body,
                        'data': json.dumps({'action': 'view_matches', 'user_id': user_id})
                    }).execute()
                else:
                    print(f"❌ 구독 {i+1}번 전송 실패")

            except Exception as sub_error:
                print(f"❌ 구독 {i+1}번 전송 중 오류: {sub_error}")

        print(f"🎯 최종 결과: 사용자 {user_id}에게 {success_count}/{len(subscriptions.data)}개의 푸시 알림 전송 성공")
        return success_count > 0

    except Exception as e:
        print(f"❌ 매칭 알림 전송 실패: {e}")
        import traceback
        print(f"❌ 상세 오류: {traceback.format_exc()}")
        return False

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
        test_models = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-2.5-flash']
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

@app.route('/admin/api-quota')
def check_api_quota():
    """API 할당량 및 토큰 사용량 확인"""
    if not session.get('logged_in'):
        return jsonify({'error': '로그인이 필요합니다'}), 401

    try:
        if not GOOGLE_API_KEY:
            return jsonify({'error': 'Google AI API 키가 설정되지 않았습니다.'}), 500
        
        genai.configure(api_key=GOOGLE_API_KEY)
        
        # 간단한 테스트 요청으로 토큰 사용량 확인
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(
            "Hello",
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=10,
                temperature=0.1
            )
        )
        
        quota_info = {
            'status': 'success',
            'test_response': response.text if response.text else 'No response',
            'finish_reason': response.candidates[0].finish_reason if response.candidates else 'No candidates',
            'finish_reason_description': {
                1: 'STOP (정상 완료)',
                2: 'MAX_TOKENS (토큰 한도 도달) 또는 SAFETY (안전 필터)',
                3: 'RECITATION (반복/인용)',
                4: 'OTHER (기타)'
            }
        }
        
        # 토큰 사용량 정보
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            quota_info['token_usage'] = {
                'prompt_tokens': usage.prompt_token_count,
                'completion_tokens': usage.candidates_token_count,
                'total_tokens': usage.total_token_count
            }
        else:
            quota_info['token_usage'] = {
                'message': '토큰 사용량 정보를 가져올 수 없습니다'
            }
        
        return jsonify(quota_info)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': '할당량 확인 중 오류가 발생했습니다.'
        }), 500

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

def perform_batch_matching(user_group_1, user_group_2, model, batch_name="", timeout_callback=None):
    """상위 3명 제한 최적화 매칭 (룰 기반 → 상위 3명 선별 → AI 심층 분석)"""
    print(f"🚀 {batch_name} 매칭 시작: {len(user_group_1)}명 × {len(user_group_2)}명")
    print("📊 전략: 전체 룰 기반 계산 → 인당 상위 3명 선별 → AI 심층 분석")
    
    last_progress_time = time.time()
    
    # 1단계: 각 사용자에 대해 모든 상대방과의 룰 기반 점수 계산
    print(f"📊 1단계: 룰 기반 점수 계산 중...")
    user_candidates = {}  # user1_id -> [(user2, score, reason), ...]

    for i, user1 in enumerate(user_group_1):
        current_time = time.time()
        
        # 타임아웃 확인
        if timeout_callback and timeout_callback(current_time):
            print(f"⏰ 타임아웃 감지: {batch_name} 1단계 중단")
            break
        
        # 무응답 감지 (7초로 단축)
        if current_time - last_progress_time > 7:
            print(f"⚠️ 무응답 감지: {batch_name} 1단계 7초 동안 진행 없음")
            print(f"🔄 현재 시간: {current_time:.2f}, 마지막 진행: {last_progress_time:.2f}")
            break
        
        # 진행률 표시 (10개마다)
        if i % 10 == 0:
            progress = (i / len(user_group_1)) * 100
            print(f"📊 룰 기반 계산 진행률: {progress:.1f}% ({i}/{len(user_group_1)})")
            last_progress_time = current_time
        
        candidates = []
        
        for user2 in user_group_2:
            if user1['id'] == user2['id']:
                continue  # 자기 자신 제외
            
            # 캐시 없이 바로 룰 기반 계산 (최대 속도)
            score, reason = calculate_rule_based_matching(user1, user2)
            print(f"⚡ 룰 기반 계산: {user1['name']} ↔ {user2['name']} (점수: {score})")
            
            # 70점 이상만 후보에 추가
            if score >= 70:
                candidates.append((user2, score, reason))
        
        # 점수 높은 순으로 정렬하여 상위 3명 선택
        candidates.sort(key=lambda x: x[1], reverse=True)
        top_3_candidates = candidates[:3]
        
        user_candidates[user1['id']] = top_3_candidates
        
        if top_3_candidates:
            print(f"🎯 {user1['name']} 상위 3명 선별: {[(c[0]['name'], c[1]) for c in top_3_candidates]}")
        
        # 진행 시간 업데이트
        last_progress_time = time.time()
    
    # 2단계: 선별된 상위 3명에 대해서만 AI 심층 분석
    print(f"📊 2단계: 선별된 후보들 AI 심층 분석...")
    
    matches = []
    ai_analysis_count = 0
    
    total_users = len(user_group_1)
    processed_users = 0
    
    for user1 in user_group_1:
        processed_users += 1
        current_time = time.time()
        
        print(f"👤 사용자 {processed_users}/{total_users} 처리 중: {user1['name']} ({(processed_users/total_users)*100:.1f}%)")
        
        # 타임아웃 확인
        if timeout_callback and timeout_callback(current_time):
            print(f"⏰ 타임아웃 감지: {batch_name} AI 분석 중단")
            break
        
        candidates = user_candidates.get(user1['id'], [])
        
        for user2, rule_score, rule_reason in candidates:
            print(f"🤖 AI 심층 분석: {user1['name']} ↔ {user2['name']} (룰 기반: {rule_score}점)")
            ai_analysis_count += 1
            
            # AI 호출 간격 조절 (메모리 및 API 안정성)
            if ai_analysis_count % 5 == 0:  # 5번마다로 빈도 증가
                time.sleep(1.0)  # 더 긴 휴식으로 안정성 확보
                gc.collect()  # 가비지 컬렉션으로 메모리 정리
                print(f"⏸️ AI 분석 휴식: {ai_analysis_count}회 완료 (메모리 정리)")
                
                # 매 10회마다 상태 로그만 출력
                if ai_analysis_count % 10 == 0:
                    print(f"📊 AI 분석 진행: {ai_analysis_count}회 완료")
            
            # 매 AI 호출마다 진행 상황 출력 (무한 대기 방지)
            print(f"🤖 AI 호출 준비: {user1['name']} ↔ {user2['name']} ({ai_analysis_count}번째)")
            
            # AI 심층 분석 조건 확인 후 수행
            if should_use_ai_matching(user1, user2, rule_score):
                final_score, final_reason = perform_ai_matching_analysis(user1, user2, rule_score, model)
            else:
                # 룰 기반 결과 사용
                final_score, final_reason = rule_score, rule_reason
            
            # 캐시 저장 완전 제거 - 속도 최우선
            
            # 매칭 결과에 추가
            matches.append({
                    'user1_id': user1['id'],
                    'user2_id': user2['id'],
                    'user1_name': user1['name'],
                    'user2_name': user2['name'],
                'compatibility_score': final_score,
                'matching_reason': final_reason
            })
            print(f"✅ {batch_name}: {user1['name']} ↔ {user2['name']} (최종 점수: {final_score})")
            
            # 진행 시간 업데이트
            last_progress_time = time.time()
    
    print(f"🏁 {batch_name} 매칭 완료: {len(matches)}개 결과 (AI 분석: {ai_analysis_count}회)")
    return matches

@app.route('/admin/matching', methods=['POST'])
def perform_matching():
    # 로컬 개발 환경에서 세션 체크 우회 (디버깅용)
    import os
    if os.getenv('FLASK_ENV') == 'development':
        print("🔧 개발 환경에서 세션 체크 우회")
    elif not session.get('logged_in'):
        return jsonify({'error': '로그인이 필요합니다'}), 401

    # 매칭 시작 시간 기록 및 타임아웃 감지
    matching_start_time = time.time()
    max_matching_time = 600  # 10분 타임아웃
    last_activity_time = matching_start_time

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

        # 대규모 매칭 지원을 위한 사용자 수 제한 해제
        total_users = len(new_users) + len(existing_users)
        # 제한 제거 - 대규모 매칭 가능
        print(f"📊 대규모 매칭 모드: 총 {total_users}명 처리 (제한 없음)")

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
        required_keys = ['id', 'name', 'mbti', 'saju_result', 'ai_analysis', 'gender']
        for i, user in enumerate(new_users + existing_users):
            print(f"사용자 {i} 데이터: 타입={type(user)}, 키={list(user.keys()) if isinstance(user, dict) else 'N/A'}")

            # 딕셔너리 타입 확인
            if not isinstance(user, dict):
                print(f"⚠️ 사용자 {i} 데이터가 딕셔너리가 아닙니다: 타입={type(user)}")
                continue

            # 필수 키 존재 확인
            missing_keys = [key for key in required_keys if key not in user]
            if missing_keys:
                print(f"⚠️ 사용자 {i} 데이터에 필수 키가 없습니다. 누락된 키: {missing_keys}")
                continue

            print(f"✅ 사용자 {i} 데이터 구조 정상: {user['name']} ({user['id']})")

        matches = []
        all_pair_scores = []  # 모든 쌍의 호환성 점수를 저장

        # AI를 사용한 매칭 수행
        print("🤖 AI 매칭 분석 시작...")
        # API 키 확인
        if not GOOGLE_API_KEY:
            return jsonify({'error': 'Google AI API 키가 설정되지 않아 매칭을 수행할 수 없습니다. 관리자에게 문의해주세요.'}), 500

        # Vercel 환경 최적화: 간단한 모델만 사용
        model_names = ['gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-pro']  # 2.0-Flash 우선 (안정성 검증됨)
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

        # 1. 최적화된 배치 매칭 분석 수행
        print("💑 최적화된 매칭 분석 시작...")
        all_matches = []

        # 타임아웃 체크 함수 정의
        def check_timeout(current_time):
            elapsed = current_time - matching_start_time
            if elapsed > max_matching_time:
                print(f"⏰ 매칭 타임아웃: {elapsed:.1f}초 경과 (제한: {max_matching_time}초)")
                return True
            return False

        # 새로운 남자 × 기존 여자 매칭
        if new_males and existing_females:
            print(f"🚀 남자↔여자 매칭 시작... ({len(new_males)}×{len(existing_females)})")
            male_female_matches = perform_batch_matching(
                new_males, existing_females, model, "남자↔여자", check_timeout
            )
            all_matches.extend(male_female_matches)
            
            # 중간 타임아웃 체크
            if check_timeout(time.time()):
                raise TimeoutError("매칭 처리 시간이 초과되었습니다")

        # 새로운 여자 × 기존 남자 매칭  
        if new_females and existing_males:
            print(f"🚀 여자↔남자 매칭 시작... ({len(new_females)}×{len(existing_males)})")
            female_male_matches = perform_batch_matching(
                new_females, existing_males, model, "여자↔남자", check_timeout
            )
            all_matches.extend(female_male_matches)
            
            # 중간 타임아웃 체크
            if check_timeout(time.time()):
                raise TimeoutError("매칭 처리 시간이 초과되었습니다")

        # 새로운 사용자들끼리 매칭
        if new_males and new_females:
            print(f"🚀 새로운사용자내 매칭 시작... ({len(new_males)}×{len(new_females)})")
            internal_matches = perform_batch_matching(
                new_males, new_females, model, "새로운사용자내", check_timeout
            )
            all_matches.extend(internal_matches)

        # 모든 매칭 결과를 all_pair_scores 형식으로 변환
        all_pair_scores = []
        for match in all_matches:
                    all_pair_scores.append({
                'user1_id': match['user1_id'],
                'user2_id': match['user2_id'],
                'user1_name': match['user1_name'],
                'user2_name': match['user2_name'],
                'compatibility_score': match['compatibility_score'],
                'matching_reason': match['matching_reason']
            })

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

        print(f"🎯 최종 선정된 매칭 수: {len(unique_matches)}개")

        # 3. 선정된 매칭 결과들을 Supabase에 저장 (upsert로 중복 방지)
        inserted_count = 0
        for match in unique_matches:
            try:
                result = supabase.table('matches').upsert({
                    'user1_id': match['user1_id'],
                    'user2_id': match['user2_id'],
                    'compatibility_score': match['compatibility_score'],
                    'matching_reason': match['matching_reason']
                }).execute()
                inserted_count += 1
                print(f"✅ 매칭 저장: {match['user1_id']} ↔ {match['user2_id']} (점수: {match['compatibility_score']})")
            except Exception as e:
                print(f"⚠️ 매칭 저장 실패 {match['user1_id']} ↔ {match['user2_id']}: {e}")
                continue

        print(f"📊 매칭 저장 완료: {inserted_count}/{len(unique_matches)}개 성공")

        # 매칭 결과를 응답용으로도 저장
        # 모든 사용자들에서 이름 찾기
        all_users_for_lookup = new_users + existing_users
        for match in unique_matches:
            matches.append({
                'user1': {'id': match['user1_id'], 'name': next(u['name'] for u in all_users_for_lookup if u['id'] == match['user1_id'])},
                'user2': {'id': match['user2_id'], 'name': next(u['name'] for u in all_users_for_lookup if u['id'] == match['user2_id'])},
                'compatibility_score': match['compatibility_score'],
                'reason': match['matching_reason']
            })

        # 매칭 분석에 참여한 새로운 사용자들의 is_matched를 TRUE로 업데이트
        # (새로운 사용자만 매칭 분석에 참여했으므로 새로운 사용자들의 상태만 변경)
        new_user_ids = set()
        for user in new_users:  # 새로운 사용자들
            new_user_ids.add(user['id'])

        if new_user_ids:
            # 새로운 사용자들의 is_matched를 TRUE로 업데이트
            for user_id in new_user_ids:
                supabase.table('results').update({'is_matched': True}).eq('id', user_id).execute()

                # 매칭 완료 푸시 알림 전송
                send_matching_notification(user_id)

        # 최종 실행 시간 계산
        total_time = time.time() - matching_start_time
        
        # 응답 객체 구성 (JSON 직렬화 안전)
        response_data = {
            'success': True,
            'message': f'매칭이 완료되었습니다. 70점 이상인 매칭 결과만 선정하여 총 {len(matches)}개의 매칭 결과를 생성했습니다.',
            'matches_count': len(matches),
            'execution_time': round(total_time, 2),
            'matches': matches
        }
        
        print(f"✅ 매칭 완료: {len(matches)}개 결과, 실행시간: {total_time:.2f}초")
        
        return jsonify(response_data)

    except TimeoutError as e:
        print(f"⏰ 매칭 타임아웃 발생: {str(e)}")
        return jsonify({
            'success': False,
            'error': '매칭 처리 시간이 초과되었습니다',
            'message': '처리 시간이 10분을 초과했습니다. 사용자 수를 줄여서 다시 시도해주세요.',
            'timeout': True
        }), 408

    except Exception as e:
        # 실행 시간 계산
        elapsed_time = time.time() - matching_start_time

        print(f"❌ 최종 매칭 처리 중 치명적 오류 발생: {str(e)}")
        print(f"❌ 오류 타입: {type(e).__name__}")
        print(f"❌ 실행 시간: {elapsed_time:.2f}초")
        
        import traceback
        print(f"❌ 상세 오류: {traceback.format_exc()}")

        # 오류 유형별 친화적 메시지
        error_message = '매칭 처리 중 오류가 발생했습니다'
        if "timeout" in str(e).lower() or "time" in str(e).lower():
            error_message = '처리 시간이 초과되었습니다. 사용자 수를 줄여서 다시 시도해주세요.'
        elif "quota" in str(e).lower() or "limit" in str(e).lower():
            error_message = 'AI API 사용량 제한에 도달했습니다. 잠시 후 다시 시도해주세요.'
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            error_message = '네트워크 연결에 문제가 있습니다. 다시 시도해주세요.'
        elif "json" in str(e).lower():
            error_message = '데이터 처리 중 오류가 발생했습니다. 다시 시도해주세요.'

        return jsonify({
            'success': False,
            'error': error_message,
            'error_type': type(e).__name__,
            'execution_time': round(elapsed_time, 2)
        }), 500

@app.route('/admin/matching/results')
def get_matching_results():
    # 로컬 개발 환경에서 세션 체크 우회 (디버깅용)
    import os
    if os.getenv('FLASK_ENV') == 'development':
        print("🔧 개발 환경에서 세션 체크 우회")
    elif not session.get('logged_in'):
        return jsonify({'error': '로그인이 필요합니다'}), 401

    try:
        print("🔍 매칭 결과 조회 시작")
        
        # Supabase에서 매칭 결과 조회 (모든 결과 조회)
        matches_response = supabase.table('matches').select('*').order('compatibility_score', desc=True).order('created_at', desc=True).execute()
        
        print(f"📊 조회된 매칭 결과: {len(matches_response.data)}개")

        results = []
        for match in matches_response.data:
            try:
                # 각 사용자 정보를 개별적으로 조회
                user1_response = supabase.table('results').select('name, mbti, instagram_id').eq('id', match['user1_id']).execute()
                user2_response = supabase.table('results').select('name, mbti, instagram_id').eq('id', match['user2_id']).execute()

                user1_data = user1_response.data[0] if user1_response.data else {'name': 'Unknown', 'mbti': '', 'instagram_id': ''}
                user2_data = user2_response.data[0] if user2_response.data else {'name': 'Unknown', 'mbti': '', 'instagram_id': ''}

                results.append({
                    'id': match['id'],
                    'compatibility_score': match['compatibility_score'],
                    'matching_reason': match['matching_reason'] if match['matching_reason'] else '',
                    'created_at': match['created_at'],
                    'user1': {
                        'name': user1_data.get('name', 'Unknown'),
                        'mbti': user1_data.get('mbti', ''),
                        'instagram': user1_data.get('instagram_id', '')
                    },
                    'user2': {
                        'name': user2_data.get('name', 'Unknown'),
                        'mbti': user2_data.get('mbti', ''),
                        'instagram': user2_data.get('instagram_id', '')
                    }
                })
            except Exception as item_error:
                print(f"⚠️ 매칭 항목 처리 오류: {item_error}")
                continue

        print(f"✅ 매칭 결과 처리 완료: {len(results)}개")
        return jsonify({'matches': results})

    except Exception as e:
        print(f"❌ 매칭 결과 조회 오류: {e}")
        # 간단한 대체 조회 시도
        try:
            matches_response = supabase.table('matches').select('*').execute()
            simple_results = [{
                'id': m['id'],
                'compatibility_score': m['compatibility_score'],
                'matching_reason': m['matching_reason'] if m['matching_reason'] else '',
                'created_at': m['created_at'],
                'user1': {'name': f"User {m['user1_id']}", 'mbti': '', 'instagram': ''},
                'user2': {'name': f"User {m['user2_id']}", 'mbti': '', 'instagram': ''}
            } for m in matches_response.data]
            print(f"🔄 대체 조회 성공: {len(simple_results)}개")
            return jsonify({'matches': simple_results})
        except:
            return jsonify({'matches': [], 'error': '매칭 결과를 불러올 수 없습니다'}), 200

# --- [푸시 알림 관련 API 엔드포인트들] ---

@app.route('/api/push/vapid-public-key')
def get_vapid_public_key():
    """VAPID 퍼블릭 키 반환 (푸시 알림 구독용)"""
    if not VAPID_PUBLIC_KEY:
        return jsonify({'error': 'VAPID 퍼블릭 키가 설정되지 않았습니다'}), 500

    return jsonify({'publicKey': VAPID_PUBLIC_KEY})

@app.route('/api/push/subscribe', methods=['POST'])
def subscribe_push():
    """푸시 알림 구독 등록"""
    try:
        data = request.get_json()
        device_token = data.get('device_token')
        subscription = data.get('subscription')
        user_id = data.get('user_id')  # 선택적

        if not device_token or not subscription:
            return jsonify({'error': 'device_token과 subscription이 필요합니다'}), 400

        if save_push_subscription(device_token, subscription, user_id):
            return jsonify({'message': '푸시 알림 구독이 등록되었습니다'})
        else:
            return jsonify({'error': '구독 등록에 실패했습니다'}), 500

    except Exception as e:
        return jsonify({'error': f'구독 등록 중 오류 발생: {e}'}), 500

@app.route('/api/push/unsubscribe', methods=['POST'])
def unsubscribe_push():
    """푸시 알림 구독 해제"""
    try:
        data = request.get_json()
        device_token = data.get('device_token')

        if not device_token:
            return jsonify({'error': 'device_token이 필요합니다'}), 400

        # 구독 정보 삭제
        supabase.table('push_subscriptions').delete().eq('device_token', device_token).execute()

        return jsonify({'message': '푸시 알림 구독이 해제되었습니다'})

    except Exception as e:
        return jsonify({'error': f'구독 해제 중 오류 발생: {e}'}), 500

@app.route('/api/user/device-token', methods=['POST'])
def get_or_create_device_token():
    """디바이스 토큰 생성 또는 기존 토큰 반환"""
    try:
        device_token = generate_device_token()
        return jsonify({'device_token': device_token})
    except Exception as e:
        return jsonify({'error': f'디바이스 토큰 생성 중 오류 발생: {e}'}), 500

@app.route('/api/user/link-device', methods=['POST'])
def link_device_to_user():
    """디바이스를 사용자 계정에 연결"""
    try:
        data = request.get_json()
        device_token = data.get('device_token')
        user_id = data.get('user_id')  # results 테이블의 id

        if not device_token or not user_id:
            return jsonify({'error': 'device_token과 user_id가 필요합니다'}), 400

        # 디바이스 토큰이 존재하는지 확인
        subscription = get_push_subscription(device_token)
        if not subscription:
            return jsonify({'error': '등록되지 않은 디바이스 토큰입니다'}), 400

        # 사용자 연결 업데이트
        supabase.table('push_subscriptions').update({
            'user_id': user_id
        }).eq('device_token', device_token).execute()

        return jsonify({'message': '디바이스가 사용자 계정에 연결되었습니다'})

    except Exception as e:
        return jsonify({'error': f'디바이스 연결 중 오류 발생: {e}'}), 500

@app.route('/matches/<int:user_id>')
def view_matches(user_id):
    """매칭 결과 조회 페이지"""
    try:
        # 사용자의 매칭 결과 조회
        matches = supabase.table('matches').select('*').or_(
            f'user1_id.eq.{user_id},user2_id.eq.{user_id}'
        ).order('compatibility_score', desc=True).execute()

        if not matches.data:
            return render_template('no_matches.html', user_id=user_id)

        # 매칭 상대 정보 조회
        matched_users = []
        for match in matches.data:
            # 상대방 정보 찾기
            other_user_id = match['user2_id'] if match['user1_id'] == user_id else match['user1_id']

            user_info = supabase.table('results').select('name, mbti, instagram_id').eq('id', other_user_id).execute()
            if user_info.data:
                user_data = user_info.data[0]
                matched_users.append({
                    'id': other_user_id,
                    'name': user_data['name'],
                    'mbti': user_data['mbti'],
                    'instagram_id': user_data['instagram_id'],
                    'compatibility_score': match['compatibility_score'],
                    'matching_reason': match['matching_reason']
                })

        return render_template('matches.html',
                             user_id=user_id,
                             matches=matched_users)

    except Exception as e:
        print(f"❌ 매칭 결과 조회 중 오류: {e}")
        return f"매칭 결과를 불러오는 중 오류가 발생했습니다: {e}", 500

@app.route('/push-settings')
def push_settings():
    """푸시 알림 설정 페이지"""
    return render_template('push_settings.html')

@app.route('/push-test')
def push_test():
    """푸시 알림 테스트 페이지"""
    return render_template('push_test.html')

@app.route('/api/push/test', methods=['POST'])
def send_test_notification():
    """테스트 푸시 알림 전송"""
    try:
        data = request.get_json()
        device_token = data.get('device_token')
        title = data.get('title', '테스트 알림')
        body = data.get('body', '푸시 알림이 정상적으로 작동하고 있습니다!')

        if not device_token:
            return jsonify({'error': 'device_token이 필요합니다'}), 400

        # 디바이스 토큰으로 구독 정보 조회
        subscription = get_push_subscription(device_token)
        if not subscription:
            return jsonify({'error': '등록되지 않은 디바이스 토큰입니다'}), 400

        subscription_info = {
            'endpoint': subscription['endpoint'],
            'keys': {
                'p256dh': subscription['p256dh'],
                'auth': subscription['auth']
            }
        }

        test_data = {
            'action': 'test',
            'timestamp': str(datetime.now())
        }

        if send_push_notification(subscription_info, title, body, test_data):
            return jsonify({'message': '테스트 알림이 전송되었습니다'})
        else:
            return jsonify({'error': '알림 전송에 실패했습니다'}), 500

    except Exception as e:
        return jsonify({'error': f'테스트 알림 전송 중 오류 발생: {e}'}), 500

@app.route('/saju', methods=['POST'])
def analyze_saju():
    try:
        data = request.get_json()
        name = data.get('name', '정보 없음')
        student_id = data.get('studentId', '0')
        year = int(data['year']); month = int(data['month']); day = int(data['day']); hour = int(data['hour'])
        mbti = data.get('mbti', '정보 없음')
        instagram_id = data.get('instagramId', '')
        gender = data.get('gender', '')
    except Exception as e:
        return jsonify({"error": f"데이터를 받는 중 오류 발생: {e}"}), 400

    try:
        year_p, month_p, day_p, time_p = calculate_saju_pillars(year, month, day, hour)
        saju_text = f"{year_p}/{month_p}/{day_p}/{time_p}"
    except Exception as e:
        return jsonify({"error": f"사주를 계산하는 중 오류 발생: {e}"}), 500

    try:
        # 캐시 키 생성 (MBTI만 - 사주 정보는 동적으로 채움)
        analysis_cache_key = mbti

        # 사주 오행 분석 추가 (모든 경우에 공통으로 먼저 생성)
        saju_analysis = get_saju_element_analysis(year_p, month_p, day_p, time_p)
        
        # 캐시 확인 (이미 분석된 MBTI이면 즉시 반환) - 임시로 비활성화하여 항상 새 형식 사용
        if False and analysis_cache_key in saju_analysis_cache:
            print(f"⚡ 캐시된 MBTI 분석 템플릿 사용: {name}({mbti})")
            
            # 항상 새로운 형식으로 생성 (캐시는 참고용으로만 사용)
            ai_response = f"""🔮 사주 정보
연주(년): {year_p}, 월주(월): {month_p}, 일주(일): {day_p}, 시주(시): {time_p}

{saju_analysis}

💬 AI 분석 결과
{name}님은 밝고 따뜻한 성격을 가지고 계시네요. MBTI {mbti} 유형답게 창의적이고 사람들과의 소통을 좋아하는 스타일입니다. 연애에서는 진심 어린 마음으로 상대방을 대하는 타입이에요.

🤝 추천 매칭 상대
사주: {year_p}의 기운과 잘 어울리는 사주를 가진 분
MBTI: {mbti}와 잘 맞는 유형들

행복한 연애 하시길 바래요! 💕"""
        else:
            # AI 호출 없이 즉시 생성 (템플릿 기반)
            print(f"🤖 새로운 형식으로 사주 분석 생성: {name}")
            print(f"🔍 사주 오행 분석 미리보기: {saju_analysis[:100]}...")
            
            ai_response = f"""🔮 사주 정보
연주(년): {year_p}, 월주(월): {month_p}, 일주(일): {day_p}, 시주(시): {time_p}

{saju_analysis}

💬 AI 분석 결과
{name}님은 밝고 따뜻한 성격을 가지고 계시네요. MBTI {mbti} 유형답게 창의적이고 사람들과의 소통을 좋아하는 스타일입니다. 연애에서는 진심 어린 마음으로 상대방을 대하는 타입이에요.

🤝 추천 매칭 상대
사주: {year_p}의 기운과 잘 어울리는 사주를 가진 분
MBTI: {mbti}와 잘 맞는 유형들

행복한 연애 하시길 바래요! 💕"""

            # 캐시에 저장 및 파일에 저장
            saju_analysis_cache[analysis_cache_key] = ai_response
            print(f"💾 캐시 메모리 저장 완료 (크기: {len(saju_analysis_cache)})")
            save_saju_cache(saju_analysis_cache)
            print(f"💾 사주 분석 결과 파일에 저장: {name} (키: {analysis_cache_key})")

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

            # 사용자 ID 저장 (푸시 알림 연결용)
            user_id = insert_response.data[0]['id'] if insert_response.data else None

        except Exception as e:
            print(f"Supabase 저장 중 오류 발생: {e}")
            return jsonify({"error": f"데이터 저장 중 오류가 발생했습니다: {e}"}), 500
            # DB 저장 끝
    except Exception as e:
        return jsonify({"error": f"Gemini API 처리 중 오류 발생: {e}"}), 500

    return jsonify({
        "saju_result": saju_text,
        "ai_analysis": ai_response,
        "user_id": user_id
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

    # 매칭 중단 방지: 자동 재시작 비활성화
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)



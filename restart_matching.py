#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
매칭이 멈췄을 때 즉시 재시작할 수 있는 스크립트
"""

import requests
import time
import sys

def restart_matching():
    """매칭 프로세스 재시작"""
    print("🔄 매칭 시스템 재시작 중...")
    
    try:
        # 1. 서버 상태 확인
        print("📡 서버 연결 확인...")
        response = requests.get('https://cbacb040e05b.ngrok-free.app/admin', timeout=5)
        if response.status_code not in [200, 302]:
            print("❌ 서버에 연결할 수 없습니다. 서버를 먼저 시작해주세요.")
            return False
        
        print("✅ 서버 연결 성공")
        
        # 2. 매칭 요청 전송 (세션 우회를 위해 개발 모드 사용)
        print("🚀 매칭 요청 전송...")
        
        # 간단한 매칭 상태 확인 요청
        test_response = requests.get('http://localhost:5000/admin/matching/results', timeout=10)
        
        if test_response.status_code == 401:
            print("⚠️ 로그인이 필요합니다. 웹 브라우저에서 직접 매칭을 시작해주세요.")
            print("🌐 브라우저에서 http://localhost:5000/admin 접속")
            return False
        
        print("✅ 매칭 시스템이 재시작 가능한 상태입니다.")
        print("💡 웹 브라우저에서 매칭을 다시 시작해주세요:")
        print("   1. http://localhost:5000/admin 접속")
        print("   2. 로그인 후 '매칭 시작' 버튼 클릭")
        
        return True
        
    except requests.exceptions.Timeout:
        print("⏰ 서버 응답 시간 초과. 서버가 멈춘 것 같습니다.")
        print("💡 서버를 재시작해주세요:")
        print("   1. 터미널에서 Ctrl+C로 서버 중지")
        print("   2. python api/index.py로 서버 재시작")
        return False
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False

def check_matching_status():
    """매칭 진행 상황 모니터링"""
    print("📊 매칭 상태 모니터링 시작...")
    
    last_log_time = time.time()
    check_interval = 30  # 30초마다 체크
    
    while True:
        try:
            # 서버 응답 확인
            response = requests.get('https://cbacb040e05b.ngrok-free.app/admin', timeout=5)
            
            if response.status_code == 200:
                current_time = time.time()
                print(f"✅ {time.strftime('%H:%M:%S')} - 서버 정상 작동 중")
                
                # 30초마다 상태 체크
                if current_time - last_log_time > check_interval:
                    print("📊 매칭이 30초 이상 진행되지 않으면 재시작을 고려해주세요.")
                    last_log_time = current_time
                    
            else:
                print(f"⚠️ 서버 응답 이상: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("⏰ 서버가 응답하지 않습니다. 매칭이 멈춘 것 같습니다!")
            print("🔄 restart_matching.py를 실행하여 재시작하세요.")
            break
            
        except KeyboardInterrupt:
            print("\n👋 모니터링을 중단합니다.")
            break
            
        except Exception as e:
            print(f"❌ 모니터링 오류: {e}")
            
        time.sleep(10)  # 10초마다 체크

def main():
    print("🎯 매칭 시스템 관리 도구")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == 'monitor':
        check_matching_status()
    else:
        restart_matching()
        
        # 재시작 후 모니터링 옵션 제공
        print("\n📊 매칭 진행을 모니터링하시겠습니까? (y/n): ", end="")
        if input().lower() == 'y':
            print("\n🔍 매칭 모니터링 시작 (Ctrl+C로 중단)")
            time.sleep(2)
            check_matching_status()

if __name__ == "__main__":
    main()

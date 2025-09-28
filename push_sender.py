#!/usr/bin/env python3
"""
직접 HTTP 요청으로 푸시 알림 전송 스크립트
"""
import requests
import json
import time
import base64
import os
import sys
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend

def send_push_notification(subscription_info, title, body, data=None, vapid_email="", vapid_public_key="", vapid_private_key="", app_url=""):
    """푸시 알림 전송 - 직접 HTTP 요청 (Web Push 프로토콜)"""
    try:
        endpoint = subscription_info.get('endpoint', '')
        p256dh = subscription_info.get('keys', {}).get('p256dh', '')
        auth = subscription_info.get('keys', {}).get('auth', '')

        if not all([endpoint, p256dh, auth]):
            print("❌ 구독 정보가 불완전합니다")
            return False

        print(f"📤 푸시 알림 전송 시도: {endpoint[:50]}...")
        print(f"📝 제목: {title}")
        print(f"📝 내용: {body}")

        # VAPID 개인 키 로드 (테스트용 임시 키 생성)
        try:
            # 테스트를 위해 임시로 새 키 생성
            private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
            print("⚠️ 임시 VAPID 키를 생성해서 사용합니다 (테스트용)")
        except Exception as e:
            print(f"❌ VAPID 키 생성 실패: {e}")
            return False

        # VAPID JWT 생성
        payload_data = {
            "aud": "https://web.push.apple.com",
            "exp": int(time.time()) + 86400,
            "sub": f"mailto:{vapid_email}"
        }

        # JWT 헤더
        header = {"alg": "ES256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip('=')

        # 서명
        message = f"{header_b64}.{payload_b64}".encode()
        signature_der = private_key.sign(message, ec.ECDSA(hashes.SHA256()))
        signature_b64 = base64.urlsafe_b64encode(signature_der).decode().rstrip('=')

        jwt_token = f"{header_b64}.{payload_b64}.{signature_b64}"

        # 푸시 페이로드
        push_payload = json.dumps({
            'title': title,
            'body': body,
            'icon': f'{app_url}/static/img/kor.gif',
            'badge': f'{app_url}/static/img/kor.gif',
            'data': data or {}
        }, ensure_ascii=False)

        # Web Push 헤더 (Apple Push 서비스용)
        headers = {
            'TTL': '86400',
            'Content-Type': 'application/json;charset=utf-8',
            'Authorization': f'Bearer {jwt_token}',
            'Content-Encoding': 'aes128gcm'
        }

        print(f"📨 JWT 토큰 길이: {len(jwt_token)}")

        # HTTP 요청 전송
        response = requests.post(
            endpoint,
            data=push_payload.encode('utf-8'),
            headers=headers,
            timeout=10
        )

        print(f"📡 HTTP 응답: {response.status_code}")

        if response.status_code in [200, 201, 202]:
            print("✅ 푸시 알림 전송 성공")
            return True
        elif response.status_code in [400, 404, 410, 413]:
            print(f"⚠️ 클라이언트 오류 ({response.status_code}) - 구독이 만료되었을 수 있음")
            print(f"응답: {response.text}")
            return False
        else:
            print(f"⚠️ 서버 오류 ({response.status_code}): {response.text}")
            return False

    except Exception as e:
        print(f"❌ 푸시 알림 전송 실패: {e}")
        import traceback
        print(f"상세 오류: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    # 하드코딩된 테스트용 키 사용
    test_vapid_private_key = "3MhQJjdYEyruoHLKSK8Ry0mURHfF1k2y6dtBKmA1cQg"  # web-push 호환 형식
    test_vapid_public_key = "BHfpLCcwKDVg2TkshpmVn9Tr3nizK-dxkCAkAIIkp59UBXRU3Iwim8FuSCXoQOLUYjPxO6GJPncPup_bBpK7z-w"

    subscription_info = {
        'endpoint': "https://web.push.apple.com/QN4T4JnzQzp-YdwNMGffJVGWoVsICJhDAuR5d2f4WkgcJ1Q5xGb9f2zE5S8vK7mNpL3yH1aBcD9eF6gM2nR4sT8uV5wX3yZ",
        'keys': {
            'p256dh': "BDndaGaU3xYQe9zotlgNj8Hd9vylRzt7k5cKz6EFxnVdQ8WzheEf9u02tYGL2qgxFTSypz0CGZHXIBpjaqY3OBo=",
            'auth': "Xnk7fz34KSnM6s88GQ1O5Q=="
        }
    }

    success = send_push_notification(
        subscription_info,
        "하드코딩 키 테스트",
        "web-push 호환 키로 테스트 중입니다",
        None,
        "vologi148@gmail.com",
        test_vapid_public_key,
        test_vapid_private_key,
        "https://591231f57e20.ngrok-free.app"
    )
    sys.exit(0 if success else 1)

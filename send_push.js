const webpush = require("web-push");

// 환경변수에서 VAPID 키 가져오기
const vapidEmail = process.env.VAPID_EMAIL || "mailto:vologi148@gmail.com";
const vapidPublicKey =
  process.env.VAPID_PUBLIC_KEY ||
  "BHfpLCcwKDVg2TkshpmVn9Tr3nizK-dxkCAkAIIkp59UBXRU3Iwim8FuSCXoQOLUYjPxO6GJPncPup_bBpK7z-w";
const vapidPrivateKey =
  process.env.VAPID_PRIVATE_KEY ||
  "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JR0hBZ0VBTUJNR0J5cUdTTTQ5QWdFR0NDcUdTTTQ5QXdFSEJHMHdhd0lCQVFRZzNNaFFKamRZRXlydW9ITEsKU0s4UnkwbVVSSGZGMWsyeTZkdEJLbUExY1FpaFJBTkNBQVFKWmRUVGIxMDRmVThUMVNjVjFvT0pQZlQ2dk1WOQpRRWl4Mkh5UGlBOUcyUVFqNGhVclNVOW1wbnR4S0NWdjk2bzh4R002RWR3VS9Cc3pEUjVjMEcxLwotLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tCg";

// VAPID 키 설정
webpush.setVapidDetails(
  vapidEmail.startsWith("mailto:") ? vapidEmail : `mailto:${vapidEmail}`,
  vapidPublicKey,
  vapidPrivateKey
);

// 명령줄 인자에서 구독 정보 가져오기
const endpoint = process.argv[2];
const p256dh = process.argv[3];
const auth = process.argv[4];
const title = process.argv[5] || "테스트 알림";
const body = process.argv[6] || "알림 테스트 중입니다";
const appUrl = process.env.APP_URL || "https://591231f57e20.ngrok-free.app";

if (!endpoint || !p256dh || !auth) {
  console.error(
    "사용법: node send_push.js <endpoint> <p256dh> <auth> [title] [body]"
  );
  process.exit(1);
}

const subscription = {
  endpoint: endpoint,
  keys: {
    p256dh: p256dh,
    auth: auth,
  },
};

const payload = JSON.stringify({
  title: title,
  body: body,
  icon: `${appUrl}/static/img/kor.gif`,
  badge: `${appUrl}/static/img/kor.gif`,
  data: {
    action: "view_matches",
    url: `${appUrl}/matches/14`,
  },
});

console.log("🔔 푸시 알림 전송 시도...");
console.log("Endpoint:", endpoint.substring(0, 60) + "...");
console.log("p256dh 길이:", p256dh.length, "(예상: 87)");
console.log("auth 길이:", auth.length, "(예상: 22)");
console.log("VAPID Private Key 길이:", vapidPrivateKey.length);
console.log("VAPID Public Key 길이:", vapidPublicKey.length);

// iOS Safari 호환성을 위한 옵션들
const options = {
  vapidDetails: {
    subject: vapidEmail,
    publicKey: vapidPublicKey,
    privateKey: vapidPrivateKey,
  },
  // iOS Safari에서는 다른 content encoding을 사용할 수 있음
  contentEncoding: "aes128gcm", // 또는 'aesgcm'
  // TTL 설정
  TTL: 86400,
};

webpush
  .sendNotification(subscription, payload, options)
  .then((result) => {
    console.log("✅ 푸시 알림 전송 성공");
    console.log("결과:", result);
    process.exit(0);
  })
  .catch((err) => {
    console.error("❌ 푸시 알림 전송 실패");
    console.error("오류:", err.message);
    if (err.statusCode) {
      console.error("HTTP 상태 코드:", err.statusCode);
    }
    console.error("스택 트레이스:", err.stack);

    // 400 에러일 경우 추가 정보 출력
    if (err.statusCode === 400) {
      console.error("🔍 400 Bad Request - 구독 키 검증 실패");
      console.error("이는 iOS Safari의 키 형식이 표준과 다를 수 있습니다.");
    }

    process.exit(1);
  });

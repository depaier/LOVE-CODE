const webpush = require("web-push");

// 환경변수에서 VAPID 키 가져오기
const vapidEmail = process.env.VAPID_EMAIL;
const vapidPublicKey = process.env.VAPID_PUBLIC_KEY;
const vapidPrivateKey = process.env.VAPID_PRIVATE_KEY;

// VAPID 키 설정
webpush.setVapidDetails(
  vapidEmail.startsWith('mailto:') ? vapidEmail : `mailto:${vapidEmail}`,
  vapidPublicKey,
  vapidPrivateKey
);

const subscription = {
  endpoint: "https://web.push.apple.com/QAu3mIhIlemU83Ivr2FbFrb8FnyX4T7QtFEZpbmcSD-09_AndQCnnh83ou11id_WX3lNEAxkygIZ-dbE7xpERc2q7dL3FrCT8grwi_wbx9vM3o5aQ5eGIE2F2mntqri-JG7R0WZlURw1I3ZgsRbfvjgKxvzf09FfHB2XXG-P-Zc",
  keys: {
    p256dh: "BOHBqs+Re97HTthdClH3",
    auth: "FYCTz5hqvvoAodmGgnDV"
  }
};

const payload = JSON.stringify({
  title: "테스트 알림",
  body: "푸시 알림이 정상적으로 작동하고 있습니다!",
  icon: "https://591231f57e20.ngrok-free.app/static/img/kor.gif",
  badge: "https://591231f57e20.ngrok-free.app/static/img/kor.gif",
  data: {}
});

console.log("Node.js에서 실제 subscription으로 푸시 알림 전송 시도...");

webpush.sendNotification(subscription, payload)
  .then(result => {
    console.log("✅ 푸시 알림 전송 성공");
    console.log("결과:", result);
    process.exit(0);
  })
  .catch(err => {
    console.error("❌ 푸시 알림 전송 실패:", err.message);
    console.error("에러 코드:", err.statusCode);
    if (err.statusCode === 410) {
      console.error("구독이 만료되었습니다.");
    } else if (err.statusCode === 400) {
      console.error("잘못된 요청입니다.");
    }
    process.exit(1);
  });

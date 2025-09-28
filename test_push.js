// andreinwald 예제 기반 Node.js 푸시 알림 테스트
const webpush = require("web-push");

// web-push 호환 VAPID 키 설정
webpush.setVapidDetails(
  "mailto:vologi148@gmail.com",
  "BAdlhTczKvrmrihDxrCezWb-siCRJASkg9iKhieFow4uBme5QcWzAGpSC1JD0ydO4D9KAQjF-ZMovyTQHWhCHOs",
  "234kIfJL4tf6y0m2mInyqBZY3CjvL8At4YTmwKBDzak"
);

// andreinwald의 subscription 토큰
const subscription = {
  endpoint:
    "https://web.push.apple.com/QNgjQzZnDjeZEzvH4hYXjK1aX9D03ssynNxS3CO2bh6C6WFeCeoNLn3qkzHxkNDT2nPz_4pKf8QZXAbOAzjgs3C8yxGhzKS59PNXO5yAEwxfeK2846pMeI4VWPNWCywyRQnHNt83cpsPX7UQMurBza_vBFv5nic8lyS3IfHoqiQ",
  keys: {
    p256dh:
      "BFtf_43Xj5XqHZodbYoVropBLv6RLHcZ_UtXRHYgfbao7D9us1M1GXxzXAeDWXfHDS84oQ9af8Somnbll_9co7A",
    auth: "TPt-MUsvlOSV02aQIDaCHg",
  },
};

const payload = JSON.stringify({
  title: "Node.js 테스트",
  body: "web-push 라이브러리로 보내는 테스트 알림입니다!",
  icon: "https://andreinwald.github.io/webpush-ios-example/images/favicon.png",
  data: {
    url: "https://andreinwald.github.io/webpush-ios-example/?page=success",
  },
});

console.log("🔔 Node.js web-push 라이브러리로 테스트 시작");

webpush
  .sendNotification(subscription, payload)
  .then((result) => {
    console.log("✅ 푸시 알림 전송 성공:", result);
  })
  .catch((err) => {
    console.error("❌ 푸시 알림 전송 실패:", err);
  });

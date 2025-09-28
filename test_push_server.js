// 실제 구독 토큰으로 푸시 알림 전송 테스트
const webpush = require("web-push");

// web-push 호환 VAPID 키 설정
webpush.setVapidDetails(
  "mailto:vologi148@gmail.com",
  "BHfpLCcwKDVg2TkshpmVn9Tr3nizK-dxkCAkAIIkp59UBXRU3Iwim8FuSCXoQOLUYjPxO6GJPncPup_bBpK7z-w",
  "3MhQJjdYEyruoHLKSK8Ry0mURHfF1k2y6dtBKmA1cQg"
);

// 실제 데이터베이스의 구독 정보 (사용자 ID: 13)
const subscription = {
  endpoint:
    "https://web.push.apple.com/QN4T4JnzQzp-YdwNMGffJVGWoVsICJhDAuR5d2f4WkgcJ1Q5xGb9f2zE5S8vK7mNpL3yH1aBcD9eF6gM2nR4sT8uV5wX3yZ",
  keys: {
    p256dh:
      "BDndaGaU3xYQe9zotlgNj8Hd9vylRzt7k5cKz6EFxnVdQ8WzheEf9u02tYGL2qgxFTSypz0CGZHXIBpjaqY3OBo=",
    auth: "Xnk7fz34KSnM6s88GQ1O5Q==",
  },
};

const payload = JSON.stringify({
  title: "사주 매칭 알림",
  body: "매칭 상대를 찾았어요! 확인해보세요.",
  icon: "https://591231f57e20.ngrok-free.app/static/img/kor.gif",
  badge: "https://591231f57e20.ngrok-free.app/static/img/kor.gif",
  data: {
    action: "view_matches",
    user_id: 13,
    url: "https://591231f57e20.ngrok-free.app/matches/13",
  },
});

console.log("🔔 실제 사용자 구독 토큰으로 푸시 알림 전송 테스트");
console.log("Endpoint:", subscription.endpoint);

webpush
  .sendNotification(subscription, payload)
  .then((result) => {
    console.log("✅ 푸시 알림 전송 성공:", result);
  })
  .catch((err) => {
    console.error("❌ 푸시 알림 전송 실패:", err);
    console.error("상세 오류:", err.message);
    console.error("스택 트레이스:", err.stack);
  });

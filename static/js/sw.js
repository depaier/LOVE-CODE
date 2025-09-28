// Service Worker for Push Notifications
// 사주 매칭 서비스 푸시 알림용 Service Worker

// Service Worker 설치 이벤트
self.addEventListener("install", (event) => {
  console.log("Service Worker 설치됨");
  // 즉시 활성화
  self.skipWaiting();
});

// Service Worker 활성화 이벤트
self.addEventListener("activate", (event) => {
  console.log("Service Worker 활성화됨");
  // 기존 Service Worker 정리
  event.waitUntil(self.clients.claim());
});

// 푸시 메시지 수신 이벤트
self.addEventListener("push", (event) => {
  console.log("푸시 메시지 수신:", event);

  let data = {};

  if (event.data) {
    try {
      data = event.data.json();
    } catch (error) {
      console.error("푸시 데이터 파싱 실패:", error);
      data = {
        title: "새로운 알림",
        body: event.data.text() || "알림이 도착했습니다.",
      };
    }
  } else {
    data = {
      title: "새로운 알림",
      body: "알림이 도착했습니다.",
    };
  }

  const options = {
    body: data.body || "알림이 도착했습니다.",
    icon: data.icon || "/static/img/kor.gif",
    badge: data.badge || "/static/img/kor.gif",
    image: data.image,
    data: data.data || {},
    requireInteraction: data.requireInteraction !== false, // iOS Safari에서는 기본적으로 true
    silent: data.silent || false,
    tag: data.tag || "saju-matching-notification",
    renotify: data.renotify !== false, // iOS Safari 호환성
    actions: data.actions || [
      {
        action: "view",
        title: "확인하기",
      },
      {
        action: "dismiss",
        title: "닫기",
      },
    ],
    // iOS Safari 전용 설정
    sound: data.sound || null,
    vibration: data.vibration || null,
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

// 알림 클릭 이벤트
self.addEventListener("notificationclick", (event) => {
  console.log("알림 클릭됨:", event);

  const notification = event.notification;
  const action = event.action;
  const data = notification.data || {};

  notification.close();

  // 액션에 따른 처리
  if (action === "dismiss") {
    // 닫기 액션 - 아무것도 하지 않음
    return;
  }

  // 기본 액션이나 'view' 액션 처리
  let url = "/";

  // 데이터에 따라 다른 URL로 이동
  if (data.action === "view_matches" && data.user_id) {
    url = `/matches/${data.user_id}?notification=match_complete`;
  } else if (data.url) {
    url = data.url;
  }

  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        // iOS Safari 호환성을 위해 더 간단한 방식 사용
        const isIOS = clientList.some((client) =>
          /iPad|iPhone|iPod/.test(client.userAgent || "")
        );

        // 이미 열려있는 창이 있는지 확인
        for (let i = 0; i < clientList.length; i++) {
          const client = clientList[i];
          if (client.url.includes(url) && "focus" in client) {
            return client.focus();
          }
        }

        // 새 창 열기 (iOS Safari에서는 새로운 탭으로 열림)
        if (clients.openWindow) {
          return clients.openWindow(url);
        }
      })
  );
});

// 알림 닫힘 이벤트 (선택적)
self.addEventListener("notificationclose", (event) => {
  console.log("알림 닫힘:", event);
});

// 백그라운드 메시지 처리 (필요시)
self.addEventListener("message", (event) => {
  console.log("Service Worker 메시지 수신:", event.data);

  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

// 주기적 백그라운드 동기화 (필요시)
self.addEventListener("sync", (event) => {
  console.log("백그라운드 동기화:", event.tag);

  if (event.tag === "background-sync") {
    event.waitUntil(doBackgroundSync());
  }
});

// 백그라운드 동기화 함수
async function doBackgroundSync() {
  try {
    // 필요한 백그라운드 작업 수행
    console.log("백그라운드 동기화 작업 수행");
  } catch (error) {
    console.error("백그라운드 동기화 실패:", error);
  }
}

// 에러 처리
self.addEventListener("error", (event) => {
  console.error("Service Worker 에러:", event.error);
});

self.addEventListener("unhandledrejection", (event) => {
  console.error("Service Worker 처리되지 않은 Promise 거부:", event.reason);
});

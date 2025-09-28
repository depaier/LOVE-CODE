// Service Worker for Push Notifications
// 사주 매칭 서비스 푸시 알림용 Service Worker
// Version: 2024-09-29-v3

// Service Worker 설치 이벤트
self.addEventListener("install", (event) => {
  console.log("Service Worker 설치됨");
  // 즉시 활성화
  self.skipWaiting();
});

// Service Worker 활성화 이벤트
self.addEventListener("activate", (event) => {
  console.log("Service Worker 활성화됨 - Version: 2024-09-29-v3");
  // 기존 캐시 정리 및 즉시 제어권 획득
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            console.log("기존 캐시 삭제:", cacheName);
            return caches.delete(cacheName);
          })
        );
      })
      .then(() => {
        console.log("모든 클라이언트에 대한 제어권 획득");
        return self.clients.claim();
      })
  );
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
  console.log("🔔 알림 클릭됨:", event);
  console.log("📝 알림 제목:", event.notification.title);
  console.log("📝 알림 내용:", event.notification.body);

  const notification = event.notification;
  const action = event.action;
  let data = notification.data || {};

  // 데이터가 문자열로 오는 경우 파싱
  if (typeof data === "string") {
    try {
      data = JSON.parse(data);
      console.log("📝 문자열 데이터를 JSON으로 파싱했습니다:", data);
    } catch (e) {
      console.error("❌ JSON 파싱 실패:", e);
      data = {};
    }
  }

  console.log("📊 알림 액션:", action);
  console.log("📊 알림 데이터:", JSON.stringify(data));
  console.log("📊 데이터 타입:", typeof data);
  console.log("📊 데이터 구조 상세:", {
    action: data.action,
    user_id: data.user_id,
    url: data.url,
    source: data.source,
    dataKeys: Object.keys(data || {}),
  });
  
  // 특별히 매칭 알림인 경우 강조 표시
  if (data.action === 'view_matches') {
    console.log("🎯🎯🎯 매칭 알림 감지됨! user_id:", data.user_id);
  }

  notification.close();

  // 액션에 따른 처리
  if (action === "dismiss") {
    console.log("❌ 사용자가 알림을 닫았습니다");
    return;
  }

  // 기본 액션이나 'view' 액션 처리
  let url = "/";

  // 데이터에 따라 다른 URL로 이동
  if (data.action === "view_matches" && data.user_id) {
    url = `/matches/${data.user_id}?notification=match_complete`;
    console.log("🎯 매칭 결과 페이지로 이동:", url);
  } else if (data.action === "view_home") {
    url = "/?notification=waiting";
    console.log("🎯 홈페이지로 이동 (매칭 대기):", url);
  } else if (data.url) {
    url = data.url;
    console.log("🎯 사용자 지정 URL로 이동:", url);
  } else {
    console.log("⚠️ 유효한 데이터가 없어 홈페이지로 이동:", url);
    console.log("📊 확인된 데이터:", {
      action: data.action,
      user_id: data.user_id,
      url: data.url,
    });
  }

  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        console.log(`🔍 현재 열린 탭 수: ${clientList.length}개`);
        console.log(`🎯 이동할 URL: ${url}`);

        // iOS Safari 호환성을 위해 더 간단한 방식 사용
        const isIOS = clientList.some((client) =>
          /iPad|iPhone|iPod/.test(client.userAgent || "")
        );

        // 이미 열려있는 창에서 정확한 URL이 있는지 확인
        let foundMatchingClient = null;
        for (let i = 0; i < clientList.length; i++) {
          const client = clientList[i];
          console.log(`📋 탭 ${i + 1}: ${client.url}`);

          // 정확히 같은 URL을 가진 탭 찾기
          if (
            client.url === url ||
            client.url.split("?")[0] === url.split("?")[0]
          ) {
            foundMatchingClient = client;
            console.log(`✅ 동일한 페이지를 찾았습니다: ${client.url}`);
            break;
          }
        }

        // 정확히 같은 URL의 탭이 있으면 포커스
        if (foundMatchingClient && "focus" in foundMatchingClient) {
          console.log(`🎯 기존 탭으로 포커스 이동`);
          return foundMatchingClient.focus();
        }

        // 매칭 결과 페이지로 가야 하는데 다른 페이지가 열려있다면
        // 기존 탭에서 URL 변경을 시도
        if (clientList.length > 0) {
          const firstClient = clientList[0];
          console.log(
            `🔄 기존 탭에서 URL 변경 시도: ${firstClient.url} → ${url}`
          );

          // postMessage로 페이지 이동 요청 - 더 강력한 방식
          try {
            firstClient.postMessage({
              type: "NAVIGATE",
              url: url,
              force: true,
              timestamp: Date.now(),
            });

            console.log("📤 페이지 이동 메시지 전송 완료");

            // 잠시 후 포커스
            setTimeout(() => {
              if (firstClient.focus) {
                firstClient.focus();
                console.log("🎯 기존 탭 포커스 완료");
              }
            }, 100);

            return Promise.resolve();
          } catch (err) {
            console.error("❌ postMessage 전송 실패:", err);
            // postMessage 실패 시 새 창으로 열기
            if (clients.openWindow) {
              return clients.openWindow(url);
            }
          }
        }

        // 새 창 열기 (iOS Safari에서는 새로운 탭으로 열림)
        console.log(`🆕 새 창을 엽니다: ${url}`);
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

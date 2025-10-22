// ==========================================================
// YouTube Queue Online — v01.6.2
// Ngày cập nhật: 17/10/2025
// Loại cập nhật: Bảo vệ trang Host + Đổi mật khẩu Host (JS)
// Thay đổi (so với v01.6.1):
// - Thêm popup xác minh mật khẩu host (ẩn giao diện khi chưa verify)
// - Thêm luồng đổi mật khẩu host (yêu cầu HOST_KEY trong form)
// - Giữ nguyên toàn bộ điều khiển queue/now playing/config/logo
// ==========================================================

const qs = (s) => document.querySelector(s);
const queueEl = qs("#queue");
const historyEl = qs("#history");
const countdown = qs("#countdown");
let player = null;
let currentId = null;
let tickTimer = null;
let editingRate = false;

function headersAuth() {
  return HOST_KEY
    ? { "Content-Type": "application/json", "X-Host-Key": HOST_KEY }
    : { "Content-Type": "application/json" };
}

function who(it) {
  const n = it.by_name || "-";
  const ip = it.by_ip ? ` (${it.by_ip})` : "";
  return `by ${n}${ip}`;
}

function rQueue(it) {
  return `<div class="item neu-item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg" alt="thumb">
    <div class="flex-1">
      <div class="font-medium">${it.title||it.id}</div>
      <div class="small">${who(it)}</div>
    </div>
    <button class="neu-btn remove-btn" data-id="${it.id}">Remove</button>
  </div>`;
}
function rHistory(it) {
  return `<div class="item neu-item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg" alt="thumb">
    <div class="text-sm">${it.title||it.id}</div>
    <div class="small ml-auto">${who(it)}</div>
  </div>`;
}

window.onYouTubeIframeAPIReady = function () {
  player = new YT.Player("player", {
    videoId: "",
    playerVars: { autoplay: 1, controls: 1 },
    events: { onReady: onPlayerReady, onStateChange: onPlayerStateChange },
  });
};

function onPlayerReady() {
  refresh();
  if (tickTimer) clearInterval(tickTimer);
  tickTimer = setInterval(sendProgressTick, 1000);
}

function onPlayerStateChange(e) {
  if (e.data === YT.PlayerState.ENDED) {
    post("/api/progress", {
      ended: true,
      videoId: currentId,
      pos: player.getDuration(),
      dur: player.getDuration(),
    }).then(() => setTimeout(refresh, 800));
  }
}

async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: headersAuth(), body: JSON.stringify(body || {}) });
  return r.json().catch(() => ({}));
}

async function refresh() {
  try {
    const s = await (await fetch("/api/state")).json();
    queueEl.innerHTML = (s.queue||[]).map(rQueue).join("") || '<div class="small">Queue empty</div>';
    historyEl.innerHTML = (s.history||[]).slice(0,15).map(rHistory).join("") || '<div class="small">No history</div>';

    if (!editingRate) {
      const rateBox = qs("#rate");
      if (rateBox && document.activeElement !== rateBox) {
        rateBox.value = (s.config && s.config.rate_limit_s) || 180;
      }
      const nickBox = qs("#nickLimit");
      if (nickBox && document.activeElement !== nickBox) {
        nickBox.value = (s.config && s.config.nickname_valid_minutes) || 60;
      }
    }

    const cid = s.current && s.current.id;
    if (cid && cid !== currentId && player) {
      currentId = cid;
      player.loadVideoById({ videoId: cid, startSeconds: 0, suggestedQuality: "large" });
    }

    queueEl.querySelectorAll("[data-id]").forEach(btn => {
      btn.onclick = async () => { await post("/api/remove", { id: btn.dataset.id }); await refresh(); };
    });
  } catch (e) { }
}

async function sendProgressTick() {
  if (!player || !HOST_KEY) return;
  try {
    const dur = Number(player.getDuration() || 0);
    const pos = Number(player.getCurrentTime() || 0);
    const vid = currentId;
    if (dur > 0) {
      const remain = Math.max(0, dur - pos);
      if (remain <= 3) { countdown.classList.remove("hidden"); countdown.textContent = Math.ceil(remain); }
      else { countdown.classList.add("hidden"); }
    }
    await post("/api/progress", { videoId: vid, pos, dur, ended: false });
  } catch (e) { }
}

qs("#btnPlay").onclick = async () => { await post("/api/play", {}); await refresh(); };
qs("#btnNext").onclick = async () => { await post("/api/next", {}); await refresh(); };
qs("#btnPrev").onclick = async () => { await post("/api/prev", {}); await refresh(); };
qs("#btnClear").onclick = async () => { await post("/api/clear", {}); await refresh(); };

const btnLogo = qs("#btnLogo");
if (btnLogo) {
  btnLogo.onclick = async () => {
    const f = qs("#logo").files[0];
    if (!f) { alert("Please choose a logo file first."); return; }
    const fd = new FormData(); fd.append("logo", f);
    const r = await fetch("/api/logo", { method: "POST", headers: HOST_KEY ? { "X-Host-Key": HOST_KEY } : {}, body: fd });
    const d = await r.json().catch(() => ({}));
    if (r.ok && d.ok) { alert("✅ Logo uploaded successfully!"); setTimeout(() => location.reload(), 600); }
    else { alert("❌ Upload failed: " + (d.error || "Unknown error")); }
  };
}

const saveBtn = qs("#btnSaveCfg");
if (saveBtn) {
  saveBtn.onclick = async () => {
    const rateVal = parseInt(qs("#rate").value || "180", 10);
    const nickVal = parseInt(qs("#nickLimit").value || "60", 10);

    saveBtn.textContent = "Saving...";
    saveBtn.disabled = true;

    try {
      const r = await fetch("/api/config", {
        method: "POST",
        headers: headersAuth(),
        body: JSON.stringify({ rate_limit_s: rateVal, nickname_valid_minutes: nickVal }),
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok && d.ok) {
        alert(`✅ Settings saved!\nSubmit limit: ${d.rate_limit_s}s\nNickname valid: ${d.nickname_valid_minutes} mins`);
      } else {
        alert(`❌ Failed: ${d.error || "Unknown error"}`);
      }
    } catch (err) {
      alert("⚠️ Network or server error while saving settings.");
    } finally {
      saveBtn.textContent = "Save settings";
      saveBtn.disabled = false;
      await refresh();
    }
  };
}

const rateInput = qs("#rate");
if (rateInput) {
  rateInput.addEventListener("focus", () => { editingRate = true; });
  rateInput.addEventListener("blur", () => { editingRate = false; });
}
const nickInput = qs("#nickLimit");
if (nickInput) {
  nickInput.addEventListener("focus", () => { editingRate = true; });
  nickInput.addEventListener("blur", () => { editingRate = false; });
}

// ===== HOST VERIFY POPUP =====
const overlay = document.getElementById("lockOverlay");
const hostPass = document.getElementById("hostPass");
const btnLogin = document.getElementById("btnHostLogin");
const loginMsg = document.getElementById("loginMsg");

async function tryLogin() {
  const pw = (hostPass.value || "").trim();
  if (!pw) return;
  loginMsg.textContent = "Verifying...";
  try {
    const r = await fetch("/api/host/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw }),
    });
    const d = await r.json().catch(() => ({}));
    if (r.ok && d.ok) {
      overlay.style.display = "none";
      document.body.classList.remove("blurred");
    } else {
      loginMsg.textContent = "❌ Wrong password";
    }
  } catch {
    loginMsg.textContent = "Network error.";
  }
}
if (btnLogin) btnLogin.addEventListener("click", tryLogin);
if (hostPass) hostPass.addEventListener("keydown", (e) => { if (e.key === "Enter") tryLogin(); });

// ===== CHANGE HOST PASSWORD =====
const btnChange = document.getElementById("btnChangePass");
if (btnChange) {
  btnChange.onclick = async () => {
    const oldp = (document.getElementById("oldPass").value || "").trim();
    const newp = (document.getElementById("newPass").value || "").trim();
    const key = (document.getElementById("masterKey").value || "").trim();
    const msg = document.getElementById("changeMsg");

    msg.textContent = "Processing...";
    try {
      const r = await fetch("/api/host/change_password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_password: oldp, new_password: newp, key }),
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok && d.ok) {
        msg.textContent = "✅ Password updated successfully!";
        document.getElementById("oldPass").value = "";
        document.getElementById("newPass").value = "";
        document.getElementById("masterKey").value = "";
      } else {
        msg.textContent = "❌ " + (d.error || "Update failed.");
      }
    } catch {
      msg.textContent = "Network error.";
    }
  };
}

// Kick things off
refresh();
setInterval(refresh, 2000);

/* =========================================================
   v01.6.2b — 2025-10-23 — Chat Fix
   - Sửa lỗi: nút "Gửi 💬" không hoạt động do JS chạy trước DOM
   - Bổ sung: nhấn phím Enter cũng gửi được tin nhắn
   - Giữ nguyên style và logic cũ
========================================================= */

window.addEventListener('DOMContentLoaded', () => {
  if (typeof io === 'undefined') return; // chưa load socket.io ⇒ bỏ qua

  const socket = io();

  const chatBox = document.getElementById('chat-box');
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');

  if (!chatBox || !chatInput || !sendBtn) return;

  // Escape HTML
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    })[c]);
  }

  function getNickname() {
    try {
      const ls = localStorage.getItem('nickname');
      if (ls && ls.trim()) return ls.trim();
    } catch (e) {}
    return 'Host';
  }

  // Nhận tin nhắn broadcast
  socket.on('chat_message', (data) => {
    const nameTag = data.role === 'host'
      ? `<strong style="color:#2563eb;">[HOST]</strong> ${escapeHtml(data.user)}`
      : `<strong>${escapeHtml(data.user)}</strong>`;
    const row = document.createElement('div');
    row.style.marginBottom = '6px';
    row.innerHTML = `${nameTag}: ${escapeHtml(data.msg)}`;
    chatBox.appendChild(row);
    chatBox.scrollTop = chatBox.scrollHeight;
  });

  // Hàm gửi tin
  function sendMessage() {
    const text = (chatInput.value || '').trim();
    if (!text) return;
    socket.emit('chat_message', {
      user: getNickname(),
      role: (window.IS_HOST ? 'host' : 'user'),
      msg: text,
      timestamp: new Date().toISOString()
    });
    chatInput.value = '';
  }

  // Gắn sự kiện Click và Enter
  sendBtn.addEventListener('click', sendMessage);
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault(); // tránh xuống dòng
      sendMessage();
    }
  });
});

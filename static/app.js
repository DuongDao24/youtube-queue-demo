// ==========================================================
// YouTube Queue Online — v01.6.1
// Ngày cập nhật: 17/10/2025
// Loại cập nhật: Nickname bắt buộc trước khi submit
// - UI nickname (get/set) với hiệu lực theo phút từ host
// - Queue/History hiển thị "by nickname" (không lộ IP)
// =========================================================

const qEl = document.getElementById('queue');
const hEl = document.getElementById('history');
const playing = document.getElementById('playing');
const pbar = document.getElementById('pbar');
const msgEl = document.getElementById('msg');
const btnAdd = document.getElementById('btnAdd');

const nickForm = document.getElementById('nickForm');
const nickInput = document.getElementById('nickInput');
const nickMsg = document.getElementById('nickMsg');
const nickInfo = document.getElementById('nickInfo');

let nicknameOK = false;

function rowQueue(it, idx){
  const name = it.by_name ? it.by_name : "-";
  return `<div class="item neu-item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg" alt="thumb">
    <div class="flex-1">
      <div class="font-medium">${it.title||it.id}</div>
      <div class="small">#${idx+1} • by ${name}</div>
    </div>
  </div>`;
}
function rowHistory(it){
  const name = it.by_name ? it.by_name : "-";
  return `<div class="item neu-item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg" alt="thumb">
    <div class="flex-1">
      <div class="text-sm">${it.title||it.id}</div>
      <div class="small">by ${name}</div>
    </div>
  </div>`;
}
function renderState(s){
  document.getElementById('limit').textContent = (s.config&&s.config.rate_limit_s)||180;
  playing.innerHTML = s.current ? `<img class="thumb" src="https://i.ytimg.com/vi/${s.current.id}/hqdefault.jpg" alt="thumb">
      <div><div class="font-semibold">${s.current.title||s.current.id}</div>
      <a class="text-blue-600 text-sm" target="_blank" href="https://www.youtube.com/watch?v=${s.current.id}">Open on YouTube</a></div>`
    : '<div class="small">No current.</div>';
  const p = s.progress || {}; const pos = p.pos||0, dur = p.dur||0;
  pbar.style.width = dur>0 ? Math.min(100, Math.round(pos*100/dur))+'%' : '0%';
  qEl.innerHTML = (s.queue||[]).map((it,i)=>rowQueue(it,i)).join("") || '<div class="small">Empty</div>';
  hEl.innerHTML = (s.history||[]).slice(0,15).map(rowHistory).join("") || '<div class="small">No history</div>';
}

async function loadState(){
  try{
    const s = await (await fetch('/api/state')).json();
    renderState(s);
  }catch(e){}
}

// ---- Nickname flow ----
async function checkNickname() {
  try {
    const r = await fetch('/api/nickname');
    const d = await r.json();
    if (d.ok) {
      nicknameOK = !!d.valid;
      if (d.valid) {
        nickInfo.textContent = `Welcome, ${d.name}! (expires in ${d.remain_mins} mins)`;
        if (nickForm) nickForm.style.display = "none";
      } else {
        nickInfo.textContent = `Please set your nickname (valid for ${d.limit_mins} mins).`;
        if (nickForm) nickForm.style.display = "flex";
      }
    }
  } catch (e) {}
}

if (nickForm) {
  nickForm.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const name = (nickInput.value || '').trim();
    if (!name) return;
    nickMsg.textContent = 'Saving...';
    try{
      const r = await fetch('/api/nickname', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name })});
      const d = await r.json().catch(()=>({}));
      if (!r.ok || !d.ok) {
        nickMsg.textContent = d.error || 'Cannot save nickname.';
      } else {
        nickMsg.textContent = 'Saved!';
        await checkNickname();
      }
    }catch(err){
      nickMsg.textContent = 'Network error.';
    }
  });
}

// ---- Add video ----
document.getElementById('addForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const url = document.getElementById('url').value.trim();
  if(!url){ return; }
  if (!nicknameOK) {
    msgEl.textContent = 'Please set your nickname first.';
    return;
  }
  msgEl.textContent = 'Submitting...';
  btnAdd.disabled = true;
  try{
    const r = await fetch('/api/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});
    const d = await r.json().catch(()=>({}));
    if(!r.ok){
      msgEl.textContent = d.error || 'Error adding video.';
    }else{
      msgEl.textContent = 'Added: ' + (d.item?.title||d.item?.id||'');
      document.getElementById('url').value='';
      await loadState();
    }
  }catch(err){ msgEl.textContent = 'Network error. Please try again.'; }
  finally{ btnAdd.disabled = false; }
});

setInterval(loadState, 2000);
(async ()=>{ await checkNickname(); await loadState(); })();

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

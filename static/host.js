const $ = s => document.querySelector(s);
let PLAYER, CURRENT_ID = null, POLL = null, LOGGED = false;

async function api(url, data){
  const r = await fetch(url, {
    method: data ? "POST" : "GET",
    headers: {"Content-Type":"application/json"},
    body: data ? JSON.stringify(data) : undefined
  });
  return await r.json();
}

function onYouTubeIframeAPIReady(){
  PLAYER = new YT.Player('player', {
    width: '100%', height: '100%',
    playerVars: {autoplay:1, rel:0, controls:1},
    events: { onStateChange }
  });
}
window.onYouTubeIframeAPIReady = onYouTubeIframeAPIReady;

function ensureLoginUI(){ $('#loginBackdrop').style.display = LOGGED ? 'none' : 'flex'; }

async function login(){
  const u = $('#lgUser').value.trim();
  const p = $('#lgPass').value.trim();
  if(!u || !p) return;
  const r = await api('/api/login',{username:u,password:p});
  if(r.ok){ LOGGED=true; ensureLoginUI(); refresh(); }
  else alert('Not authorized or error');
}

function loadVideo(id){
  if(!PLAYER || !id) return;
  CURRENT_ID = id;
  try{ PLAYER.loadVideoById(id); }catch(e){}
}

async function next(){ await api('/api/next',{}); await refresh(); }
async function clearQ(){ await api('/api/clear',{}); await refresh(); }

async function saveSettings(){
  const rate = parseInt($('#rate').value||'60',10);
  const nh = parseInt($('#nickHours').value||'24',10);
  const r = await api('/api/settings',{rate_limit_s:rate, nick_change_hours:nh});
  if(!r.ok) alert('Cannot save settings'); else refresh();
}
async function saveHostAuth(){
  const newUser=$('#newUser').value.trim(), newPass=$('#newPass').value.trim(), key=$('#hostKey').value.trim();
  if(!key){ alert('HOST_API_KEY required'); return; }
  const r = await api('/api/host_auth',{new_user:newUser,new_pass:newPass,host_api_key:key});
  if(!r.ok) alert('Not authorized or error'); else alert('Updated.');
}

function elItem(it){
  const d = document.createElement('div'); d.className='item';
  d.innerHTML = `<img class="thumb" src="${it.thumb||''}" onerror="this.style.display='none'">
  <div><div><b>${it.title}</b></div><div class="muted">#${it.idx} • by ${it.by||'Guest'}</div></div>`;
  return d;
}

async function refresh(){
  const s = await api('/api/state'); LOGGED = !!s.host; ensureLoginUI(); if(!s.ok) return;

  $('#rate').value = s.settings.rate_limit_s;
  $('#nickHours').value = s

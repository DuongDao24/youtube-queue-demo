// host.js — v02.3
let PLAYER, YT_READY=false, AUTH={u:'Admin',p:'0000'}, STATE={}, CD_T=null;

function $(id){return document.getElementById(id)}
function htmlItem(x, showIp){
  return `<div class="item">
    <img class="it" src="${x.thumb}">
    <div class="it2">
      <div class="t">${x.title||x.id}</div>
      <div class="muted">by <b>${x.who||'Guest'}</b>${showIp? ' • '+(x.ip||''): ''}</div>
    </div>
  </div>`;
}

function fetchState(){
  return fetch('/api/state?host=1').then(r=>r.json()).then(s=>{
    STATE = s;
    $('limit').value = s.settings.submit_limit_s;
    $('nickh').value = s.settings.nick_change_hours;

    $('queue').innerHTML = (s.queue.map(it=>htmlItem(it,true)).join('')) || '<div class="muted">Queue empty</div>';
    $('history').innerHTML = (s.history.map(it=>htmlItem(it,true)).join('')) || '<div class="muted">No history</div>';

    if (YT_READY && s.playing && (!STATE._loadedId || STATE._loadedId!==s.playing.id)){
      loadVideo(s.playing.id);
    }
  });
}

function authHeader(){
  return {'X-Host-Auth': `${AUTH.u}:${AUTH.p}`,'Content-Type':'application/json'};
}
function postJSON(url, body){ return fetch(url,{method:'POST',headers:authHeader(),body:JSON.stringify(body||{})}).then(r=>r.json()); }

function onYouTubeIframeAPIReady(){ YT_READY=true; createPlayer(); }
window.onYouTubeIframeAPIReady = onYouTubeIframeAPIReady;

function createPlayer(){
  PLAYER = new YT.Player('player',{
    videoId: null,
    playerVars: { autoplay:1, rel:0, playsinline:1 },
    events: { onReady: ()=>{}, onStateChange: onState }
  });
}
function loadVideo(id){
  STATE._loadedId = id;
  if (PLAYER && PLAYER.loadVideoById) PLAYER.loadVideoById(id, 0, "large");
  hideCountdown();
}
function onState(e){
  const s = e.data;
  if (s === YT.PlayerState.PLAYING){
    tickProgress();
    startCountdownWatcher();
  }else if (s === YT.PlayerState.ENDED){
    postJSON('/api/progress', {videoId:STATE._loadedId, pos:0, dur:0, ended:true}).then(()=>fetchState());
  }else if (s === YT.PlayerState.PAUSED){
    hideCountdown();
  }
}
function tickProgress(){
  if (!PLAYER || PLAYER.getDuration===undefined) return;
  const pos = PLAYER.getCurrentTime? PLAYER.getCurrentTime():0;
  const dur = PLAYER.getDuration? PLAYER.getDuration():0;
  postJSON('/api/progress',{videoId:STATE._loadedId,pos,dur});
  setTimeout(tickProgress, 2000);
}
function startCountdownWatcher(){
  if (CD_T) clearInterval(CD_T);
  CD_T = setInterval(()=>{
    if (!PLAYER) return;
    const pos = PLAYER.getCurrentTime? PLAYER.getCurrentTime():0;
    const dur = PLAYER.getDuration? PLAYER.getDuration():0;
    if (dur>0 && dur-pos<=10){
      showCountdown(Math.max(0,Math.ceil(dur-pos)));
      if (dur-pos<=0.5){ clearInterval(CD_T); }
    } else {
      hideCountdown();
    }
  }, 500);
}
function showCountdown(n){ $('countdown').classList.remove('hidden'); $('cd').textContent = n; }
function hideCountdown(){ $('countdown').classList.add('hidden'); }

$('btnPrev').onclick = ()=> postJSON('/api/prev').then(()=>fetchState());
$('btnNext').onclick = ()=> postJSON('/api/next').then(()=>fetchState());
$('btnClear').onclick= ()=> postJSON('/api/clear').then(()=>fetchState());

$('btnPause').onclick = ()=>{
  if (!PLAYER) return;
  const st = PLAYER.getPlayerState();
  if (st===YT.PlayerState.PLAYING) PLAYER.pauseVideo();
  else PLAYER.playVideo();
};

$('btnSaveSettings').onclick = ()=>{
  const submit_limit_s = parseInt($('limit').value||'60',10);
  const nick_change_hours = parseInt($('nickh').value||'24',10);
  fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    _user:AUTH.u,_pass:AUTH.p, submit_limit_s, nick_change_hours
  })}).then(r=>r.json()).then(()=>fetchState());
};

$('btnSaveAuth').onclick = ()=>{
  const user = $('newUser').value.trim();
  const pass = $('newPass').value.trim();
  const host_api_key = $('hostKey').value.trim();
  fetch('/api/host_auth_update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user,pass,host_api_key})})
    .then(r=>r.json()).then(j=>{
      if (j.ok){ AUTH.u = user||'Admin'; AUTH.p = pass||'0000'; alert('Updated!'); } else alert('Key mismatch');
    });
};

const modal = $('m'); const lu=$('lu'), lp=$('lp'), blogin=$('blogin');
function showLogin(){ modal.style.display='flex'; lu.focus(); }
function hideLogin(){ modal.style.display='none'; }
function tryLogin(){
  AUTH.u = lu.value.trim() || 'Admin';
  AUTH.p = lp.value || '0000';
  fetch('/api/host_login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user:AUTH.u,pass:AUTH.p})})
    .then(r=>r.json()).then(j=>{ if (j.ok){ hideLogin(); fetchState(); } else $('lmsg').textContent='Wrong username or password'; });
}
blogin.onclick=tryLogin; lp.addEventListener('keydown',e=>{if(e.key==='Enter')tryLogin();});
lu.addEventListener('keydown',e=>{if(e.key==='Enter')tryLogin();});

showLogin();
setInterval(fetchState, 2000);

window.onYouTubeIframeAPIReady = function(){
  if (!window.YT) return;
  createPlayer();
  YT_READY = true;
  fetchState();
}

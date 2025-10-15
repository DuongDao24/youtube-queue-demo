const qEl = document.getElementById('queue');
const hEl = document.getElementById('history');
const playing = document.getElementById('playing');
const pbar = document.getElementById('pbar');
const msgEl = document.getElementById('msg');

function who(it){
  const name = it.by_name || '';
  const ip   = it.by_ip || '';
  return name ? `${name} (${ip})` : ip;
}
function rowQueue(it, idx){
  return `<div class="item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg">
    <div class="flex-1">
      <div class="font-medium">${it.title||it.id}</div>
      <div class="small">#${idx+1} • by ${who(it)}</div>
    </div>
  </div>`;
}
function rowHistory(it){
  return `<div class="item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg">
    <div class="flex-1">
      <div class="text-sm">${it.title||it.id}</div>
      <div class="small">by ${who(it)}</div>
    </div>
  </div>`;
}
function renderState(s){
  document.getElementById('limit').textContent = (s.config&&s.config.rate_limit_s)||180;
  playing.innerHTML = s.current ? `<img class="thumb" src="https://i.ytimg.com/vi/${s.current.id}/hqdefault.jpg">
      <div><div class="font-semibold">${s.current.title||s.current.id}</div>
      <a class="text-blue-600 text-sm" target="_blank" href="https://www.youtube.com/watch?v=${s.current.id}">Open on YouTube</a></div>`
    : '<div class="small">No current.</div>';
  const p = s.progress || {}; const pos = p.pos||0, dur = p.dur||0;
  if (pbar) pbar.style.width = dur>0 ? Math.min(100, Math.round(pos*100/dur))+'%' : '0%';
  qEl.innerHTML = (s.queue||[]).map((it,i)=>rowQueue(it,i)).join("") || '<div class="small">Empty</div>';
  hEl.innerHTML = (s.history||[]).slice(0,15).map(rowHistory).join("") || '<div class="small">No history</div>';
}
async function load(){
  const s = await (await fetch('/api/state')).json();
  renderState(s);
}
document.getElementById('addForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const url = document.getElementById('url').value.trim();
  msgEl.textContent = 'Submitting...';
  try{
    const r = await fetch('/api/add',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({url, name: (localStorage.getItem('ytq_name')||'').trim()})
    });
    const d = await r.json();
    if(!r.ok) throw new Error(d.error||'Error');
    msgEl.textContent = 'Added: ' + (d.item.title||d.item.id);
    document.getElementById('url').value='';
    load();
  }catch(err){ msgEl.textContent = 'Error: ' + err.message; }
});

async function initName(){
  try{
    const s = await (await fetch('/api/name')).json();
    if(!localStorage.getItem('ytq_name') && s.name){
      localStorage.setItem('ytq_name', s.name);
    }
    document.getElementById('nickname').value = localStorage.getItem('ytq_name') || s.name || '';
  }catch{}
}
document.getElementById('saveName').onclick = async ()=>{
  const name = document.getElementById('nickname').value.trim();
  const out = document.getElementById('nameMsg');
  out.textContent = 'Saving...';
  try{
    const r = await fetch('/api/name',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
    const d = await r.json();
    if(!r.ok) throw new Error(d.error||'Error');
    localStorage.setItem('ytq_name', d.name);
    out.textContent = 'Saved';
  }catch(e){ out.textContent = e.message; }
};

setInterval(load, 2000);
initName();
load();

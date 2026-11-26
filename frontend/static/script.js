const $=(s,r=document)=>r.querySelector(s);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const SV=4;
let S=(()=>{try{return JSON.parse(localStorage.getItem("ns")||localStorage.getItem("cl")||"null")}catch(e){return null}})()||{lang:"uz",user:null,done:{},scores:{},coins:0,certs:[],qa:[],db:JSON.parse(JSON.stringify(SEED))};
let authMode="register"; // Ro‘yxatdan o‘tish birinchi bo‘lib ochiladi.
if(S.v!==SV){const F=JSON.parse(JSON.stringify(SEED)),o=S.db||{};
const mg=(a,b,f)=>a.map(x=>{const y=(b||[]).find(z=>z.id===x.id);return y&&f?f(x,y):x}).concat((b||[]).filter(y=>!a.some(x=>x.id===y.id)));
S.db={fields:mg(F.fields,o.fields),courses:mg(F.courses,o.courses,(x,y)=>({...x,topics:x.topics.concat((y.topics||[]).filter(p=>!x.topics.some(z=>z.id===p.id)))})),mentors:o.mentors||F.mentors,contests:mg(F.contests,o.contests,(x,y)=>({...x,status:y.status})),rules:o.rules||F.rules};S.v=SV}
const save=()=>{try{localStorage.setItem("ns",JSON.stringify(S))}catch(e){}};
const t=k=>(I18N[S.lang]&&I18N[S.lang][k])||I18N.en[k]||k;
const L=x=>typeof x==="object"?(x[S.lang]||x.en):x;
const key=(c,i)=>c+":"+i, pass=()=>+S.db.rules.pass;
const course=id=>S.db.courses.find(c=>c.id===id);
const isAdmin=()=>S.user&&S.user.role==="admin";
const qparse=s=>String(s).split("\n").map(l=>l.split("|").map(x=>x.trim())).filter(p=>p.length>=4).map(p=>({q:p[0],o:p.slice(1,-1),c:Math.min(Math.max((/^[a-z]$/i.test(p[p.length-1])?p[p.length-1].toUpperCase().charCodeAt(0)-64:(+p[p.length-1]||1))-1,0),p.length-3)}));
const shuffle=a=>{a=a.slice();for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]]}return a};
const prog=c=>c.topics.filter(x=>S.done[key(c.id,x.id)]).length;
const bar=(a,b)=>`<div class="bar2"><i style="width:${b?100*a/b:0}%"></i></div>`;
let run=null,tab="ai",chat=[],acts={},forms={};

function toast(m){const e=$("#toast");e.textContent=m;e.className="on";clearTimeout(toast.t);toast.t=setTimeout(()=>e.className="",3200)}
function render(h){$("#app").innerHTML=h}
// Render assistant replies as safe GitHub-Flavored Markdown.
function renderMarkdown(source){
  const raw=String(source??"");
  if(!window.marked || !window.DOMPurify) return esc(raw).replace(/\n/g,"<br>");
  const rendered=window.marked.parse(raw,{gfm:true,breaks:true});
  return window.DOMPurify.sanitize(rendered,{
    USE_PROFILES:{html:true},
    ADD_ATTR:["target","rel"]
  }).replace(/<a\s+(?![^>]*\brel=)/gi,'<a rel="noopener noreferrer" target="_blank" ');
}
function video(u){
  if(!u)return'<div class="video">🎬</div>';
  const y=u.match(/(?:youtu\.be\/|v=|embed\/)([\w-]{11})/);
  return y?`<iframe class="video" src="https://www.youtube-nocookie.com/embed/${y[1]}" allowfullscreen title="video"></iframe>`:`<video class="video" controls src="${esc(u)}"></video>`;
}
async function askAI(q){
  if(CONFIG.AI_ENDPOINT){try{const r=await fetch(CONFIG.AI_ENDPOINT,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({q,lang:S.lang})});return(await r.json()).answer}catch(e){}}
  return t("ai_demo");
}

Object.assign(I18N.uz,{qs_err:"Savollar formati noto‘g‘ri. Har qatorda: Savol|A|B|C|to‘g‘ri javob raqami",no_q:"Bu mavzuda hozircha savol yo‘q.",start:"Boshlash",cont:"Davom etish",none_c:"Hozircha kurs yo‘q."});
Object.assign(I18N.en,{qs_err:"Invalid question format. One per line: Question|A|B|C|correct number",no_q:"This topic has no questions yet.",start:"Start",cont:"Continue",none_c:"No courses yet."});
Object.assign(I18N.ru,{qs_err:"Неверный формат вопросов. В строке: Вопрос|A|B|C|номер верного",no_q:"В этой теме пока нет вопросов.",start:"Начать",cont:"Продолжить",none_c:"Курсов пока нет."});
let chatK="";
const CHK='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
const FI={web:'<path d="M8 8l-5 4 5 4M16 8l5 4-5 4M14 5l-4 14"/>',py:'<path d="M5 7l5 5-5 5M12 18h7"/>',ds:'<path d="M12 3l7 7-8 9-6 1 1-6zM14 6l4 4"/>'};
const fic=f=>FI[f.id]?`<svg class="gi" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${FI[f.id]}</svg>`:`<span class="gi e">${f.icon||"✦"}</span>`;
const PAL=[["#d6177a","#ff6fb1","#ffc4de",1],["#fff0f7","#ffd0e5","#ff8fc3",0],["#a8106a","#f23c94","#ffa6d2",1],["#fff4ef","#ffd6e7","#ff7ab8",0]];
const amp=s=>esc(s).replace(/&amp;/g,'<i class="amp">&amp;</i>');
const pal=c=>{const p=PAL[Math.max(0,S.db.courses.indexOf(c))%4];return{cls:p[3]?"dk":"lt",st:`--a:${p[0]};--b:${p[1]};--c:${p[2]}`}};
const RINGS='<svg viewBox="0 0 260 260" aria-hidden="true"><circle cx="150" cy="110" r="100"/><circle cx="150" cy="110" r="72"/><circle cx="150" cy="110" r="44"/></svg>';
const cinfo=c=>({n:c.topics.length,d:prog(c),k:c.topics.reduce((a,x)=>a+(+x.coins||0),0)});
const cmeta=c=>{const i=cinfo(c);return`<div class="meta"><span>${i.n} ${t("topics").toLowerCase()}</span><span>${i.k} ${t("coins").toLowerCase()}</span></div>`};
const fname=c=>{const f=S.db.fields.find(x=>x.id===c.field);return f?esc(L(f.name)):""};
function ccard(c){const p=pal(c),i=cinfo(c);
  return`<a class="course ${p.cls}" href="#/course/${c.id}" style="${p.st}"><div class="cv">${RINGS}<div class="pr"><span class="pill">${fname(c)}</span>${c.lvl?`<span class="pill">${esc(L(c.lvl))}</span>`:""}</div><h3>${amp(L(c.title))}</h3></div><div class="cb">${c.sub?`<p>${esc(L(c.sub))}</p>`:""}${cmeta(c)}${bar(i.d,i.n)}<div class="go"><small class="sub">${i.d}/${i.n}</small><span>${i.d?t("cont"):t("start")}</span></div></div></a>`}
const navOn=p=>{const h=location.hash||"#/";if(p==="#/")return h==="#/"||/^#\/(field|course|lesson)\b/.test(h);if(p==="#/practice")return/^#\/(practice|quiz)\b/.test(h);if(p==="#/contests")return/^#\/contests?\b/.test(h);return h.startsWith(p)};
const ltabs=()=>["ai","mentor"].map(k=>`<button class="${tab===k?"on":""}" data-act="tab" data-v="${k}">${t(k)}</button>`).join("");
function lpanel(cid,tid){
  if(tab==="ai")return`<div class="msgs" aria-live="polite">${chat.map(m=>`<div class="m ${m.u?"u":""}">${m.u?esc(m.x):renderMarkdown(m.x)}</div>`).join("")}</div><form class="f" data-form="ai"><input name="q" placeholder="${t("ask_ph")}" required autocomplete="off"><button class="btn">${t("send")}</button></form>`;
  if(!S.db.mentors.length)return`<p>${t("no_mentors")}</p>`;
  return`<form class="f" data-form="mentor"><label>${t("mentor")}<select name="m" style="width:100%">${S.db.mentors.map(m=>`<option value="${m.id}">${esc(m.name)} · ${esc(m.spec)}</option>`).join("")}</select></label><textarea name="q" rows="3" placeholder="${t("ask_ph")}" required></textarea><button class="btn">${t("send")}</button></form>`+S.qa.filter(q=>q.k===key(cid,tid)).map(q=>`<div class="row" style="margin-top:10px"><span class="nm">${esc(q.q)}<small>${esc(q.mn)}</small></span><span class="tag">${t("pending")}</span></div>`).join("");
}
function paintLP(){const p=$("#lp");if(!p)return;const h=location.hash.split("/");p.innerHTML=lpanel(h[2],h[3]);const b=$("#lt");if(b)b.innerHTML=ltabs();const f=$("#lp input,#lp textarea");if(f&&tab==="ai")f.focus()}
const views={
login(){
  return`<section class="login-wrap"><div class="hero"><span class="badge">${t("h_badge")}</span><h1>${t("h_title")}</h1><p>${t("h_sub")}</p>
  <div class="stats"><div class="stat"><b>${CONFIG.MEMBERS}+</b><span>${t("h_s1")}</span></div><div class="stat"><b>${S.db.fields.length}</b><span>${t("h_s2")}</span></div><div class="stat"><b>${S.db.courses.length}</b><span>${t("h_s3")}</span></div></div></div>
  <div class="card login f"><h1>${authMode==="register"?"Ro‘yxatdan o‘tish":t("login_t")}</h1><p class="sub">${authMode==="register"?"Yangi hisob yaratish uchun ma’lumotlaringizni kiriting.":"Email va parolingiz bilan hisobingizga kiring."}</p>
  ${authMode==="register"?`<form class="f" data-form="auth-register"><label>Ism va familiya<input name="name" minlength="2" maxlength="120" autocomplete="name" required></label><label>Email<input name="email" type="email" autocomplete="email" required></label><label>Parol (kamida 8 belgi)<input name="password" type="password" minlength="8" autocomplete="new-password" required></label><label>Parolni tasdiqlang<input name="confirm" type="password" minlength="8" autocomplete="new-password" required></label><button class="btn">Ro‘yxatdan o‘tish</button></form><button type="button" class="auth-switch" data-act="auth-mode" data-v="login">Hisobingiz allaqachon bormi? Kirish</button>`:`<form class="f" data-form="auth-login"><label>Email<input name="email" type="email" autocomplete="email" required></label><label>Parol<input name="password" type="password" minlength="8" autocomplete="current-password" required></label><button class="btn">${t("login_open")}</button></form><button type="button" class="auth-switch" data-act="auth-mode" data-v="register">Hisobingiz yo‘qmi? Ro‘yxatdan o‘tish</button>`}
  <div class="divider" style="margin:18px 0;text-align:center">— Admin kirishi —</div>
  <form class="f" data-form="admin-login"><label>Admin login<input name="login" autocomplete="username" required></label><label>Parol<input name="password" type="password" autocomplete="current-password" required></label><button class="btn ghost">Admin sifatida kirish</button></form></div></section>`;
},
home(){
  const live=S.db.contests.find(k=>k.status==="active"),nd=Object.keys(S.done).length;
  return`<section class="hero"><span class="badge">${t("h_badge")}</span><h1>${t("hi")}, <em>${esc(S.user.name)}</em></h1><p>${t("h_sub")}</p>
  <div class="stats"><div class="stat"><b>${S.coins}</b><span>${t("coins")}</span></div><div class="stat"><b>${nd}</b><span>${t("lessons_done")}</span></div><div class="stat"><b>${S.db.courses.length}</b><span>${t("h_s3")}</span></div></div></section>`+
  (live?`<a class="banner" href="#/contests"><b>${t("live_banner")}</b> ${esc(live.title)}</a>`:"")+
  `<h2>${t("pick")}</h2><div class="grid">`+S.db.fields.map(f=>`<a class="card pick fcard" href="#/field/${f.id}"><span class="ic">${fic(f)}</span><h3>${esc(L(f.name))}</h3><p>${S.db.courses.filter(c=>c.field===f.id).length} ${t("courses").toLowerCase()}</p></a>`).join("")+`</div>`+
  `<h2>${t("courses")}</h2><div class="grid cg">`+S.db.courses.map(ccard).join("")+`</div>`;
},
field(id){
  const f=S.db.fields.find(x=>x.id===id);if(!f)return views.home();
  const cs=S.db.courses.filter(c=>c.field===id);
  return`<a class="back" href="#/">← ${t("back")}</a><h1>${esc(L(f.name))}</h1>`+(cs.length?`<div class="grid cg">${cs.map(ccard).join("")}</div>`:`<div class="card">${t("none_c")}</div>`);
},
course(id){
  const c=course(id);if(!c)return views.home();const p=pal(c),i=cinfo(c);
  return`<a class="back" href="#/field/${c.field}">← ${t("back")}</a><section class="chero ${p.cls}" style="${p.st}">${RINGS}<span class="pill">${fname(c)}</span><h1>${amp(L(c.title))}</h1>${c.sub?`<p>${esc(L(c.sub))}</p>`:""}${cmeta(c)}${bar(i.d,i.n)}</section><h2>${t("topics")}</h2>`+
  c.topics.map((x,n)=>{const dn=S.done[key(c.id,x.id)];return`<a class="row" href="#/lesson/${c.id}/${x.id}"><span class="num ${dn?"ok":""}">${dn?CHK:n+1}</span><span class="nm">${esc(L(x.title))}</span>${dn?`<span class="tag ok">${t("done")}</span>`:`<span class="tag">${t("open")}</span>`}</a>`}).join("");
},
lesson(cid,tid){
  const c=course(cid),x=c&&c.topics.find(z=>z.id===tid);if(!x)return views.home();
  if(chatK!==cid+tid){chat=[];chatK=cid+tid}
  const h=`<a class="back" href="#/course/${cid}">← ${esc(L(c.title))}</a><h1>${esc(L(x.title))}</h1>${video(x.video)}`;
  if(!S.done[key(cid,tid)])return h+`<div class="gap"><button class="btn" data-act="complete" data-c="${cid}" data-t="${tid}">${t("complete")}</button></div>`;
  return h+`<h2>${t("after_t")}</h2><div class="tabs" id="lt">${ltabs()}</div><div class="card" id="lp">${lpanel(cid,tid)}</div><div class="gap"><a class="btn" href="#/quiz/${cid}/${tid}">${t("go_test")}</a></div>`;
},
practice(){
  const cs=S.db.courses.filter(c=>prog(c));
  let h=`<h1>${t("practice_t")}</h1><p class="sub">${t("practice_s")}</p><p class="sub">${t("tip_coin")}</p>`;
  if(!cs.length)return h+`<div class="card" style="margin-top:16px">${t("none_done")}</div>`;
  return h+cs.map(c=>{
    const all=c.topics.every(x=>(S.scores[key(c.id,x.id)]||0)>=pass());
    return`<h2>${esc(L(c.title))}</h2>`+c.topics.filter(x=>S.done[key(c.id,x.id)]).map(x=>{const s=S.scores[key(c.id,x.id)];return`<a class="row" href="#/quiz/${c.id}/${x.id}"><span class="nm">${esc(L(x.title))}${s!==undefined?`<small>${t("result")}: ${s}%</small>`:""}</span><span class="tag ${s>=pass()?"ok":""}">${s!==undefined?t("retake"):t("take")}</span></a>`}).join("")+
    (all?`<div class="gap"><a class="btn" href="#/cert/${c.id}">🏅 ${t("cert_get")}</a></div>`:`<p class="sub">${t("cert_need")}</p>`);
  }).join("");
},
contests(){
  const ks=S.db.contests;
  return`<h1>${t("contests_t")}</h1>`+(ks.length?ks.map(k=>`<div class="card" style="margin-bottom:14px"><span class="tag ${k.status==="active"?"live":""}">${t("st_"+k.status)}</span><h3 style="margin:10px 0 4px">${esc(k.title)}</h3><p>${t("reward")}: ${t("r_"+k.reward)}${k.reward!=="cert"?" · "+k.coins:""}</p>${S.scores["k:"+k.id]!==undefined?`<p>${t("result")}: ${S.scores["k:"+k.id]}%</p>`:""}${k.status==="active"&&S.scores["k:"+k.id]===undefined?`<div class="gap"><a class="btn" href="#/contest/${k.id}">${t("join")}</a></div>`:""}</div>`).join(""):`<div class="card">${t("no_contests")}</div>`);
},
me(){
  return`<h1>${esc(S.user.name)}</h1><div class="grid"><div class="card"><p>${t("coins")}</p><div class="big">🪙 ${S.coins}</div></div><div class="card"><p>${t("lessons_done")}</p><div class="big">${Object.keys(S.done).length}</div></div></div><section class="card" style="margin-top:16px"><h3>🔗 Telegram hisobini bog'lash</h3><p class="sub">Telegram botda /myid buyrug'ini yuboring va chiqqan raqamni kiriting. Shunda bot coin balansingiz va musobaqalaringizni ko'ra oladi.</p><form data-form="telegram-link" class="f"><label>Telegram ID<input name="telegram_id" inputmode="numeric" pattern="[0-9]+" placeholder="123456789" required></label><button class="btn">Telegramni bog'lash</button></form></section><h2>${t("my_certs")}</h2>`+
  (S.certs.length?S.certs.map(id=>`<a class="row" href="#/cert/${id}"><span>🏅</span><span class="nm">${esc(certTitle(id))}</span></a>`).join(""):`<p class="sub">—</p>`);
},
cert(id){
  const kk=S.db.contests.find(k=>k.id===id),cc=course(id),ok=kk?(S.scores["k:"+id]>=pass()&&kk.reward!=="coin"):!!cc&&cc.topics.length>0&&cc.topics.every(x=>(S.scores[key(id,x.id)]||0)>=pass());
  if(!ok)return`<div class="card">${t("cert_need")}</div>`;
  if(!S.certs.includes(id)){S.certs.push(id);save()}
  setTimeout(()=>drawCert($("#cv"),S.user.name,certTitle(id),id),0);
  return`<a class="back" href="#/me">← ${t("back")}</a><h1>🏅 ${t("cert_of")}</h1><canvas id="cv" width="1200" height="850"></canvas><div class="gap"><button class="btn" data-act="dl">${t("download")}</button></div>`;
}};
function certTitle(id){const k=S.db.contests.find(x=>x.id===String(id));return k?k.title:L((course(String(id))||{title:id}).title)}
function drawCert(cv,name,title,id){
  if(!cv)return;const g=cv.getContext("2d"),W=1200,H=850;
  const paint=()=>{
  let gr=g.createLinearGradient(0,0,W,H);gr.addColorStop(0,"#fff9fc");gr.addColorStop(.55,"#ffe6f1");gr.addColorStop(1,"#ffc6e0");g.fillStyle=gr;g.fillRect(0,0,W,H);
  [[0,0,520,"rgba(255,111,174,.35)"],[W,H,560,"rgba(225,29,116,.22)"]].forEach(o=>{const r=g.createRadialGradient(o[0],o[1],0,o[0],o[1],o[2]);r.addColorStop(0,o[3]);r.addColorStop(1,"rgba(255,255,255,0)");g.fillStyle=r;g.fillRect(0,0,W,H)});
  const gold=g.createLinearGradient(0,0,W,0);gold.addColorStop(0,"#d98a7a");gold.addColorStop(.5,"#ffe6d6");gold.addColorStop(1,"#d98a7a");
  g.strokeStyle=gold;g.lineWidth=8;g.strokeRect(30,30,W-60,H-60);g.strokeStyle="#ec2c86";g.lineWidth=1.5;g.strokeRect(54,54,W-108,H-108);
  g.strokeStyle=gold;g.lineWidth=1;g.strokeRect(66,66,W-132,H-132);
  g.textAlign="center";g.fillStyle="#ec2c86";g.font="800 24px Manrope, sans-serif";if("letterSpacing"in g)g.letterSpacing="10px";g.fillText("NEXTSTEP",W/2+5,140);if("letterSpacing"in g)g.letterSpacing="0px";
  g.fillStyle=gold;g.fillRect(W/2-60,162,120,2);
  g.fillStyle="#2a0d24";g.font="600 88px Fraunces, serif";g.fillText(t("cert_of"),W/2,278);
  g.font="500 24px Manrope, sans-serif";g.fillStyle="#85627a";g.fillText(t("cert_given"),W/2,350);
  const tg=g.createLinearGradient(W/2-300,0,W/2+300,0);tg.addColorStop(0,"#c01168");tg.addColorStop(1,"#ec2c86");
  g.fillStyle=tg;g.font="italic 600 76px Fraunces, serif";g.fillText(name,W/2,455,W-300);
  g.fillStyle=gold;g.fillRect(W/2-260,490,520,2);
  g.fillStyle="#2a0d24";g.font="700 36px Manrope, sans-serif";g.fillText(title,W/2,562,W-300);
  g.fillStyle="#85627a";g.font="500 21px Manrope, sans-serif";g.fillText(new Date().toLocaleDateString(S.lang==="uz"?"en-GB":S.lang),W/2,650);g.fillText("ID: NS-"+id.toUpperCase()+"-"+(name.length*7919%9973),W/2,688);
  const sg=g.createRadialGradient(1005,675,10,1005,690,70);sg.addColorStop(0,"#fff0c9");sg.addColorStop(.5,"#e2b36a");sg.addColorStop(1,"#a87325");
  g.fillStyle=sg;g.beginPath();for(let i=0;i<24;i++){const a=i*Math.PI/12,r=i%2?58:70;g.lineTo(1005+r*Math.cos(a),690+r*Math.sin(a))}g.closePath();g.fill();
  g.fillStyle="#fff";g.font="700 42px Manrope, sans-serif";g.fillText("★",1005,705);};
  paint();if(document.fonts&&document.fonts.load)Promise.all(["600 40px Fraunces","italic 600 40px Fraunces","700 20px Manrope"].map(f=>document.fonts.load(f))).then(paint).catch(()=>{});
}

// ---- test ----
function quizStart(ctx){run={ctx,i:0,sc:0,qs:shuffle(ctx.qs)};quizView()}
function quizView(){$("#app").classList.toggle("q",run.i>0);
  const q=run.qs[run.i];
  render(`<a class="back" href="${run.ctx.type==="t"?"#/practice":"#/contests"}">← ${t("back")}</a><h1>${esc(run.ctx.title)}</h1><div class="bar2"><i style="width:${100*run.i/run.qs.length}%"></i></div><p class="sub">${run.i+1} / ${run.qs.length}</p><div class="card"><h3 style="margin-bottom:16px">${esc(q.q)}</h3>`+q.o.map((o,k)=>`<button class="opt" data-act="pick" data-k="${k}"><b>${"ABCDEF"[k]}</b>${esc(o)}</button>`).join("")+`</div>`);
}
function quizEnd(){$("#app").classList.remove("q");
  const c=run.ctx,n=run.qs.length,pct=Math.round(100*run.sc/n),k=c.key,prev=S.scores[k];let coins=0;
  if(c.type==="t"){if((prev||0)<pass()&&pct>=pass())coins=pct>=90?+c.coins:Math.round(c.coins/2)}
  else if(prev===undefined&&pct>=pass()&&c.reward!=="cert")coins=Math.round(c.coins*pct/100);
  if(prev===undefined||pct>prev)S.scores[k]=pct;
  S.coins+=coins;save();head();
  const cert=c.type==="k"&&pct>=pass()&&c.reward!=="coin";
  render(`<div class="card center" style="max-width:520px;margin:40px auto"><h2 style="margin-top:0">${t("result")}</h2><div class="big">${pct}%</div><p>${run.sc}/${n}</p>${coins?`<p>${t("got_coins")} <b>🪙 ${coins}</b></p>`:""}<div class="gap" style="justify-content:center">${cert?`<a class="btn" href="#/cert/${c.id}">🏅 ${t("cert_get")}</a>`:""}<a class="btn ghost" href="${c.type==="t"?"#/practice":"#/contests"}">${t("back")}</a></div></div>`);
}
acts.pick=el=>{
  const q=run.qs[run.i],all=document.querySelectorAll(".opt"),k=+el.dataset.k;
  all.forEach(b=>b.disabled=true);all[q.c].classList.add("ok");
  if(k===q.c)run.sc++;else el.classList.add("no");
  run.tm=setTimeout(()=>{if(!/^#\/(quiz|contest)\//.test(location.hash))return;run.i++;run.i<run.qs.length?quizView():quizEnd()},800);
};


acts.complete=el=>{S.done[key(el.dataset.c,el.dataset.t)]=true;chat=[];save();route()};
acts.tab=el=>{tab=el.dataset.v;paintLP()};
acts["auth-mode"]=el=>{authMode=el.dataset.v==="login"?"login":"register";route()};
acts.logout=()=>{S.user=null;save();location.hash="#/login";route()};
acts.dl=()=>{const a=document.createElement("a");a.href=$("#cv").toDataURL("image/png");a.download="certificate.png";a.click()};
forms.ai=async f=>{const q=f.get("q"),k=chatK;chat.push({u:1,x:q});paintLP();const a=await askAI(q);if(k===chatK)chat.push({x:a});paintLP()};
forms.mentor=f=>{const m=S.db.mentors.find(x=>x.id===f.get("m"));const h=location.hash.split("/");S.qa.push({k:key(h[2],h[3]),q:f.get("q"),mn:m.name});save();toast(t("sent_m"));paintLP()};

// ---- marshrut ----
function head(){
  const u=S.user;$("#links").innerHTML=u?[["#/",t("nav_home")],["#/practice",t("nav_practice")],["#/contests",t("nav_contests")],["#/me",t("nav_me")]].concat(isAdmin()?[["#/admin",t("nav_admin")]]:[]).map(a=>`<a href="${a[0]}" class="${navOn(a[0])?"on":""}"${navOn(a[0])?' aria-current="page"':""}>${a[1]}</a>`).join(""):"";
  $("#coins").hidden=!u;$("#coins").textContent="🪙 "+S.coins;$("#out").hidden=!u;$("#out").textContent=t("logout");$("#lang").value=S.lang;document.documentElement.lang=S.lang;
}
function route(){$("#app").classList.remove("q");
  if(run&&run.tm)clearTimeout(run.tm);
  const[r,a,b]=location.hash.slice(2).split("/");
  if(!S.user&&r!=="login"){history.replaceState(null,"","#/login");return route()}
  if(S.user&&r==="login"){history.replaceState(null,"","#/");return route()}
  if(r==="quiz"){const c=course(a),x=c&&c.topics.find(z=>z.id===b);
    if(!x){history.replaceState(null,"","#/");return route()}
    if(!S.done[key(a,b)]){history.replaceState(null,"","#/lesson/"+a+"/"+b);return route()}
    const qs=qparse(L(x.qs));
    if(!qs.length){toast(t("no_q"));history.replaceState(null,"","#/course/"+a);return route()}
    quizStart({type:"t",key:key(a,b),title:L(x.title),coins:x.coins,qs});head();return}
  if(r==="contest"){const k=S.db.contests.find(z=>z.id===a),qs=k?qparse(L(k.qs)):[];
    if(k&&k.status==="active"&&qs.length&&S.scores["k:"+a]===undefined)quizStart({type:"k",key:"k:"+a,id:a,title:k.title,coins:k.coins,reward:k.reward,qs});
    else{history.replaceState(null,"","#/contests");return route()}
    head();return}
  const fn=r==="admin"?(isAdmin()?adminView:views.home):views[r||"home"]||views.home;
  render(fn(a,b));head();
}
function boot(){
  document.addEventListener("click",e=>{const el=e.target.closest("[data-act]");if(el&&acts[el.dataset.act])acts[el.dataset.act](el)});
  document.addEventListener("submit",e=>{const f=e.target.closest("[data-form]");if(!f)return;e.preventDefault();const fd=new FormData(f);const r=forms[f.dataset.form](fd,f);return r});
  document.addEventListener("pointermove",e=>{const c=e.target.closest&&e.target.closest(".pick");if(c){const r=c.getBoundingClientRect();c.style.setProperty("--mx",(e.clientX-r.left)+"px");c.style.setProperty("--my",(e.clientY-r.top)+"px")}});
  const tp=$(".top"),sc=()=>tp.classList.toggle("stuck",scrollY>10);addEventListener("scroll",sc,{passive:true});sc();
  $("#lang").onchange=e=>{S.lang=e.target.value;save();route()};
  window.addEventListener("hashchange",()=>{route();scrollTo(0,0)});route();
}

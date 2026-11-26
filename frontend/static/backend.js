// ============================================================
// CodeLab backend adapter (NextStep UI)
// All user progress and admin changes are persisted by Flask.
// ============================================================
const API_BASE = "";
let API_TOKEN = localStorage.getItem("nextstep_token") || "";
let API_READY = false;
async function api(path, method="GET", body=null){
  const headers={"Content-Type":"application/json"};
  if(API_TOKEN) headers.Authorization="Bearer "+API_TOKEN;
  const res=await fetch(API_BASE+path,{method,headers,body:body===null?undefined:JSON.stringify(body)});
  let data={}; try{data=await res.json()}catch(e){}
  if(!res.ok){ if(res.status===401){API_TOKEN="";localStorage.removeItem("nextstep_token");S.user=null;} throw new Error(data.error||("HTTP "+res.status)); }
  return data;
}
const toQs = arr => (arr||[]).map(q=>[q.q,...(q.o||[]),1].join("|")).join("\n");
async function refreshRemote(){
  if(!API_TOKEN) return;
  const [me, fields, courses, mentors, contests, rules] = await Promise.all([
    api('/api/me'),api('/api/fields'),api('/api/courses'),api('/api/mentors'),api('/api/contests'),api('/api/rules')
  ]);
  const fullCourses=await Promise.all(courses.map(c=>api('/api/courses/'+c.id)));
  const fieldMap=new Map(fields.map(f=>[String(f.id),String(f.id)]));
  S.db.fields=fields.map(f=>({...f,id:String(f.id)}));
  S.db.courses=fullCourses.map(c=>({id:String(c.id),field:String(c.field),title:c.title,
    sub:"",lvl:"",topics:(c.topics||[]).map(t=>({id:String(t.id),title:t.title,video:t.video||"",coins:t.coins||0,qs:toQs(t.questions||[])}))}));
  S.db.mentors=mentors.map(m=>({...m,id:String(m.id)}));
  const fullContests=await Promise.all(contests.map(k=>api('/api/contests/'+k.id)));
  S.db.contests=fullContests.map(k=>({...k,id:String(k.id),qs:toQs(k.questions||[])}));
  S.db.rules={pass:rules.pass||60};
  S.user=me.user; S.coins=me.user.coins||0;
  S.done={}; S.scores={};
  for(const c of S.db.courses) for(const tpc of c.topics){
    const p=me.progress[String(tpc.id)]; if(p){if(p.done)S.done[key(c.id,tpc.id)]=true;if(p.score!==null&&p.score!==undefined)S.scores[key(c.id,tpc.id)]=p.score;}
  }
  S.certs=(me.certificates||[]).map(x=>String(x.id));
  for(const [contestId,score] of Object.entries(me.contest_scores||{})) S.scores['k:'+contestId]=score;
  S.qa=[]; S.v=5; API_READY=true; save();
}
// The original route renderer remains intact; it now hydrates from the DB first.
const localRoute = route;
route = async function(){
  if(!API_TOKEN){ S.user=null; S.coins=0; S.done={}; S.scores={}; }
  if(API_TOKEN){
    try{
      await refreshRemote();
      const parts=location.hash.slice(2).split('/');
      if(parts[0]==='cert' && parts[1] && !S.db.contests.some(k=>k.id===parts[1])){
        const cid=Number(parts[1]);
        if(cid && !S.certs.includes(String(cid))){
          await api('/api/certificates/course/'+cid,'POST',{});
          await refreshRemote();
        }
      }
    }catch(e){toast(e.message);}
  }
  localRoute();
};
// Never allow local-only demo identities to grant admin access.
forms['admin-login']=async f=>{
  try{
    const data=await api('/api/auth/admin','POST',{login:String(f.get('login')||''),password:String(f.get('password')||'')});
    API_TOKEN=data.token;localStorage.setItem('nextstep_token',API_TOKEN);
    await refreshRemote();location.hash='#/';route();
  }catch(e){toast(e.message||'Admin login amalga oshmadi');}
};
acts.logout=()=>{API_TOKEN='';API_READY=false;localStorage.removeItem('nextstep_token');S.user=null;S.coins=0;location.hash='#/login';route();};
// Telegram account linking: user must be authenticated on the NextStep website.
forms['telegram-link']=async f=>{
  const telegram_id=String(f.get('telegram_id')||'').trim();
  if(!/^[0-9]{5,20}$/.test(telegram_id)){toast('Telegram ID noto‘g‘ri');return;}
  try{await api('/api/me/telegram','POST',{telegram_id:Number(telegram_id)});toast('Telegram hisobi muvaffaqiyatli bog‘landi');}
  catch(e){toast(e.message||'Telegram hisobini bog‘lab bo‘lmadi');}
};
// Backend-backed AI and mentor questions.
async function askAI(q){try{return (await api('/api/ai/ask','POST',{q,lang:S.lang})).answer;}catch(e){return e.message;}}
forms.ai=async f=>{const q=String(f.get('q')||'').trim();if(!q)return;chat.push({u:1,x:q});paintLP();const a=await askAI(q);chat.push({x:a});paintLP();};
forms.mentor=async f=>{
  try{const h=location.hash.split('/'),topicId=Number(h[3]),mentorId=Number(f.get('m'));
    await api('/api/mentor/ask','POST',{q:f.get('q'),topic_id:topicId,mentor_id:mentorId});
    toast(t('sent_m'));paintLP();
  }catch(e){toast(e.message);}
};
acts.complete=async el=>{try{await api('/api/topics/'+Number(el.dataset.t)+'/complete','POST',{});await refreshRemote();route();}catch(e){toast(e.message);}};
// Server-side quiz scoring; the browser never receives correct answer indices.
function quizStart(ctx){
  const qs=ctx.qs.map((q,i)=>({...q,_original:i}));
  run={ctx,i:0,sc:0,qs:shuffle(qs),answers:new Array(qs.length).fill(0)};quizView();
}
async function quizEnd(){
  $('#app').classList.remove('q'); const c=run.ctx;
  try{
    let result;
    if(c.type==='t') result=await api('/api/topics/'+Number(c.key.split(':')[1])+'/quiz','POST',{answers:run.answers});
    else result=await api('/api/contests/'+Number(c.id)+'/submit','POST',{answers:run.answers});
    await refreshRemote(); head();
    const cert=c.type==='k'&&result.cert;
    render(`<div class="card center" style="max-width:520px;margin:40px auto"><h2 style="margin-top:0">${t('result')}</h2><div class="big">${result.pct}%</div><p>${result.correct}/${result.total}</p>${result.coins?`<p>${t('got_coins')} <b>🪙 ${result.coins}</b></p>`:''}<div class="gap" style="justify-content:center">${cert?`<a class="btn" href="#/cert/${c.id}">🏅 ${t('cert_get')}</a>`:''}<a class="btn ghost" href="${c.type==='t'?'#/practice':'#/contests'}">${t('back')}</a></div></div>`);
  }catch(e){toast(e.message);location.hash=c.type==='t'?'#/practice':'#/contests';route();}
}
acts.pick=el=>{
  const q=run.qs[run.i],k=Number(el.dataset.k),all=document.querySelectorAll('.opt');
  all.forEach(b=>b.disabled=true); run.answers[q._original]=k;
  run.i++;
  setTimeout(()=>{if(run.i<run.qs.length)quizView();else quizEnd();},350);
};
// Admin panel: every action calls a protected /api/admin endpoint.
forms.afield=async f=>{try{await api('/api/admin/fields','POST',{name:f.get('n')});await refreshRemote();toast(t('saved'));route();}catch(e){toast(e.message);}};
forms.acourse=async f=>{try{await api('/api/admin/courses','POST',{field:Number(f.get('f')),title:f.get('n')});await refreshRemote();toast(t('saved'));route();}catch(e){toast(e.message);}};
function parseAdminQuestions(raw){return qparse(raw).map(q=>({q:q.q,o:q.o,c:q.c}));}
forms.atopic=async f=>{try{const questions=parseAdminQuestions(f.get('q'));if(!questions.length)throw new Error(t('qs_err'));await api('/api/admin/topics','POST',{course:Number(f.get('c')),title:f.get('n'),video:f.get('v'),coins:Number(f.get('k'))||0,questions});await refreshRemote();toast(t('saved'));route();}catch(e){toast(e.message);}};
forms.amentor=async f=>{try{await api('/api/admin/mentors','POST',{name:f.get('n'),spec:f.get('s')});await refreshRemote();toast(t('saved'));route();}catch(e){toast(e.message);}};
forms.acontest=async f=>{try{const questions=parseAdminQuestions(f.get('q'));if(!questions.length)throw new Error(t('qs_err'));await api('/api/admin/contests','POST',{title:f.get('n'),reward:f.get('r'),coins:Number(f.get('k'))||0,questions});await refreshRemote();toast(t('saved'));route();}catch(e){toast(e.message);}};
forms.arules=async f=>{try{await api('/api/admin/rules','PATCH',{pass:Number(f.get('p'))||60});await refreshRemote();toast(t('saved'));route();}catch(e){toast(e.message);}};
acts.delm=async el=>{try{await api('/api/admin/mentors/'+Number(el.dataset.id),'DELETE');await refreshRemote();route();}catch(e){toast(e.message);}};
acts.startk=async el=>{try{await api('/api/admin/contests/'+Number(el.dataset.id),'PATCH',{status:'active'});await refreshRemote();route();}catch(e){toast(e.message);}};
acts.endk=async el=>{try{await api('/api/admin/contests/'+Number(el.dataset.id),'PATCH',{status:'ended'});await refreshRemote();route();}catch(e){toast(e.message);}};
// Botsiz email/parol autentifikatsiyasi.
function acceptAuth(data){API_TOKEN=data.token;localStorage.setItem('nextstep_token',API_TOKEN);return refreshRemote();}
forms['auth-register']=async f=>{
  const password=String(f.get('password')||''),confirm=String(f.get('confirm')||'');
  if(password!==confirm){toast('Parollar mos kelmadi');return;}
  try{const data=await api('/api/auth/register','POST',{name:f.get('name'),email:f.get('email'),password});await acceptAuth(data);location.hash='#/';route();}
  catch(e){toast(e.message||'Ro‘yxatdan o‘tib bo‘lmadi');}
};
forms['auth-login']=async f=>{
  try{const data=await api('/api/auth/login','POST',{email:f.get('email'),password:f.get('password')});await acceptAuth(data);location.hash='#/';route();}
  catch(e){toast(e.message||'Kirish amalga oshmadi');}
};
const originalBoot=boot;
boot=function(){originalBoot();if(API_TOKEN){refreshRemote().then(()=>route()).catch(()=>{API_TOKEN='';localStorage.removeItem('nextstep_token');route();});}};
boot();

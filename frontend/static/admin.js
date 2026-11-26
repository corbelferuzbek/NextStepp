let aTab="content";
const opt=(arr,f)=>arr.map(f).join("");
function adminView(){
  const D=S.db,tb=(k,l)=>`<button class="${aTab===k?"on":""}" data-act="atab" data-v="${k}">${t(l)}</button>`;
  let h=`<h1>${t("admin_t")}</h1><div class="tabs">${tb("content","a_content")}${tb("mentors","a_mentors")}${tb("contests","a_contests")}${tb("rules","a_rules")}</div>`;
  if(aTab==="content")h+=`<div class="two"><form class="card f" data-form="afield"><h3>${t("add_field")}</h3><label>${t("title")}<input name="n" required></label><button class="btn">${t("add")}</button></form>
  <form class="card f" data-form="acourse"><h3>${t("add_course")}</h3><label>${t("field")}<select name="f" style="width:100%">${opt(D.fields,f=>`<option value="${f.id}">${esc(L(f.name))}</option>`)}</select></label><label>${t("title")}<input name="n" required></label><button class="btn">${t("add")}</button></form></div>
  <form class="card f" data-form="atopic" style="margin-top:16px"><h3>${t("add_topic")}</h3><label>${t("course")}<select name="c" style="width:100%">${opt(D.courses,c=>`<option value="${c.id}">${esc(L(c.title))}</option>`)}</select></label><label>${t("title")}<input name="n" required></label><label>${t("video_url")}<input name="v" placeholder="https://youtu.be/…"></label><label>${t("coin_amt")}<input name="k" type="number" min="0" value="10"></label><label>${t("qs_hint")}<textarea name="q" rows="4" required></textarea></label><button class="btn">${t("add")}</button></form>`;
  if(aTab==="mentors")h+=`<form class="card f" data-form="amentor"><h3>${t("add_mentor")}</h3><label>${t("name")}<input name="n" required></label><label>${t("spec")}<input name="s" required></label><button class="btn">${t("add")}</button></form><h2>${t("a_mentors")}</h2>`+opt(D.mentors,m=>`<div class="row"><span class="nm">${esc(m.name)}<small>${esc(m.spec)}</small></span><button class="btn ghost sm" data-act="delm" data-id="${m.id}">${t("del")}</button></div>`);
  if(aTab==="contests")h+=`<form class="card f" data-form="acontest"><h3>${t("add_contest")}</h3><label>${t("title")}<input name="n" required></label><label>${t("reward")}<select name="r" style="width:100%"><option value="coin">${t("r_coin")}</option><option value="cert">${t("r_cert")}</option><option value="both">${t("r_both")}</option></select></label><label>${t("coin_amt")}<input name="k" type="number" min="0" value="50"></label><label>${t("qs_hint")}<textarea name="q" rows="4" required></textarea></label><button class="btn">${t("add")}</button></form><h2>${t("a_contests")}</h2>`+
    opt(D.contests,k=>`<div class="row"><span class="nm">${esc(k.title)}<small>${t("r_"+k.reward)}${k.reward!=="cert"?" · "+k.coins:""}</small></span><span class="tag ${k.status==="active"?"live":""}">${t("st_"+k.status)}</span>${k.status==="upcoming"?`<button class="btn sm" data-act="startk" data-id="${k.id}">${t("start_c")}</button>`:""}${k.status==="active"?`<button class="btn ghost sm" data-act="endk" data-id="${k.id}">${t("end_c")}</button>`:""}</div>`);
  if(aTab==="rules")h+=`<form class="card f" data-form="arules"><h3>${t("a_rules")}</h3><label>${t("pass_pct")}<input name="p" type="number" min="1" max="100" value="${pass()}"></label><p class="sub">${t("tip_coin")}</p><button class="btn">${t("save")}</button></form>`;
  return h;
}
const done=m=>{save();toast(m||t("saved"));route()};
acts.atab=el=>{aTab=el.dataset.v;route()};
acts.delm=el=>{S.db.mentors=S.db.mentors.filter(m=>m.id!==el.dataset.id);done()};
acts.startk=el=>{S.db.contests.find(k=>k.id===el.dataset.id).status="active";done(t("notified")+" ("+CONFIG.MEMBERS+")")}; 
acts.endk=el=>{S.db.contests.find(k=>k.id===el.dataset.id).status="ended";done()};
forms.afield=f=>{S.db.fields.push({id:"f"+Date.now(),icon:"📘",name:f.get("n")});done()};
forms.acourse=f=>{if(!f.get("f"))return;S.db.courses.push({id:"c"+Date.now(),field:f.get("f"),title:f.get("n"),topics:[]});done()};
forms.atopic=f=>{const c=course(f.get("c"));if(!c)return toast(t("none_c"));if(!qparse(f.get("q")).length)return toast(t("qs_err"));c.topics.push({id:"t"+Date.now(),title:f.get("n"),video:f.get("v"),coins:+f.get("k")||0,qs:f.get("q")});done()};
forms.amentor=f=>{S.db.mentors.push({id:"m"+Date.now(),name:f.get("n"),spec:f.get("s")});done()};
forms.acontest=f=>{if(!qparse(f.get("q")).length)return toast(t("qs_err"));S.db.contests.push({id:"k"+Date.now(),title:f.get("n"),status:"upcoming",reward:f.get("r"),coins:+f.get("k")||0,qs:f.get("q")});done()};
forms.arules=f=>{S.db.rules.pass=+f.get("p")||60;done()};

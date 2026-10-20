"""THROWAWAY: make a double-clickable, offline review of the mock discovery trial."""

import json
from pathlib import Path

from trial import SCHEMAS, groups_for

HERE = Path(__file__).parent
transcripts = json.loads((HERE / "transcripts.json").read_text(encoding="utf-8"))
for record in transcripts["records"]:
    record["run"] = "initial"
for filename, label in (
    ("continued_transcripts.json", "continued"),
    ("retry_2026_10_20_transcripts.json", "2026-10-20 retry"),
):
    continuation = HERE / filename
    if continuation.exists():
        continued = json.loads(continuation.read_text(encoding="utf-8"))
        transcripts["requests_used"] = continued["requests_used"]
        transcripts["records"].extend(dict(record, run=label) for record in continued["records"])
budgets = {"original": {"budget": transcripts["budget"], "requests_used": transcripts["requests_used"]}}
for filename in (
    "revised_30turns_transcripts.json",
    "revised_30turns_remaining_transcripts.json",
    "revised_30turns_final_transcripts.json",
):
    revised_path = HERE / filename
    if revised_path.exists():
        revised = json.loads(revised_path.read_text(encoding="utf-8"))
        budgets["revised"] = {key: revised[key] for key in ("budget", "requests_used")}
        transcripts["records"].extend(dict(record, run="revised 30-turn") for record in revised["records"])
uncapped_path = HERE / "no_reply_cap_transcripts.json"
if uncapped_path.exists():
    uncapped = json.loads(uncapped_path.read_text(encoding="utf-8"))
    budgets["revised"] = {key: uncapped[key] for key in ("budget", "requests_used")}
    transcripts["records"].extend(
        dict(record, run="no reply-token cap") for record in uncapped["records"]
    )
data = {
    "groups": {variant: groups_for(variant) for variant in ("proposal", "focused")},
    "trials": transcripts,
    "schema_basis": SCHEMAS["basis"],
    "budgets": budgets,
}
template = r"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>THROWAWAY · CST discovery trial</title>
<style>
body{font:16px/1.5 system-ui;background:#f5f7fa;color:#172331;max-width:1100px;margin:40px auto;padding:0 20px}
h1,h2{line-height:1.2}section{background:white;padding:24px;margin:24px 0;border:1px solid #dce3eb;border-radius:10px}
button,select{font:inherit;padding:8px 12px;margin:5px;border:1px solid #a4b7cd;border-radius:5px;background:white;cursor:pointer}
button:hover,button.chosen{background:#dcecff;border-color:#2467a6}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6f8;padding:16px}
.warning{border-left:5px solid #2467a6;padding-left:16px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
label{display:block}small{color:#526679}dt{font-weight:600}dd{margin:0 0 10px;overflow-wrap:anywhere}.tabs{display:flex;flex-wrap:wrap}
@media(max-width:700px){.grid{display:block}}
</style>
<h1>Can Qwen find the CST tools it needs?</h1>
<p class="warning"><strong>THROWAWAY / MOCK ONLY.</strong> This demo asks whether replacing small tool selections
between model turns is understandable and useful. The transcript section contains actual institutional
model responses to synthetic scenarios. All CST results are mocked; no project was changed and no native
execution was validated. Free play is a deterministic illustration, not a new endpoint call.</p>
<p id="budgets"></p>
<section><h2>Explore the selection rules</h2>
<label>Configuration <select id="variant"><option value="proposal">Proposal-style</option><option value="focused">Inspection-first</option></select></label>
<div class="grid"><div><h3>Desired capability groups</h3><div id="groups"></div></div>
<div><h3>Current state</h3><dl id="state"></dl><p id="notice" role="status"></p></div></div>
<h3>Free play</h3><div id="free"></div>
<h3>Guided walkthroughs</h3><div id="walktabs" class="tabs"></div><p id="walkdesc"></p><div id="steps"></div>
</section>
<section><h2>Review the actual model conversations</h2>
<p>Choose a conversation, then step through requests, responses and mock operations.
Raw schemas were not pasted into tool results. Request entries show the tools actually sent on the wire.</p>
<div id="trialtabs" class="tabs"></div><p id="trialinfo"></p>
<button id="restart">Restart conversation</button><button id="next">Show next event</button><button id="all">Show full conversation</button>
<div id="conversation"></div><h3>Latest mock operation state</h3><pre id="observed">No mock operation yet.</pre>
</section>
<small id="basis"></small>
<script>
const data=__DATA__;
// Pure illustrative state machine. No DOM, network, storage or CST access.
const startup=v=>v==='focused'?['discover_tools','cst_connection_status','cst_project_info']:['discover_tools','cst_connection_status'];
const names=(v,groups)=>[...new Set([...startup(v),...groups.flatMap(g=>data.groups[v][g].names)])].sort();
const initial=v=>({variant:v,active:[],pending:null,requestNames:startup(v),missing:false,uncertain:false,last:'Ready. No CST operations will run.'});
function reduce(old,action){
 const s=JSON.parse(JSON.stringify(old));
 if(action.type==='reset')return initial(s.variant);
 if(action.type==='select'){
  const candidate=names(s.variant,action.groups);
  if(candidate.length>18){s.last=`Rejected: ${candidate.length} functions exceeds 18. Previous selection preserved.`;return s;}
  if(s.missing&&candidate.includes('cst_create_cylinder')){s.last='Rejected: cylinder tool missing. Previous selection preserved.';return s;}
  s.pending=action.groups;s.last='Selection staged. Current response still uses its original tool set.';
 }else if(action.type==='turn'){
  if(s.pending!==null){s.active=s.pending;s.pending=null;}
  s.requestNames=names(s.variant,s.active);s.last='Next model request now carries the selected schemas.';
 }else if(action.type==='missing'){s.missing=!s.missing;s.last='Synthetic catalogue availability toggled; no server was contacted.';}
 else if(action.type==='uncertain'){s.uncertain=true;s.last='Injected uncertain mutation: effect unknown. All CST dispatch blocked.';}
 else if(action.type==='cylinder'){
  s.last=s.uncertain?'Blocked: transport outcome is uncertain. Do not retry or query CST.':
    !s.requestNames.includes('cst_create_cylinder')?'Blocked: cylinder was not visible in the originating request.':
    'Mock cylinder accepted. This illustrates exposure only; native effect is NOT verified.';
 }
 return s;
}
let state=initial('proposal');
const walks=[
 {name:'Material → geometry',desc:'Discovery must change the next request, not authorize new tools in the current response.',steps:[
  ['Select material tools',{type:'select',groups:['materials_basic']}],['Start next turn',{type:'turn'}],
  ['Replace with geometry',{type:'select',groups:['geometry_basic']}],['Try cylinder too early',{type:'cylinder'}],
  ['Start next turn',{type:'turn'}],['Try mock cylinder',{type:'cylinder'}]]},
 {name:'Too many tools',desc:'Rejection must not silently truncate the selection.',steps:[
  ['Select parameters',{type:'select',groups:['parameters']}],['Start next turn',{type:'turn'}],
  ['Request oversized union',{type:'select',groups:['session_project','project_context','parameters','materials_basic','geometry_basic']}]]},
 {name:'Missing tool',desc:'One unavailable member rejects a group atomically.',steps:[
  ['Mark cylinder unavailable',{type:'missing'}],['Request geometry',{type:'select',groups:['geometry_basic']}]]},
 {name:'Uncertain mutation',desc:'An uncertain attempt is not evidence of failure and does not permit a replay.',steps:[
  ['Select geometry',{type:'select',groups:['geometry_basic']}],['Start next turn',{type:'turn'}],
  ['Inject uncertain attempt',{type:'uncertain'}],['Try cylinder again',{type:'cylinder'}]]}
];
function button(text,fn,parent){const b=document.createElement('button');b.textContent=text;b.onclick=fn;parent.append(b);return b;}
function addField(parent,title,value){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=title;dd.textContent=value;parent.append(dt,dd);}
function render(){
 const panel=document.getElementById('state');panel.replaceChildren();
 addField(panel,'Current request groups',state.active.join(', ')||'Startup only');
 addField(panel,'Staged next groups',state.pending===null?'No update':state.pending.join(', ')||'Startup only');
 addField(panel,'Functions visible in originating request',state.requestNames.join(', '));
 addField(panel,'Visible count',state.requestNames.length+' / 18');
 addField(panel,'Cylinder available',state.missing?'No':'Yes');
 addField(panel,'CST dispatch',state.uncertain?'Blocked — uncertain outcome':'Mock only');
 document.getElementById('notice').textContent=state.last;
}
function groupInputs(){const panel=document.getElementById('groups');panel.replaceChildren();
 for(const [g,value]of Object.entries(data.groups[state.variant])){const l=document.createElement('label'),c=document.createElement('input');c.type='checkbox';c.value=g;l.append(c,document.createTextNode(' '+g+' ('+value.names.length+')'));panel.append(l);}}
document.getElementById('variant').onchange=e=>{state=initial(e.target.value);groupInputs();render();};
const free=document.getElementById('free');
button('Request selected tools',()=>{state=reduce(state,{type:'select',groups:[...document.querySelectorAll('#groups input:checked')].map(c=>c.value)});render();},free);
for(const[label,type]of [['Start next model turn','turn'],['Try mock cylinder','cylinder'],['Toggle missing cylinder','missing'],['Inject uncertain outcome','uncertain'],['Reset','reset']])button(label,()=>{state=reduce(state,{type});render();},free);
for(const walk of walks)button(walk.name,()=>{
 state=initial(state.variant);render();document.getElementById('walkdesc').textContent=walk.desc;
 const steps=document.getElementById('steps');steps.replaceChildren();
 for(const[label,action]of walk.steps)button(label,()=>{state=reduce(state,action);render();},steps);
},document.getElementById('walktabs'));
let selected=0,position=0;
function review(){
 const t=data.trials.records[selected],panel=document.getElementById('conversation');panel.replaceChildren();
 document.getElementById('trialinfo').textContent=`${t.run} / ${t.variant} / ${t.scenario}: ${t.status}; ${t.events.filter(e=>e.kind==='request').length} actual HTTP requests. All CST operations mocked.`;
 const p=document.createElement('pre');p.textContent='USER\n'+t.prompt;panel.append(p);
 if(t.instructions){const details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='System instructions and tool-group table';pre.textContent=t.instructions;details.append(summary,pre);panel.append(details);}
 let latest='No mock operation yet.';
 for(const e of t.events.slice(0,position)){
  const title=document.createElement('h3'),pre=document.createElement('pre');
  title.textContent=e.kind==='assistant'?'MODEL RESPONSE':e.kind==='request'?'NEXT REQUEST / VISIBLE TOOLS':'MOCK TOOL / RESULT';
  pre.textContent=JSON.stringify(e,null,2);panel.append(title,pre);
  if(e.kind==='tool')latest=JSON.stringify(e.state,null,2);
 }
 document.getElementById('observed').textContent=latest;
}
data.trials.records.forEach((t,i)=>button(t.run+' · '+t.variant+' · '+t.scenario,()=>{selected=i;position=0;review();},document.getElementById('trialtabs')));
document.getElementById('restart').onclick=()=>{position=0;review();};
document.getElementById('next').onclick=()=>{position=Math.min(position+1,data.trials.records[selected].events.length);review();};
document.getElementById('all').onclick=()=>{position=data.trials.records[selected].events.length;review();};
document.getElementById('basis').textContent=data.schema_basis+' The free-play reducer illustrates timing; observed transcripts are the endpoint evidence. No future rerun is authorized by this file.';
document.getElementById('budgets').textContent=Object.entries(data.budgets).map(([name,b])=>name+': '+b.requests_used+' / '+b.budget+' HTTP requests').join(' · ');
groupInputs();render();review();
</script></html>"""
(HERE / "review.html").write_text(
    template.replace("__DATA__", json.dumps(data).replace("<", "\\u003c")), encoding="utf-8"
)
print("Created self-contained review.html (offline; no endpoint or CST access).")

/* Component logic QA in a minimal DOM fixture. No browser or real visibility proof. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const crypto=require('node:crypto');
const code=fs.readFileSync(__dirname+'/hongik_panel.js','utf8');
function fixture(){
 const nodes=new Map(),listeners={},sent=[],audio=[];let pending=null,failNext=false;
 class AudioStub{constructor(url){this.url=url;this.paused=false;audio.push(this)}play(){this.onplaying?.();return Promise.resolve()}pause(){this.paused=true}removeAttribute(){}load(){}}
 class Element{
  constructor(tag){this.tagName=tag;this.children=[];this.hidden=false;this.disabled=false;this.attributes={};this.dataset={};this.textContent='';this.classes=new Set();
   this.classList={add:n=>this.classes.add(n),remove:n=>this.classes.delete(n),toggle:(n,on)=>on?this.classes.add(n):this.classes.delete(n),contains:n=>this.classes.has(n)};}
  set id(v){this._id=v;nodes.set(v,this)}get id(){return this._id}
  set innerHTML(html){for(const m of html.matchAll(/<([a-z][a-z0-9]*)\b([^>]*)>/g)){const id=m[2].match(/\bid="([^"]+)"/);if(!id)continue;const e=new Element(m[1]);e.id=id[1];e.hidden=/\bhidden\b/.test(m[2]);this.children.push(e)}}
  appendChild(e){this.children.push(e)}append(...e){this.children.push(...e)}replaceChildren(...e){this.children=[...e]}
  setAttribute(k,v){this.attributes[k]=v}focus(){document.activeElement=this}
 }
 const document={body:new Element('body'),visibilityState:'visible',activeElement:null,
  createElement:t=>new Element(t),getElementById:id=>nodes.get(id),addEventListener:(n,f)=>listeners[n]=f};
 const context={document,window:{},crypto,Audio:AudioStub,localStorage:{getItem:()=>null},performance:{now:()=>123},setTimeout,clearTimeout,AbortController,encodeURIComponent,
  fetch:async(url,options={})=>{
   if(url==='/api/command'){
    const body=JSON.parse(options.body);sent.push(body);
    if(pending){const wait=pending;pending=null;await wait}
    if(failNext){failNext=false;return{ok:false,json:async()=>({error:'연결을 다시 확인해 주세요.'})}}
    return{ok:true,json:async()=>({session_id:body.session_id,command_id:'command-'+sent.length})};
   }
   assert.match(url,/^\/api\/reply\?/);
   return{ok:true,json:async()=>({accepted:true,message:'요청한 간격을 확보하고 있어요.'})};
  }};
 vm.runInNewContext(code,context,{filename:'hongik_panel.js'});
 const options=[{action:'study_inspect',label:'현재 안전조치 확인',detail:'조회'},
  {action:'study_distance',label:'더 감속하고 거리 확보',detail:'감속'},
  {action:'study_stop_request',label:'안전한 곳에 정차 요청',detail:'요청'}];
 function update({active=true,session='s1',feedback='',connected=true,outcome={phase:'idle'},choices=options,staged=false}={}){
  context.window.CockpitUpdate({connected,session:{session_id:session,stage:'running',navigation:{id:session+'-weaving',
   research_event:{active,options:choices,staged_options:staged,title:active?'전방에 안개가 있습니다':'경로를 따라 주행합니다',description:'상황 설명',live_detail:'실제 속도와 앞차 간격 안내',feedback,outcome,pending:outcome.phase!=='idle',
    narration:{cached:true,url:'/api/narration/audio/fog.wav',speaker:'Sohee'}}}}});
 }
 return{nodes,sent,audio,document,listeners,update,$:id=>nodes.get(id),
  blockNext(){let resolve;pending=new Promise(r=>resolve=r);return resolve},failNext:()=>failNext=true};
}
const settle=()=>new Promise(r=>setImmediate(r));
(async()=>{
 let f=fixture();f.update({active:false});assert(f.$('research-dialog').hidden);assert(!f.$('research-launch').classList.contains('has-update'));
 const staged=fixture();staged.update({staged:true});await staged.$('research-launch').onclick();
 assert(staged.$('research-options').hidden);assert(!staged.$('research-options-open').hidden);
 assert.equal(staged.sent.at(-1).client_event.options_visible,false);
 staged.audio[0].onended();await settle();await settle();
 assert(!staged.$('research-options').hidden);assert(staged.sent.some(x=>x.action==='study_options'));
 f.update();await settle();assert(f.$('research-dialog').hidden);assert(f.$('research-launch').classList.contains('has-update'));
 assert.equal(f.sent.filter(x=>x.action==='study_presented').length,1);f.update();await settle();assert.equal(f.sent.filter(x=>x.action==='study_presented').length,1);
 await f.$('research-launch').onclick();assert(!f.$('research-dialog').hidden);assert(!f.$('research-options').hidden);
 assert.equal(f.audio.length,1);assert.equal(f.audio[0].url,'/api/narration/audio/fog.wav');assert(!f.audio[0].paused);
 assert.equal(f.$('research-options').children.length,3);assert(!f.$('research-launch').classList.contains('has-update'));
 assert.equal(f.sent.at(-1).action,'study_open');assert.equal(f.sent.at(-1).client_event.options_visible,true);
 assert(!f.sent.some(x=>x.action==='study_distance'));
 const first=f.$('research-options').children[0];f.update();assert.equal(f.$('research-options').children[0],first);
 await f.$('research-options').children[1].onclick();assert(f.audio[0].paused);assert(!f.$('research-confirmation').hidden);assert(!f.sent.some(x=>x.action==='study_distance'));
 await f.$('research-back').onclick();assert(f.$('research-confirmation').hidden);assert(!f.$('research-options').hidden);
 await f.$('research-options').children[1].onclick();
 await Promise.all([f.$('research-execute').onclick(),f.$('research-execute').onclick()]);
 assert.equal(f.sent.filter(x=>x.action==='study_distance').length,1);assert(f.$('research-options').hidden);assert.match(f.$('research-feedback').textContent,/간격/);
 f.update({outcome:{phase:'observing',summary:'간격 확보 결과'}});assert(f.$('research-options').hidden);assert.match(f.$('research-feedback').textContent,/결과/);
 f.$('research-close').onclick();await settle();assert(f.$('research-dialog').hidden);assert(!f.sent.some(x=>x.action==='study_stop_request'));
 f.update({active:false,outcome:{phase:'complete',message:'체험을 종료합니다',summary:'간격 유지 결과'}});assert(!f.$('research-ending').hidden);assert.match(f.$('research-ending-summary').textContent,/간격 유지/);
 f.update({active:false,session:'s2'});await f.$('research-launch').onclick();assert(f.$('research-options').hidden);
 f.update({session:'s2'});await settle();assert(!f.$('research-options').hidden);assert(f.sent.some(x=>x.action==='study_options'));
 f.listeners.keydown({key:'Escape',preventDefault(){}});await settle();assert(f.$('research-dialog').hidden);
 f=fixture();f.document.visibilityState='hidden';f.update();await settle();assert.equal(f.sent.length,0);
 f.document.visibilityState='visible';f.listeners.visibilitychange();await settle();assert.equal(f.sent[0].action,'study_presented');
 const release=f.blockNext(),opening=f.$('research-launch').onclick();await settle();f.update({session:'s-new'});release();await opening;
 assert(f.$('research-dialog').hidden);assert(f.$('research-confirmation').hidden);assert(f.audio[0].paused);assert(!f.sent.some(x=>x.action==='study_distance'));
 f=fixture();f.update();await settle();f.failNext();await f.$('research-launch').onclick();await settle();
 // A failed open never enables or executes choices and does not spam retries.
 assert(!f.sent.some(x=>x.action==='study_options'));assert(f.$('research-options').children.every(x=>x.disabled));
 assert(!f.sent.some(x=>['study_distance','study_stop_request'].includes(x.action)));
 f.update({active:false});assert(!f.$('research-launch').classList.contains('has-update'));assert(f.$('research-options').hidden);
 f=fixture();const overtake={action:'study_overtake',label:'추월 시도',detail:'왼쪽 차로로 이동'};
 f.update({choices:[overtake]});await f.$('research-launch').onclick();
 await f.$('research-options').children[0].onclick();assert(!f.sent.some(x=>x.action==='study_overtake'));
 await f.$('research-back').onclick();assert(!f.sent.some(x=>x.action==='study_overtake'));
 await f.$('research-options').children[0].onclick();await f.$('research-execute').onclick();
 assert.equal(f.sent.filter(x=>x.action==='study_overtake').length,1);
 f=fixture();f.update({choices:[{...overtake,disabled:true,disabled_reason:'준비 중'}]});await f.$('research-launch').onclick();
 assert(f.$('research-options').children[0].disabled);await f.$('research-options').children[0].onclick();
 assert(!f.sent.some(x=>x.action==='study_choice'));
 f=fixture();f.update({choices:[overtake]});await f.$('research-launch').onclick();await f.$('research-options').children[0].onclick();
 f.update({choices:[{...overtake,disabled:true,disabled_reason:'구간 끝'}]});assert(f.$('research-execute').disabled);
 await f.$('research-execute').onclick();assert(!f.sent.some(x=>x.action==='study_overtake'));
 f.update({outcome:{phase:'complete',message:'추월 시도 중 충돌이 발생해 주행 체험이 종료되었습니다.',summary:'사고 결과 확인'}});
 assert.match(f.$('research-ending-message').textContent,/충돌/);
 console.log('PASS: invitation, one-click choices, cached Sohee click playback/cancel, explicit execution, cancel/X, dedup, inactive/onset, visibility, stale session and failure paths. Minimal-DOM component QA; not real browser QA.');
})().catch(e=>{console.error(e);process.exitCode=1});

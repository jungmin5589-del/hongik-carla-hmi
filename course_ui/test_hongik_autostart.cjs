const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const helper=fs.readFileSync(__dirname+'/hongik-wake.js','utf8'),source=fs.readFileSync(__dirname+'/hongik-assistant.js','utf8');
function browser(mode='running',visible=true){
 const nodes=new Map(),events={},calls=[],contexts=[];let requested=0,stopped=0;
 const node=id=>{if(!nodes.has(id))nodes.set(id,{hidden:id==='hongik-dialog'||id==='hongik-proposal',dataset:{},attrs:{},handlers:{},setAttribute(k,v){this.attrs[k]=v},addEventListener(k,v){this.handlers[k]=v},focus(){}});return nodes.get(id)};
 const document={visibilityState:visible?'visible':'hidden',getElementById:node,body:{classList:{add(){}}},addEventListener:(name,callback)=>events[name]=callback};
 class Context{
  constructor(){this.state=mode==='suspended'?'suspended':'running';this.sampleRate=48000;this.resumes=0;this.audioWorklet={addModule:async()=>{}};contexts.push(this)}
  resume(){this.resumes++;if(mode==='suspended'&&this.resumes===1)return new Promise(()=>{});this.state='running';this.onstatechange?.();return Promise.resolve()}
  close(){this.state='closed';return Promise.resolve()}
  createMediaStreamSource(){return {connect(){}}}createGain(){return {gain:{value:0},connect(){}}}
 }
 class Worklet{constructor(){this.port={}}connect(){return {connect(){}}}}
 const window={addEventListener(){},passengerNarration:{arm(){},enqueue(){throw Error('auto-start must not speak or ask')},cancel(){}}};
 const context=vm.createContext({window,document,navigator:{mediaDevices:{getUserMedia:async()=>{requested++;if(mode==='denied')throw Object.assign(Error('denied'),{name:'NotAllowedError'});return {getTracks:()=>[{stop(){stopped++}}]}}}},AudioContext:Context,AudioWorkletNode:Worklet,Date,setTimeout,fetch:async(path)=>{calls.push(path);return {ok:true,json:async()=>path==='/api/voice/prepare'?{job_id:'prepare',status:'queued'}:{status:'complete'}}}});
 vm.runInContext(helper,context);vm.runInContext(source,context);
 return {nodes,node,document,events,calls,contexts,requested:()=>requested,stopped:()=>stopped};
}
const flush=async()=>{for(let i=0;i<50;i++)await Promise.resolve()};
(async()=>{
 const a=browser();await flush();assert.equal(a.requested(),1);assert.match(a.node('hongik-voice-badge').textContent,/호출 대기/);assert.equal(a.node('hongik-dialog').hidden,true);assert.equal(a.calls.some(path=>path.startsWith('/api/assistant')),false);
 await a.node('hongik-call-toggle').handlers.click();assert.equal(a.stopped(),1);a.document.visibilityState='hidden';a.events.visibilitychange();a.document.visibilityState='visible';a.events.visibilitychange();await flush();assert.equal(a.requested(),1,'manual off is respected');
 const b=browser('suspended');await flush();assert.match(b.node('hongik-voice-badge').textContent,/한 번/);assert.equal(b.node('hongik-mic').disabled,false,'pending resume must not block setup');b.events.pointerdown();await flush();assert.match(b.node('hongik-voice-badge').textContent,/호출 대기/);
 const c=browser('denied');await flush();assert.match(c.node('hongik-voice-badge').textContent,/허용/);assert.equal(c.node('hongik-call-toggle').attrs['aria-pressed'],'false');assert.equal(c.requested(),1);
 const d=browser('running',false);await flush();assert.equal(d.requested(),0);d.document.visibilityState='visible';d.events.visibilitychange();await flush();assert.equal(d.requested(),1);
 console.log('PASS: visible page automatically starts microphone, no AI question or speech, hidden page defers, manual off persists, permission denial is visible, suspended AudioContext resumes after any click.');
})().catch(error=>{console.error(error);process.exitCode=1});

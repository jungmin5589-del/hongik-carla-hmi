const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync(__dirname+'/navigation-voice.js','utf8');
const channels=[],audible=new Set();let maximum=0;
class Channel{
 constructor(){channels.push(this)}
 postMessage(data){for(const channel of channels)if(channel!==this)queueMicrotask(()=>channel.onmessage?.({data}))}
 close(){this.onmessage=null}
}
function tab(id){
 const listeners={},history=[];let player=null;
 const document={visibilityState:'visible',addEventListener:(name,callback)=>listeners[name]=callback};
 class Backend{
  cancel(){if(player)audible.delete(player);player=null}
  speak(text,callbacks){player={id,text,callbacks};history.push(player);audible.add(player);maximum=Math.max(maximum,audible.size);callbacks.onstart()}
 }
 const context=vm.createContext({navigator,document,BroadcastChannel:Channel,AbortController,setTimeout,clearTimeout,QwenSpeechTransport:Backend});
 vm.runInContext(code,context);const voice=new context.NavigationVoice({audio:{volume:.8}});voice.setProvider('qwen');voice.arm();
 return {context,voice,document,history,hide(){document.visibilityState='hidden';listeners.visibilitychange()},end(){const current=player;audible.delete(current);player=null;current.callbacks.onend()}};
}
const wait=async(predicate)=>{for(let i=0;i<100;i++){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,5))}throw Error('Timed out waiting for voice turn')};
const message=(kind,text)=>({kind,text,priority:kind==='assistant'||kind==='arrival'?3:0});
(async()=>{
 assert.equal(typeof navigator.locks.request,'function','use real Node Web Locks');
 const a=tab('a'),b=tab('b');
 a.voice.enqueue(message('distance','500미터'));await wait(()=>a.history.length===1);
 b.voice.enqueue(message('distance','중복 안내'));await wait(()=>b.voice.current===null);
 assert.equal(b.history.length,0,'another tab skips automatic audio while the slot is held');
 const old=a.history[0];b.voice.setAssistantActive(true);b.voice.enqueue(message('assistant','앞 상황 답변'));
 await wait(()=>b.history.length===1);assert.equal(a.voice.current,null,'AI interrupts navigation in the other tab');assert.equal(audible.size,1);
 old.callbacks.onend();assert.equal(b.context.passengerTtsSpeaking,true,'late completion cannot affect another tab');
 b.voice.enqueue(message('distance','300미터'));assert.equal(b.voice.queue.length,0,'conversation drops intervening distance announcements');
 b.voice.enqueue(message('arrival','서울역에 도착했습니다.'));assert.equal(b.voice.pendingArrival.kind,'arrival');
 b.end();assert.equal(b.voice.current,null);b.voice.setAssistantActive(false);
 await wait(()=>b.history.length===2);assert.equal(b.history[1].text,'서울역에 도착했습니다.','arrival speaks after closing dialogue');
 b.hide();assert.equal(b.voice.current,null);assert.equal(audible.size,0);b.voice.enqueue(message('distance','숨겨진 탭'));assert.equal(b.history.length,2);
 a.voice.setAssistantActive(true);a.voice.enqueue(message('assistant','다시 질문'));await wait(()=>a.history.length===2);
 a.voice.enqueue(message('assistant','최신 답변'));await wait(()=>a.history.length===3);assert.equal(audible.size,1);
 a.voice.cancel();assert.equal(audible.size,0);assert.equal(maximum,1,'two tabs never play speech simultaneously');
 for(const channel of channels)channel.close();
 console.log('PASS: real Web Locks across two contexts, AI interrupts other-tab navigation, distance suppression, deferred arrival, hidden tab cancellation, newest answer and single audible voice.');
})().catch(error=>{console.error(error);process.exitCode=1});

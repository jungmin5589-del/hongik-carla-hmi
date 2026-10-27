const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const players=[],paths=[];let polls=0,resolvePending;
class Player{constructor(url){this.url=url;players.push(this)}play(){return Promise.resolve()}pause(){this.paused=true}removeAttribute(){}load(){}}
const context=vm.createContext({Audio:Player,AbortController,DOMException,setTimeout,clearTimeout,fetch:async(path)=>{
 paths.push(path);return {ok:true,json:async()=>path==='/api/tts/synthesize'?{status:'queued',job_id:'original-id'}:++polls===1?{status:'processing'}:{status:'complete',url:'/api/tts/audio/test.wav'}};
}});
vm.runInContext(fs.readFileSync(__dirname+'/qwen-speech.js','utf8'),context);
(async()=>{
 const backend=new context.QwenSpeechTransport();let starts=0,ends=0;
 await backend.speak('네, 말씀하세요.',{onstart:()=>starts++,onend:()=>ends++,onerror:e=>{throw e}});
 assert.equal(players.length,1);assert.equal(starts,0,'ready file is not playing yet');players[0].onplaying();assert.equal(starts,1);
 assert.deepEqual(paths.filter(p=>p.startsWith('/api/tts/job')),['/api/tts/job?id=original-id','/api/tts/job?id=original-id']);
 backend.cancel();players[0].onended();assert.equal(ends,0,'cancelled audio does not complete a new utterance');assert.equal(players[0].paused,true);
 context.fetch=()=>new Promise(resolve=>resolvePending=resolve);
 const pending=backend.speak('새 안내',{onstart:()=>starts++,onend:()=>ends++,onerror:e=>{throw e}});backend.cancel();
 resolvePending({ok:true,json:async()=>({status:'complete',url:'/late.wav'})});await pending;assert.equal(players.length,1,'late response never plays');
 vm.runInContext(fs.readFileSync(__dirname+'/navigation-voice.js','utf8'),context);
 let callbacks,cancelled=0;context.QwenSpeechTransport=class{cancel(){cancelled++}speak(text,c){callbacks=c}};
 const music={volume:.8},voice=new context.NavigationVoice({audio:music});voice.setProvider('qwen');voice.arm();voice.enqueue({kind:'assistant',text:'왼쪽으로 추월할까요?',priority:3});
 assert.equal(music.volume,.8);callbacks.onstart();assert.equal(music.volume,.2);assert.equal(context.passengerTtsSpeaking,true);
 const stale=callbacks;voice.cancel();assert.equal(music.volume,.8);assert.equal(context.passengerTtsSpeaking,false);stale.onend();assert.equal(voice.current,null);assert.ok(cancelled);
 voice.enqueue({kind:'assistant',text:'두 번째',priority:3});voice.enqueue({kind:'assistant',text:'최신 답변',priority:3});assert.equal(voice.current.message.text,'최신 답변');voice.cancel();
 console.log('PASS: Sohee job polling, actual playback timing, late/cancelled audio suppressed, music and microphone flags restored, newest dialogue supersedes previous speech.');
})().catch(e=>{console.error(e);process.exitCode=1});

/* Integration with the actual local server; fake speakers avoid audible test output. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const live=new Set();let maxLive=0,navEnded=0,aiStarted=0;
class Player{constructor(url){this.url=url}play(){live.add(this);maxLive=Math.max(maxLive,live.size);this.onplaying?.();return Promise.resolve()}pause(){live.delete(this)}removeAttribute(){}load(){}}
function client(){const context=vm.createContext({Audio:Player,document:{},AbortController,DOMException,crypto,setTimeout,clearTimeout,fetch:(path,options)=>fetch('http://127.0.0.1:8769'+path,options)});vm.runInContext(fs.readFileSync(__dirname+'/qwen-speech.js','utf8'),context);return context}
(async()=>{
 const a=client(),b=client(),nav=new a.QwenSpeechTransport({provider:'supertonic'}),ai=new b.QwenSpeechTransport({provider:'qwen'});
 await nav.speak('목적지까지 500미터 남았습니다.',{kind:'navigation',onstart(){},onend(){navEnded++},onerror(error){throw error}});assert.equal(live.size,1);
 await ai.speak('네, 말씀하세요.',{kind:'assistant',onstart(){aiStarted++},onend(){},onerror(error){throw error}});
 assert.equal(navEnded,1,'navigation acknowledged stopping before AI started');assert.equal(aiStarted,1);assert.equal(maxLive,1,'server serializes contexts without shared browser locks');assert.equal(live.size,1);
 nav.cancel();ai.cancel();await new Promise(resolve=>setTimeout(resolve,50));assert.equal(live.size,0);
 console.log('PASS: actual server grants F3 navigation, waits for its stop acknowledgement, then grants Qwen AI across independent contexts; maximum one simulated speaker.');
})().catch(error=>{console.error(error);process.exitCode=1});

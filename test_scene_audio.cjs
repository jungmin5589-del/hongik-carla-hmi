const assert=require('node:assert/strict'),{AudioLease}=require('./scene_audio.js'),{SpeechGate}=require('./exterior_sound.js');
let value=null,now=100;const store={getItem:()=>value,setItem:(k,v)=>value=v,removeItem:()=>value=null};
const a=new AudioLease('a',()=>{},{store,now:()=>now}),b=new AudioLease('b',()=>{},{store,now:()=>now});
a.claim();assert(a.owns());assert(!b.owns());b.claim();assert(!a.owns());assert(b.owns());
a.release();assert(b.owns(),'Old tab cannot release the active tab');now+=7000;assert(a.owns(),'A crashed tab lease expires');assert(!b.owns());
const gate=new SpeechGate(),cue={index:1,key:'call',expires_s:12};gate.offer(cue,5);assert.equal(gate.take(5,false),'call');gate.retry(cue,6);assert.equal(gate.take(6,false),'call','Rejected browser playback is retryable');
gate.retry(cue,13);assert.equal(gate.take(13,false),null,'Expired speech is never replayed');
console.log('PASS single audio owner, explicit takeover, expiry and rejected-play retry');

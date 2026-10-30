const assert=require('node:assert/strict');
const {doorWave,SpeechGate}=require('./exterior_sound.js');
for(const rate of [24000,44100,48000]){
 const a=doorWave(rate);
 assert.equal(a.length,Math.round(rate*.38));
 assert(a.every(Number.isFinite));
 assert(Math.max(...a.map(Math.abs))<1,'Door impact waveform must not clip');
 const rms=s=>Math.sqrt(s.reduce((n,x)=>n+x*x,0)/s.length);
 assert(rms(a.slice(-Math.round(rate*.025)))<.004,'No cut-off tail or sustained noise');
 assert(rms(a.slice(0,Math.round(rate*.05)))>.15,'A discernible short body-panel thud');
}
console.log('PASS finite unclipped short door impact at three audio sample rates');
const gate=new SpeechGate();
const cue=(index,key,expires_s)=>({index,key,expires_s});
gate.offer(cue(1,'call',12),5);
assert.equal(gate.take(5,true),null,'AI has audio priority');
assert.equal(gate.take(7,false),'call');
gate.offer(cue(1,'call',12),8);assert.equal(gate.take(8,false),null,'A line cannot replay on every state update');
gate.offer(cue(2,'refusal',23),13);gate.offer(cue(3,'complaint',37),24);
assert.equal(gate.take(24,false),'complaint','No backlog of old dialogue after a long AI explanation');
gate.offer(cue(4,'plate',53),38);assert.equal(gate.take(54,false),null,'Expired line cannot be played late');
gate.offer(cue(5,'door',71),54,false);gate.offer(cue(5,'door',71),55);
assert.equal(gate.take(55,false),null,'Paused/hidden utterance must not replay on return');
gate.offer(cue(6,'answer',82),72);gate.offer(cue(0,null,0),73,false);
assert.equal(gate.take(73,false),null,'Retreat clears pending speech');
gate.reset();gate.offer(cue(1,'call',12),5);assert.equal(gate.take(5,false),'call','New trial has its own sequence');
console.log('PASS one-shot speech, AI priority, expiry, pause/hidden/retreat and session reset');

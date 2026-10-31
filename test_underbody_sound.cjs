const assert=require('node:assert/strict');
const {contactWave,nextDelay,Player}=require('./underbody_sound.js');
for(const rate of [24000,44100,48000]){
 const waves=Array.from({length:8},(_,i)=>contactWave(rate,i));
 for(const a of waves){
  assert(a.every(Number.isFinite));assert(Math.max(...a.map(Math.abs))<1);
  const tail=a.slice(-Math.round(rate*.025));assert(Math.sqrt(tail.reduce((n,x)=>n+x*x,0)/tail.length)<.003);
 }
 assert.notDeepEqual(waves[0],waves[1],'Contacts should not be one identical loop');
}
assert(nextDelay(30,()=>.5)<nextDelay(12,()=>.5));
const starts=[];const node=()=>({connect(){return this},disconnect(){}});
const ctx={currentTime:0,sampleRate:24000,destination:{},
 createGain:()=>Object.assign(node(),{gain:{value:0,setTargetAtTime(){}}}),
 createBiquadFilter:()=>Object.assign(node(),{frequency:{value:0}}),createStereoPanner:()=>Object.assign(node(),{pan:{value:0}}),
 createBuffer:(c,n)=>({copyToChannel(){}}),
 createBufferSource:()=>Object.assign(node(),{playbackRate:{value:1},start(at){starts.push(at)},stop(){this.stopped=true}})};
const player=new Player(ctx);player.update(0);assert.equal(starts.length,0);
for(let i=0;i<50;i++){ctx.currentTime=i*.1;player.update(20)}
assert(starts.length>5&&starts.length<35);const differences=starts.slice(1).map((x,i)=>x-starts[i]);assert(new Set(differences.map(x=>x.toFixed(2))).size>4);
player.stop();assert.equal(player.active.size,0);assert.equal(player.next,0);
console.log('PASS underbody: finite short varied contacts, irregular speed-related timing, stop/pause cleanup');

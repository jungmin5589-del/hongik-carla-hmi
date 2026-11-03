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
(async()=>{
 const starts=[],sources=[],node=()=>({connect(){return this},disconnect(){}});
 const ctx={currentTime:0,sampleRate:24000,destination:{},
  createGain:()=>Object.assign(node(),{gain:{value:0,setTargetAtTime(v){this.value=v}}}),
  createStereoPanner:()=>Object.assign(node(),{pan:{value:0}}),
  createBufferSource:()=>{const s=Object.assign(node(),{playbackRate:{value:1},start(at){starts.push(at)},stop(){this.stopped=true}});sources.push(s);return s}};
 const p=new Player(ctx,{buffer:{duration:2.7}});await p.ready;p.update(0);assert.equal(starts.length,0);
 for(let i=0;i<500;i++){ctx.currentTime=i*.1;p.update(20)}
 assert(starts.length>=4&&starts.length<=8);assert(sources.every(s=>s.playbackRate.value===1));
 assert(starts.slice(1).every((t,i)=>t-starts[i]>=7),'No rapid repeated contact loop');
 p.update(20,true);assert.equal(p.gain.gain.value,.25);p.stop();assert.equal(p.active.size,0);p.dispose();p.dispose();
 const q=new Player(ctx,{buffer:{duration:2.7}});q.dispose();await q.ready;assert(!q.buffer,'Pending decode must not revive disposed player');
 console.log('PASS softened real friction: no pitch change, sparse timing, voice duck, stationary stop and pending-load cleanup');
})().catch(e=>{console.error(e);process.exitCode=1});

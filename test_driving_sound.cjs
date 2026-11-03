const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {cabinNoise,levels,Player}=require('./driving_sound.js');
for(const rate of [24000,44100,48000]){
 const b=cabinNoise(rate);assert.equal(b.road.length,rate*6);
 for(const a of [b.road,b.air]){assert(a.every(Number.isFinite));assert(a.every(x=>Math.abs(x)<1));assert(a.some(x=>Math.abs(x)>.03))}
}
assert.equal(levels(0).road,0);assert.equal(levels(0).motor,0);assert(levels(0).ambient>0);
assert(levels(60).road>levels(12).road);assert(levels(60).wind>levels(12).wind);
assert(levels(25,0,[],true).road<levels(25).road*.3);
assert.equal(levels(25,0,[],false,0).road,0);
assert(levels(10,0,[{kind:'vehicle',forward_m:2,right_m:-3}]).pan<0);
assert.equal(levels(10,0,[{kind:'pedestrian',forward_m:2,right_m:-3}]).traffic,0);
function context(){
 const starts=[],stops=[],parameter=()=>({value:0,setTargetAtTime(v){this.value=v}}),node=()=>({connect(){return this},disconnect(){}});
 return {starts,stops,currentTime:0,sampleRate:24000,state:'running',destination:{},resume(){this.state='running';return Promise.resolve()},close(){this.state='closed'},
  createGain:()=>Object.assign(node(),{gain:parameter()}),createBiquadFilter:()=>Object.assign(node(),{frequency:parameter()}),createStereoPanner:()=>Object.assign(node(),{pan:parameter()}),
  createBuffer:()=>({copyToChannel(){}}),createBufferSource:()=>Object.assign(node(),{start(){starts.push(this)},stop(){stops.push(this)}}),
  createOscillator:()=>Object.assign(node(),{frequency:parameter(),start(){starts.push(this)},stop(){stops.push(this)}})};
}
const ctx=context(),p=new Player(ctx);assert.equal(ctx.starts.length,5);p.update(30,[],false,.65);assert(p.road.gain.value>0);p.dispose();assert.equal(ctx.stops.length,5);p.dispose();assert.equal(ctx.stops.length,5);
(async()=>{
 const events={},documentEvents={},store=new Map(),contexts=[];let tick;
 const document={visibilityState:'visible',getElementById:()=>null,addEventListener:(k,v)=>documentEvents[k]=v};
 const window={CockpitUpdate(){},AudioContext:class{constructor(){const c=context();contexts.push(c);return c}}};
 const sandbox={window,document,crypto:{randomUUID:()=> 'test'},Date,Float32Array,Math,Number,Promise,
  localStorage:{getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v)},addEventListener:(k,v)=>events[k]=v,
  setInterval:f=>(tick=f,1),clearInterval(){}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/driving_sound.js','utf8'),sandbox);
 events.DOMContentLoaded();tick();const data={renderer:'CARLA RGB',connected:true,actors:[],nurec:{phase:'live',mode:'auto',speed_kph:20,scenario:{completed:false}}};
 window.CockpitUpdate(data);assert.equal(contexts.length,0,'No audio before real input');
 documentEvents.pointerdown();await Promise.resolve();assert.equal(contexts[0].starts.length,5);
 window.CockpitUpdate({...data,nurec:{...data.nurec,mode:'paused'}});assert.equal(contexts[0].stops.length,5);
 window.CockpitUpdate(data);assert.equal(contexts[0].starts.length,10);
 document.visibilityState='hidden';documentEvents.visibilitychange();assert.equal(contexts[0].stops.length,10);
 console.log('PASS cabin noise: finite waveforms, speed/traffic/voice mix, actual-input gate, pause/hidden disposal and no duplicate stop');
})().catch(e=>{console.error(e);process.exitCode=1});

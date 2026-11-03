const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
(async()=>{
 const events={},docEvents={},players=[],store=new Map();let tick,synthetic=0,fetches=0;
 const document={visibilityState:'visible',getElementById:()=>null,addEventListener:(k,f)=>docEvents[k]=f};
 const window={CockpitUpdate(){},AudioContext:class{
  constructor(){this.state='running'}resume(){return Promise.resolve()}close(){}
  createBuffer(){synthetic++;throw Error('NuRec must not create synthesized sound')}
 }};
 const sandbox={window,document,crypto:{randomUUID:()=> 'recorded-test'},Date,Math,Number,Promise,
  localStorage:{getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v)},addEventListener:(k,v)=>events[k]=v,
  setInterval:f=>(tick=f,1),clearInterval(){},fetch:async()=>{fetches++;return {ok:true,json:async()=>({available:true,url:'/api/cabin-audio/drive.mp3'})}},
  RecordedCabin:{Player:class{constructor(){this.calls=[];players.push(this)}update(...args){this.calls.push(args)}dispose(){this.dead=true}}}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/driving_sound.js','utf8'),sandbox);
 events.DOMContentLoaded();tick();const data={renderer:'NuRec RGB',connected:true,actors:[],nurec:{phase:'live',mode:'auto',speed_kph:25,scenario:{completed:false}}};
 window.CockpitUpdate(data);assert.equal(fetches,0);docEvents.pointerdown();
 for(let i=0;i<12;i++)await Promise.resolve();
 assert.equal(fetches,1);assert.equal(players.length,1);assert.equal(players[0].calls.at(-1)[0],25);assert.equal(synthetic,0);
 window.CockpitUpdate({...data,nurec:{...data.nurec,scenario:{completed:true}}});assert(players[0].dead);
 window.CockpitUpdate(data);assert.equal(players.length,2);
 document.visibilityState='hidden';docEvents.visibilitychange();assert(players[1].dead);
 console.log('PASS NuRec coordinator: no autoplay, recording catalog only after input, no synthetic fallback, completion/hidden disposal');
})().catch(e=>{console.error(e);process.exitCode=1});

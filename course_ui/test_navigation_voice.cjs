const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
vm.runInThisContext(fs.readFileSync(__dirname+'/navigation-voice.js','utf8'));
const route=(m,extra={})=>({destination:{id:'1',name:'홍익대학교'},remaining_m:m,...extra});
const state=(m,nav={},extra={})=>({connected:true,map:'Town05',ego:{id:1},session:{session_id:'a',scenario:6,stage:'running',navigation:nav},route:route(m),...extra});
const p=new NavigationVoicePlan();
assert.equal(p.update(state(1150,{status:'ready'})).length,0);
assert.match(p.update(state(1150))[0].text,/홍익대학교.*1150미터/);
assert.equal(p.update(state(1100)).length,0);
assert.match(p.update(state(990))[0].text,/1킬로미터/);
assert.equal(p.update(state(1005)).length,0);assert.equal(p.update(state(990)).length,0);
assert.match(p.update(state(280))[0].text,/300미터/); // skip stale 700/500
assert.equal(p.update(state(280)).length,0);
const hazard={id:'journey:1:0',status:'offered',title:'전방에 원목을 적재한 트럭이 있어요.',body:'옆 차로로 이동해 지나갈까요?'};
assert.match(p.update(state(250,hazard))[0].text,/원목.*차로/);
assert.equal(p.update(state(240,hazard)).length,0);
assert.equal(p.update(state(230,{...hazard,status:'executing'})).length,0);
assert.equal(p.update(state(220,hazard)).length,0);
assert.equal(p.update(state(210,{...hazard,id:'journey:2:0'})).length,1);
assert.equal(p.update({...state(15),route:route(15,{arrived:true})}).length,1); // 50m, physical journey not arrived
assert.match(p.update(state(2,{status:'arrived'}))[0].text,/도착했습니다/);
assert.equal(p.update(state(2,{status:'arrived'})).length,0);
assert.match(p.update({...state(700),session:{session_id:'b',stage:'running'}})[0].text,/안내를 시작/);
assert.match(p.update({...state(650),session:{session_id:'b',stage:'running'},route:route(650,{destination:{id:'2',name:'서울역'}})})[0].text,/서울역/);
assert.equal(p.update({connected:false}).length,0);
let spoken=[],cancelled=0;
const synth={getVoices:()=>[{lang:'en-US',localService:true},{lang:'ko-KR',name:'Heami',localService:true}],cancel:()=>cancelled++,speak:u=>spoken.push(u)};
class Utterance{constructor(text){this.text=text}}
const audio={volume:.6,muted:false},voice=new NavigationVoice({synth,Utterance,audio});
voice.update(state(800));assert.equal(spoken.length,0);voice.arm();assert.equal(spoken.length,1);
assert.equal(spoken[0].voice.name,'Heami');spoken[0].onstart();assert.equal(audio.volume,.15);
voice.setMusicVolume(.8);assert.equal(audio.volume,.2);
voice.update(state(780,hazard));assert.equal(spoken.length,2);assert.ok(cancelled);
spoken[1].onstart();assert.equal(globalThis.passengerTtsSpeaking,true);
voice.update(state(760,{...hazard,status:'executing'}));assert.equal(globalThis.passengerTtsSpeaking,false);assert.equal(audio.volume,.8);
voice.test();const stale=spoken.at(-1);stale.onstart();voice.setEnabled(false);stale.onend();assert.equal(audio.volume,.8);assert.equal(voice.queue.length,0);
voice.setEnabled(true);spoken.at(-1).onstart();spoken.at(-1).onend();
voice.update(state(740,{...hazard,id:'journey:3:0'}));voice.update({connected:false});assert.equal(voice.current,null);assert.equal(audio.volume,.8);
voice.reset();console.log('Navigation speech: distance milestones, jitter, context, hazard deduplication, actual arrival, Korean voice, priority, music restoration, cancellation passed.');

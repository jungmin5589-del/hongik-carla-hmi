/* Cached audio selection QA. No waveform quality or vehicle-actuation claim. */
const vm=require('vm'),fs=require('fs'),assert=require('assert/strict');
(async()=>{
 const urls=[],listeners={},voices={};for(const k of ['intent_gap','intent_horn','gap','partial','complete'])voices[k]={cached:true,url:'/voice/'+k+'.wav'};
 class Audio{constructor(url){urls.push(url)}play(){this.onplaying?.();return Promise.resolve()}pause(){}removeAttribute(){}load(){}remove(){}}
 const ctx={Audio,crypto:require('crypto'),console,Event:class{constructor(type){this.type=type}},dispatchEvent:()=>{},document:{visibilityState:'visible',body:{append(){}},addEventListener(){}},fetch:async()=>({json:async()=>({voices,actions:{widen:'gap'},intent_actions:{widen:'intent_gap',horn:'intent_horn'}})}),localStorage:{getItem:()=>null},addEventListener:(name,fn)=>listeners[name]=fn};ctx.window=ctx;
 vm.runInNewContext(fs.readFileSync(__dirname+'/feedback_voice.js','utf8'),ctx);listeners.DOMContentLoaded();
 const flush=()=>new Promise(r=>setImmediate(r));
 const update=(phase,action,status)=>ctx.CockpitUpdate({connected:true,session:{session_id:'s',navigation:{research_event:{study:{phase,action},outcome:{status}}}}});
 update('queued','widen');await flush();assert.deepEqual(urls,['/voice/intent_gap.wav']);
 update('applying','widen');await flush();assert.equal(urls.length,1,'do not interrupt the acknowledgement with generic applying audio');
 update('observing','widen','achieved');await flush();assert.equal(urls.at(-1),'/voice/gap.wav');
 update('observing','horn','partial');await flush();assert.equal(urls.at(-1),'/voice/partial.wav');
 console.log('PASS: prospective action voice; no generic interruption; outcome-gated result');
})().catch(e=>{console.error(e);process.exitCode=1});

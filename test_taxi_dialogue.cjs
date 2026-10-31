/* Actual CARLA + empty-profile headless browser: six finite, non-repeating lines. */
const fs=require('node:fs'),path=require('node:path');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function main(){
 const tabs=await(await fetch('http://127.0.0.1:9345/json/list')).json();
 const tab=tabs.find(t=>t.type==='page'&&['about:blank','http://127.0.0.1:8774/','http://127.0.0.1:8774/navigation'].includes(t.url));
 if(!tab?.webSocketDebuggerUrl.startsWith('ws://127.0.0.1:9345/'))throw Error('Expected own empty-profile QA browser');
 const ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 let id=0;const pending=new Map(),errors=[];
 ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.id){const p=pending.get(d.id);pending.delete(d.id);clearTimeout(p?.timer);d.error?p?.reject(Error(d.error.message)):p?.resolve(d.result)}else if(d.method==='Runtime.exceptionThrown')errors.push(d.params.exceptionDetails.text)};
 const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id,timer=setTimeout(()=>reject(Error(method+' timed out')),15000);pending.set(n,{resolve,reject,timer});ws.send(JSON.stringify({id:n,method,params}))});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value};
 const until=async(test,timeout=120000)=>{const end=Date.now()+timeout;while(Date.now()<end){if(await test())return;await delay(300)}throw Error('Taxi dialogue wait timeout')};
 const folder=path.join(__dirname,'validation','taxi-dialogue-'+Date.now());fs.mkdirSync(folder,{recursive:true});
 try{
  await send('Runtime.enable');await send('Page.enable');
  await send('Page.addScriptToEvaluateOnNewDocument',{source:"window.__taxiPlays=[];document.addEventListener('play',e=>{if(e.target.id==='city-exterior-audio'){const row={url:e.target.src,at:performance.now()};window.__taxiPlays.push(row);fetch('/state').then(r=>r.json()).then(s=>row.state=s)}},true);"});
  await send('Page.navigate',{url:'http://127.0.0.1:8774/'});
  await until(()=>evaluate("Boolean(document.querySelector('[data-profile=carpool]'))"));
  await evaluate("document.querySelector('[data-profile=carpool]').click()");
  await until(()=>evaluate("location.pathname==='/navigation'&&Boolean(document.getElementById('nurec-start'))&&!document.getElementById('nurec-start').disabled"));
  await evaluate("document.getElementById('nurec-start').click()");
  let final,firstFrame=false,doorFrame=false;const gaze=[];
  await until(async()=>{
   final=await(await fetch('http://127.0.0.1:8774/state')).json();if(final.error||final.scenario?.collision_count)throw Error(final.error||'Collision');
   if(!firstFrame&&await evaluate('window.__taxiPlays.length>0')){fs.writeFileSync(path.join(folder,'first-line-camera.jpg'),Buffer.from(await(await fetch('http://127.0.0.1:8774/frame.jpg')).arrayBuffer()));firstFrame=true}
   if(!doorFrame&&await evaluate('window.__taxiPlays.length>=2')){fs.writeFileSync(path.join(folder,'door-line-camera.jpg'),Buffer.from(await(await fetch('http://127.0.0.1:8774/frame.jpg')).arrayBuffer()));doorFrame=true}
   const ex=final.scenario?.context?.exterior;
   if(ex?.dialogue_started_s!==null&&ex?.dialogue_started_s!==undefined)gaze.push({elapsed:final.scenario.elapsed_s,...ex});
   return ex?.door_speech_started_s!==null&&ex?.door_speech_started_s!==undefined&&final.scenario.elapsed_s-ex.door_speech_started_s>=56;
  });
  const plays=await evaluate('window.__taxiPlays');
  const keys=plays.map(p=>new URL(p.url).pathname.split('/').at(-1).replace('.wav',''));
  const expected=['city_taxi_call','city_taxi_refusal','city_taxi_complaint','city_taxi_plate','city_taxi_door','city_taxi_answer'];
  if(JSON.stringify(keys)!==JSON.stringify(expected))throw Error('Unexpected or repeated voice sequence: '+JSON.stringify(keys));
  const first=plays[0]?.state?.scenario?.context?.exterior;
  if(!first||first.dialogue_started_s===null||first.call_distance_m>.38||!first.facing_vehicle)throw Error('First line started before close-range vehicle-facing attention: '+JSON.stringify(first));
  const second=plays[1]?.state?.scenario?.context?.exterior;
  if(!second?.at_window||second.knock_count<1||first.local_forward_m-second.local_forward_m<.4)throw Error('Door line did not follow physical movement and knocking: '+JSON.stringify(second));
  const moving=gaze.filter(s=>s.phase==='pacing'&&s.walk_speed_mps>.08);
  if(moving.length<3||moving.some(s=>Math.abs(s.facing_error_deg)>30))throw Error('Moving gaze was not maintained: '+JSON.stringify(moving));
  const near=gaze.filter(s=>s.knock_started_s!==null);
  if(near.some(s=>s.local_forward_m<.8||s.local_forward_m>2.2||s.local_right_m<1.4||s.local_right_m>2.1))throw Error('Actor wandered outside the short door-side strip');
  if(errors.length)throw Error(errors.join('; '));
  fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({passed:true,plays,gaze,final,scope:'Actual CARLA + isolated browser playback events; not acting quality or physical speaker/participant validation'},null,2));
  console.log('PASS six distinct taxi lines, once each in order, no runtime exception/collision: '+folder);
 }finally{
  await fetch('http://127.0.0.1:8774/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'paused'})}).catch(()=>{});
  await send('Page.navigate',{url:'about:blank'}).catch(()=>{});ws.close();
 }
}
main().catch(e=>{console.error(e);process.exitCode=1});

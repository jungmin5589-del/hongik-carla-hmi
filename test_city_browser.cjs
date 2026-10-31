/* Isolated headless QA browser only; never attaches to user browser profiles. */
const fs=require('node:fs'),path=require('node:path');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function main(){
 const profile=process.argv[2]||'yield',action=process.argv[3]||'study_direct';
 if(!['yield','carpool','rattle'].includes(profile))throw Error('Invalid profile');
 const tabs=await(await fetch('http://127.0.0.1:9345/json/list')).json();
 const tab=tabs.find(t=>t.type==='page'&&['about:blank','http://127.0.0.1:8774/','http://127.0.0.1:8774/navigation'].includes(t.url));
 if(!tab||!tab.webSocketDebuggerUrl.startsWith('ws://127.0.0.1:9345/'))throw Error('Expected own empty-profile QA browser');
 const ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 let id=0;const pending=new Map(),errors=[],audioRequests=[];
 ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.id){const j=pending.get(d.id);pending.delete(d.id);clearTimeout(j?.timer);d.error?j?.reject(Error(d.error.message)):j?.resolve(d.result)}else if(d.method==='Runtime.exceptionThrown')errors.push(d.params.exceptionDetails.text);else if(d.method==='Network.responseReceived'&&d.params.response.url.includes('/api/narration/audio/'))audioRequests.push({url:d.params.response.url,status:d.params.response.status})};
 const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id,timer=setTimeout(()=>{pending.delete(n);reject(Error(method+' timed out'))},20000);pending.set(n,{resolve,reject,timer});ws.send(JSON.stringify({id:n,method,params}))});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value};
 const until=async(test,timeout=100000)=>{const end=Date.now()+timeout;while(Date.now()<end){if(await test())return;await delay(250)}throw Error('Browser wait timeout')};
 const folder=path.join(__dirname,'validation','city-browser-'+profile+'-'+Date.now());fs.mkdirSync(folder,{recursive:true});
 const shot=async name=>{const r=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(folder,name+'.png'),Buffer.from(r.data,'base64'))};
 try{
  await send('Runtime.enable');await send('Page.enable');await send('Network.enable');
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:960,deviceScaleFactor:1,mobile:false});
  await send('Page.addScriptToEvaluateOnNewDocument',{source:"(()=>{window.__qaAudioContexts=[];const Original=window.AudioContext;window.AudioContext=class extends Original{constructor(...a){super(...a);window.__qaAudioContexts.push(this)}}})();"});
  await send('Page.navigate',{url:'http://127.0.0.1:8774/'});
  await until(()=>evaluate("Boolean(document.querySelector('[data-profile="+profile+"]'))"));await shot('selector');
  await evaluate("document.querySelector('[data-profile="+profile+"]').click()");
  await until(async()=>{const state=await(await fetch('http://127.0.0.1:8774/state')).json();if(state.error)throw Error(state.error);return evaluate("location.pathname==='/navigation'&&Boolean(document.getElementById('nurec-start'))&&!document.getElementById('nurec-start').disabled")});
  await evaluate("document.getElementById('nurec-start').click()");
  await until(async()=>{const s=await(await fetch('http://127.0.0.1:8774/state')).json();return s.scenario?.onset});
  if(profile==='carpool'){
   const external=await evaluate("({time:document.getElementById('city-exterior-audio')?.currentTime||0,contexts:window.__qaAudioContexts.map(c=>c.state)})");
   if(external.time<=0)throw Error('Exterior voice did not play: '+JSON.stringify(external));
  }
  await evaluate("document.getElementById('research-launch').click()");await delay(800);
  const first=await evaluate("({hidden:document.getElementById('research-options').hidden,skip:!document.getElementById('research-options-open').hidden,time:document.getElementById('research-sohee-audio')?.currentTime||0,eta:getComputedStyle(document.querySelector('#route-card .route-details')).display})");
  if(!first.hidden||!first.skip||first.time<=0||first.eta!=='none')throw Error('Explanation-first/Sohee/ETA check failed: '+JSON.stringify(first));
  await shot('explanation-first');
  if(profile==='yield')await until(()=>evaluate("!document.getElementById('research-options').hidden"));
  else await evaluate("document.getElementById('research-options-open').click()");
  await until(()=>evaluate("document.querySelectorAll('.research-option:not(:disabled)').length===4"));
  const layout=await evaluate("[...document.querySelectorAll('.research-option')].map(e=>{const r=e.getBoundingClientRect();return {label:e.querySelector('strong').textContent,x:r.x,y:r.y,width:r.width,bottom:r.bottom}})");
  if(!layout.every((r,i)=>Math.abs(r.x-layout[0].x)<1&&Math.abs(r.width-layout[0].width)<1&&(!i||r.y>layout[i-1].y)))throw Error('Options are not equal vertical peers');
  const dialogBottom=await evaluate("document.getElementById('research-dialog').getBoundingClientRect().bottom");
  if(layout.at(-1).bottom>dialogBottom-12)throw Error('Fourth option is clipped in the standard viewport');
  await shot('four-vertical-choices');
  const labels={study_direct:'직접 대응',study_external_notice:'외부 안내로 용건 확인하기',study_inspect:'차량 상태 점검 요청하기'};
  await evaluate("[...document.querySelectorAll('.research-option')].find(e=>e.querySelector('strong').textContent==="+JSON.stringify(labels[action])+").click()");
  await until(()=>evaluate("!document.getElementById('research-confirmation').hidden&&!document.getElementById('research-execute').disabled"));
  await shot('confirmation');await evaluate("document.getElementById('research-execute').click()");
  if(profile==='yield'){
   await until(()=>evaluate("!document.getElementById('research-direct-done').hidden"));await shot('direct-response');
   await delay(1500);const s=await(await fetch('http://127.0.0.1:8774/state')).json();if(!s.scenario.direct_pending)throw Error('Direct response completed without passenger confirmation');
   await evaluate("document.getElementById('research-direct-done').click()");
  }
  await until(async()=>{const s=await(await fetch('http://127.0.0.1:8774/state')).json();if(s.error)throw Error(s.error);return s.scenario?.completed});
  await until(()=>evaluate("!document.getElementById('research-ending').hidden"));await shot('ending');
  if(errors.length)throw Error(errors.join('; '));
  const final=await(await fetch('http://127.0.0.1:8774/state')).json();
  fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({passed:true,profile,action,first,layout,audioRequests,final,scope:'Isolated browser + actual CARLA, not physical speaker/iPhone/participant validation'},null,2));
  console.log('PASS '+profile+' staged explanation, Sohee, no ETA, four vertical choices, action and real result: '+folder);
 }finally{await send('Page.navigate',{url:'about:blank'}).catch(()=>{});ws.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});

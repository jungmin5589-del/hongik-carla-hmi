/* Run only against a separate, empty headless QA browser on port 9345. */
const fs=require('node:fs'),path=require('node:path');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function main(){
 const tabs=await(await fetch('http://127.0.0.1:9345/json/list')).json();
 const tab=tabs.find(t=>t.type==='page'&&t.url==='about:blank');
 if(!tab||!tab.webSocketDebuggerUrl.startsWith('ws://127.0.0.1:9345/'))throw Error('Expected our blank isolated QA page');
 const ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 let id=0;const pending=new Map(),errors=[];
 ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.id){const job=pending.get(d.id);pending.delete(d.id);clearTimeout(job?.timer);d.error?job?.reject(Error(d.error.message)):job?.resolve(d.result)}else if(d.method==='Runtime.exceptionThrown')errors.push(d.params.exceptionDetails.text)};
 const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;const timer=setTimeout(()=>{pending.delete(n);reject(Error('CDP timeout: '+method))},15000);pending.set(n,{resolve,reject,timer});ws.send(JSON.stringify({id:n,method,params}))});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value};
 const until=async(test,timeout=60000)=>{const end=Date.now()+timeout;while(Date.now()<end){if(await test())return;await delay(250)}throw Error('Browser wait timed out')};
 const folder=path.join(__dirname,'validation','pedestrian-browser-flow-'+Date.now());fs.mkdirSync(folder,{recursive:true});
 const shot=async name=>{const r=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(folder,name+'.png'),Buffer.from(r.data,'base64'))};
 try{
  await send('Runtime.enable');await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:960,deviceScaleFactor:1,mobile:false});
  await send('Page.navigate',{url:'http://127.0.0.1:8774/'});
  await until(()=>evaluate("Boolean(document.querySelector('[data-profile=yield]'))"));await shot('selector');
  await evaluate("document.querySelector('[data-profile=yield]').click()");
  await until(()=>evaluate("location.pathname==='/navigation'&&Boolean(document.getElementById('nurec-start'))&&!document.getElementById('nurec-start').disabled"));
  await evaluate("document.getElementById('nurec-start').click()");
  await until(async()=>{const s=await(await fetch('http://127.0.0.1:8774/state')).json();return s.scenario?.onset});
  await until(()=>evaluate("Boolean(document.getElementById('research-launch')?.classList.contains('has-update'))"));
  await evaluate("document.getElementById('research-launch').click()");
  await until(()=>evaluate("document.querySelectorAll('.research-option:not(:disabled)').length===3"));
  await delay(800);await shot('explanation-and-choices');
  const voice=await evaluate("({status:document.getElementById('research-voice-status').textContent,time:document.getElementById('research-sohee-audio')?.currentTime||0})");
  if(voice.time<=0)throw Error('Sohee audio did not advance: '+JSON.stringify(voice));
  await evaluate("document.querySelector('.research-option').click()");
  await until(()=>evaluate("!document.getElementById('research-confirmation').hidden&&!document.getElementById('research-execute').disabled"));
  await shot('confirmation');await evaluate("document.getElementById('research-execute').click()");
  await until(async()=>{const s=await(await fetch('http://127.0.0.1:8774/state')).json();return s.scenario?.yielding.phase==='crossing'});await shot('crossing');
  await until(async()=>{const s=await(await fetch('http://127.0.0.1:8774/state')).json();return s.scenario?.completed});
  await until(()=>evaluate("!document.getElementById('research-ending').hidden"));await shot('ending');
  const final=await(await fetch('http://127.0.0.1:8774/state')).json();
  if(final.scenario.yielding.announcement_count!==1||final.scenario.horn_count!==0)throw Error('Incorrect notice execution');
  if(errors.length)throw Error('Browser exceptions: '+errors.join('; '));
  fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({passed:true,voice,final,scope:'Isolated headless browser + real CARLA; not physical speaker/iPhone/participant QA'},null,2));
  console.log('PASS browser selector, navigation, alert, Sohee playback, three choices, explicit confirm, real crossing and ending: '+folder);
 }finally{ws.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});

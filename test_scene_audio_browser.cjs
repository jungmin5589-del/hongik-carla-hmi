/* Real CARLA, real decoded WebAudio signal; background visibility is reported explicitly. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{createRequire}=require('node:module');
const req=createRequire(process.env.CODEX_QA_NODE_ROOT||path.join(require('node:os').homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','package.json'));
const {chromium}=req('playwright');
async function main(){
 const folder=path.join(__dirname,'validation','scene-audio-'+Date.now());fs.mkdirSync(folder,{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true}),context=await browser.newContext(),page=await context.newPage(),errors=[],voices=[];page.on('pageerror',e=>errors.push(e.message));
 const state=async()=>(await page.request.get('http://127.0.0.1:8774/state')).json();
 const until=async(fn,seconds=65)=>{const end=Date.now()+seconds*1000;while(Date.now()<end){const v=await fn();if(v)return v;await page.waitForTimeout(150)}throw Error('Audio check timed out')};
 try{
  await page.addInitScript(()=>{const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){if(this.id==='city-exterior-audio'&&!window.qaRejectedVoice){window.qaRejectedVoice=true;return Promise.reject(new DOMException('QA simulated autoplay rejection','NotAllowedError'))}return play.call(this)}});
  await page.goto('http://127.0.0.1:8774/?lang=ko');await page.locator('[data-profile="carpool"]').click();await page.waitForURL('**/navigation',{timeout:90000});await page.locator('#passenger-depart').waitFor();await page.locator('#passenger-depart').click();
  const cover=await context.newPage();await cover.goto('about:blank');await cover.bringToFront();await page.waitForTimeout(300);
  let background=await page.evaluate(()=>document.visibilityState),method='real background tab';
  if(background!=='hidden'){await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,get:()=> 'hidden'});document.dispatchEvent(new Event('visibilitychange'))});background='hidden';method='emulated document visibility (headless browser)'}
  await until(async()=>{const d=await page.evaluate(()=>window.HongikSceneAudio?.getState());if(d?.voice==='city_taxi_call'&&d.time>.2&&d.rms>.0001){voices.push(d);return d}});
  assert.equal(voices[0].context,'running');assert.equal(voices[0].error,null);
  assert.equal(await page.evaluate(()=>window.qaRejectedVoice),true,'One rejected playback must have recovered');
  await until(async()=>{const d=await page.evaluate(()=>window.HongikSceneAudio?.getState());return d?.footstepCount>=4});
  await until(async()=>{const d=await page.evaluate(()=>window.HongikSceneAudio?.getState());if(d?.voice==='city_taxi_refusal'&&d.rms>.0001){voices.push(d);return d}});
  const stopped=await until(async()=>{const s=await state();return s.scenario?.context.exterior.at_window&&s.scenario.context.exterior.walk_speed_mps<.05?s:null});
  await page.waitForTimeout(300);const before=await page.evaluate(()=>HongikSceneAudio.getState().footstepCount);await page.waitForTimeout(2200);const after=await page.evaluate(()=>HongikSceneAudio.getState().footstepCount);assert.equal(after,before,'Stationary actor must not keep producing steps');
  await page.evaluate(()=>{delete document.visibilityState});await page.bringToFront();await page.locator('#research-launch').click();
  await until(()=>page.evaluate(()=>{const a=document.getElementById('research-sohee-audio');return a&&!a.paused&&a.currentTime>.1}));
  await page.evaluate(async()=>{const a=document.getElementById('research-sohee-audio'),c=new AudioContext(),m=c.createAnalyser();m.fftSize=256;c.createMediaElementSource(a).connect(m).connect(c.destination);await c.resume();window.qaAiOutput={c,m};Object.defineProperty(document,'visibilityState',{configurable:true,get:()=> 'hidden'});document.dispatchEvent(new Event('visibilitychange'))});
  const ai=await until(()=>page.evaluate(()=>{const a=document.getElementById('research-sohee-audio'),q=window.qaAiOutput,b=new Float32Array(256);q.m.getFloatTimeDomainData(b);const rms=Math.sqrt(b.reduce((n,x)=>n+x*x,0)/b.length);return a&&!a.paused&&a.currentTime>1&&rms>.0001?{rms,time:a.currentTime,url:a.currentSrc}:null}));
  assert.equal((await page.evaluate(()=>HongikSceneAudio.getState())).paused,true,'AI explanation has priority over actor dialogue');
  assert.deepEqual(errors,[]);const result={background,method,voices,ai,autoplay_retry_recovered:true,footsteps:after,stationary_steps_stopped:true,errors,scope:'Real CARLA and decoded browser output; no physical speaker listening claim'};fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));console.log(folder);
  await page.request.post('http://127.0.0.1:8774/control',{data:{mode:'paused'}});
 }finally{await browser.close()}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1});

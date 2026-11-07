/* Real native CARLA + isolated browser playback and rear-to-window timing. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{createRequire}=require('node:module');
const req=createRequire(process.env.CODEX_QA_NODE_ROOT||path.join(require('node:os').homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','package.json'));
const {chromium}=req('playwright');
async function main(){
 const english=process.argv.includes('--english');
 const folder=path.join(__dirname,'validation','rear-exterior-'+Date.now());fs.mkdirSync(folder,{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const get=async route=>(await page.request.get('http://127.0.0.1:8774'+route)).json();
 const until=async(fn,timeout=60000)=>{const end=Date.now()+timeout;while(Date.now()<end){const value=await fn();if(value)return value;await page.waitForTimeout(150)}throw Error('Rear approach did not reach required state')};
 const frame=async name=>fs.writeFileSync(path.join(folder,name+'.jpg'),await(await page.request.get('http://127.0.0.1:8774/frame.jpg')).body());
 try{
  await page.goto('http://127.0.0.1:8774/?lang='+(english?'en':'ko'));await page.locator('[data-profile="carpool"]').click();await page.waitForURL('**/navigation',{timeout:90000});await page.locator('#passenger-depart').waitFor();await frame('00-initial-side-window');await page.locator('#passenger-depart').click();
  const rear=await until(async()=>{const d=await get('/state'),ex=d.scenario?.context.exterior;if(ex?.voice_cue?.index===1&&ex.local_forward_m<-6)return d});await frame('01-voice-behind');
  await until(()=>page.evaluate(()=>{const a=document.getElementById('city-exterior-audio');return a&&!a.paused&&a.currentTime>.1}));
  const audio=await page.evaluate(()=>{const a=document.getElementById('city-exterior-audio');return {url:a.currentSrc,time:a.currentTime,paused:a.paused}});assert.ok(audio.url.endsWith((english?'/api/english-audio/':'/api/narration/audio/')+'city_taxi_call.wav'));
  const ex=rear.scenario.context.exterior,eye=rear.rig?.eye||rear.camera?.eye||(rear.rig?[0,-.35,1.2]:[.9,0,1.6]);
  const bearing=Math.atan2(ex.local_right_m-eye[1],ex.local_forward_m-eye[0])*180/Math.PI;
  const yaws=rear.rig?[-rear.rig.fov,0,rear.rig.fov].map(v=>v+rear.rig.yaw):[rear.camera?.yaw??35];
  const angles=yaws.map(y=>(bearing-y+540)%360-180),angle=Math.min(...angles.map(Math.abs));
  assert.ok(angles.every(a=>Math.abs(a)>(rear.rig?.fov||rear.camera?.fov||100)/2),'First voice must be outside all displayed camera FOVs');
  const windowState=await until(async()=>{const d=await get('/state');return d.scenario?.context.exterior.at_window?d:null});await frame('02-at-side-window');
  const door=await until(async()=>{const d=await get('/state');return d.scenario?.context.exterior.knock_count>=3?d:null});await frame('03-door-knock');
  assert.equal(door.scenario.collision_count,0);assert.ok(door.scenario.context.exterior.door_speech_started_s>rear.scenario.elapsed_s+5);
  await page.locator('#research-launch').click();await page.locator('#research-options button').first().waitFor();await page.screenshot({path:path.join(folder,'04-navigation-options.png')});
  await page.locator('[data-action="study_relocate"]').click();await page.locator('#research-execute').click();
  const final=await until(async()=>{const d=await get('/state');return d.scenario?.completed?d:null});assert.equal(final.scenario.outcome.status,'achieved');assert.equal(final.scenario.collision_count,0);assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({rear,windowState,door,final,audio,first_voice_outside_camera_degrees:angle,errors,scope:'Actual CARLA and browser audio playback; no physical speaker or participant judgement asserted'},null,2));
  console.log('REAR APPROACH VERIFIED',folder);
 }finally{await browser.close()}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1});

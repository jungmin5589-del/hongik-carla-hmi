/* Local browser fixtures only; no CARLA, real microphone or hardware claim. */
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{createRequire}=require('module');
const req=createRequire(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json'));
const {chromium}=req('playwright');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],sent=[],voices=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://experiment.test/**',async route=>{const u=new URL(route.request().url());
  if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:'<html><head><meta charset="utf-8"></head><body><button id="research-launch">AI</button><div id="midterm-passive">AI info</div><div id="research-dialog"><div class="midterm-choices"></div></div><button id="research-fixed-stop">Stop</button><div id="temperature">21</div><script>window.HongikFeedback={say:k=>(window.said??=[]).push(k)}</script><script src="/experiment_ui.js"></script></body></html>'});
  if(u.pathname==='/api/stt/status')return route.fulfill({json:{state:'ready'}});
  if(u.pathname==='/api/experiment/request'){const b=route.request().postDataJSON();sent.push(b);return route.fulfill({json:{supported:true,action:'notify',message:b.execute?'상황 변화 확인 중':'상황 변화를 알려드릴까요?'}})}
  if(u.pathname==='/api/command'){sent.push(route.request().postDataJSON());return route.fulfill({json:{accepted:true}})}
  const file=path.join(__dirname,u.pathname.slice(1));return route.fulfill({path:file});
 });await page.goto('https://experiment.test/');
 const update=async changes=>page.evaluate(changes=>{const d={connected:true,experiment:{ai_enabled:true,practice:false,profile:'night',request_serial:0,notice_id:0,...changes},session:{session_id:'trial-1',navigation:{id:'nav-1',research_event:{study:{phase:'idle'},outcome:{phase:'idle'}}}},nurec:{scenario:{completed:false}}};window.CockpitUpdate(d)},changes);
 await update({ai_enabled:false});assert.equal(await page.locator('#experiment-request').isVisible(),false);assert.equal(await page.locator('#research-launch').isVisible(),false);assert.equal(await page.locator('#research-fixed-stop').isVisible(),true);
 await update({});await page.locator('#experiment-type').click();await page.locator('#experiment-text').fill('위험해지면 알려 줘');await page.locator('#experiment-request form button').click();await page.locator('#experiment-confirm').waitFor({state:'visible'});assert.equal(sent.length,1);assert.equal(sent[0].execute,undefined);
 await page.locator('#experiment-cancel').click();assert.equal(sent.length,1);
 await page.locator('#experiment-request form button').click();await page.locator('#experiment-confirm').click();assert.equal(sent.at(-1).execute,true);assert.equal(sent.at(-1).source,'text');
 await update({watching:true,request_serial:1,last_request:'notify',feedback:'변화 확인 중'});assert.equal(await page.locator('#experiment-stop').isVisible(),true);
 await update({watching:true,request_serial:1,last_request:'notify',notified:true,notice_id:1,notice:'앞차에 주의',profile:'night'});assert.deepEqual(await page.evaluate(()=>window.said),['intent:notify','watch_risk']);
 await page.locator('#experiment-stop').click();assert.equal(sent.at(-1).action,'study_cancel_pending');
 await update({practice:true,temperature:22});assert.equal(await page.locator('#temperature').textContent(),'22.0°');
 assert.deepEqual(errors,[]);const folder=path.join(__dirname,'validation/experiment-fixture');fs.mkdirSync(folder,{recursive:true});await page.screenshot({path:path.join(folder,'request-card.png')});console.log('PASS: OFF hides AI, explicit confirm/cancel, direct request, monitoring feedback, practice display; fixtures only');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});

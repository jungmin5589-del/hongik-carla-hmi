/* Isolated UI fixture: no CARLA commands, real microphone or participant records. */
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{createRequire}=require('module');
const req=createRequire(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json'));
const {chromium}=req('playwright');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true,args:['--use-angle=swiftshader']});try{
 const page=await browser.newPage({viewport:{width:1194,height:834}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://notices.test/**',async route=>{const u=new URL(route.request().url());
  if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:'<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/course_ui/cockpit.css"><link rel="stylesheet" href="/midterm_panel.css"><body><header></header><main><div id="route-card"></div></main><footer><button id="temperature">21°</button><button id="emergency-stop">Stop</button></footer><script>window.spoken=[];window.HongikFeedback={say:k=>spoken.push(k),stop:()=>{}};</script><script src="/midterm_panel.js"></script></body>'});
  if(u.pathname==='/api/research-voice')return route.fulfill({json:{voices:{alert_congestion:{text:'앞차와 오른쪽 대형차가 서행하고 있어요.',cached:true,url:'/test.wav'}}}});
  if(u.pathname==='/api/command')return route.fulfill({json:{accepted:true}});
  const f=path.join(__dirname,u.pathname.slice(1));if(fs.existsSync(f))return route.fulfill({path:f});return route.fulfill({status:204});
 });await page.goto('https://notices.test/');
 const update=(active=true,extra={})=>page.evaluate(({active,extra})=>{const d={connected:true,session:{session_id:'qa',stage:'running',navigation:{id:'nav',research_event:{condition:'B',active,pending:false,title:'서행 상황',situation:'오른쪽 대형차가 서행하고 있어요.',vehicle_action:'간격을 유지하고 있어요.',options:[],study:{phase:'idle'},outcome:{phase:'idle'}}}},nurec:{profile:'congestion',scenario:{completed:false}},...extra};window.CockpitUpdate(d)},{active,extra});
 await update(false);assert.equal(await page.locator('#research-notice').isVisible(),false);
 await update();await page.locator('#research-notice').waitFor({state:'visible'});assert.deepEqual(await page.evaluate(()=>spoken),['alert_congestion']);
 for(let i=0;i<5;i++)await update();assert.equal((await page.evaluate(()=>spoken)).length,1,'one spoken notice per situation');
 await page.locator('#research-notice-close').click();await update();assert.equal(await page.locator('#research-notice').isVisible(),false);assert.equal(await page.locator('#research-launch').getAttribute('aria-expanded'),'false');
 await page.reload();await update();await page.locator('#research-notice-more').click();assert.equal(await page.locator('#research-dialog').isVisible(),true);assert.equal(await page.locator('#research-notice').isVisible(),false);assert.equal(await page.locator('#research-launch').getAttribute('aria-expanded'),'true');
 await page.reload();await update(true,{experiment:{ai_enabled:false,practice:false}});await page.waitForTimeout(100);assert.equal(await page.locator('#research-notice').isVisible(),false);assert.deepEqual(await page.evaluate(()=>spoken),[]);
 await page.reload();await update(true,{experiment:{ai_enabled:true,practice:true}});assert.equal(await page.locator('#research-notice').isVisible(),false);assert.deepEqual(await page.evaluate(()=>spoken),[]);
 await page.reload();await update();await page.locator('#research-notice').waitFor();await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator('#research-notice').evaluate(e=>getComputedStyle(e).animationName),'none');
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);const bounds=await page.locator('#research-notice').boundingBox();assert.ok(bounds.x>=0&&bounds.x+bounds.width<=390);
 assert.deepEqual(errors,[]);console.log('PASS notice once, dismiss, detail, OFF/practice exclusion, reduced motion and mobile width');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});

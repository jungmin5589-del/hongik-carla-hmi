/* Isolated local QA page over Playwright's private pipe; no user browser/profile. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {createRequire}=require('node:module');
const runtimeRequire=createRequire(process.env.CODEX_QA_NODE_ROOT||path.join(require('node:os').homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','package.json'));
const {chromium}=runtimeRequire('playwright');
async function main(){
 const english=process.argv.includes('--english');
 const folder=path.join(__dirname,'validation','midterm-browser-'+Date.now());fs.mkdirSync(folder,{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[],failed=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)failed.push([r.status(),r.url()])});
 const state=async()=>{const r=await page.request.get('http://127.0.0.1:8774/state');return r.json()};
 const shot=async name=>page.screenshot({path:path.join(folder,name+'.png'),fullPage:true});
 const until=async(test,timeout=40000)=>{const end=Date.now()+timeout;while(Date.now()<end){if(await test())return;await page.waitForTimeout(250)}throw Error('Actual state did not reach expected phase')};
 try{
  await page.goto('http://127.0.0.1:8774/?lang='+(english?'en':'ko'));await page.locator('[data-profile="night"]').click();
  await page.waitForURL('**/navigation',{timeout:90000});await page.locator('#passenger-depart').waitFor();await page.locator('#passenger-depart').click();
  assert.equal(await page.locator('#scene canvas').count(),1);assert.equal(await page.locator('.music-dock').count(),1);assert.equal(await page.locator('#navigation-map').count(),1);
  await page.locator('#research-launch.has-update').waitFor({state:'visible',timeout:60000});await shot('01-passive-banner');
  await page.locator('#research-launch').click();await page.locator('#research-options button').first().waitFor();
  assert.deepEqual(await page.locator('#research-options strong').allTextContents(),english?['Sound the horn','Increase the following distance','Overtake when safe','Wait at the roadside']:['클락션','거리 더 넓히기','안전할 때 앞질러 가기','갓길에서 잠시 기다리기']);
  await shot('02-junho-detail');if(english){await page.waitForTimeout(300);const a=await page.evaluate(()=>{const a=document.getElementById('research-sohee-audio');return {url:a?.currentSrc,time:a?.currentTime}});assert.ok(a.url?.endsWith('/api/english-audio/night.wav'));assert.ok(a.time>0);}assert.equal((await state()).scenario.horn_count,0);
  await page.locator('[data-action="study_horn"]').click();await page.locator('#research-execute').waitFor();assert.equal((await state()).scenario.horn_count,0);
  await page.locator('#research-execute').click();await page.locator('#research-countdown').waitFor();await shot('03-cancellable-countdown');await page.locator('#research-pending-cancel').click();
  await page.waitForTimeout(3500);assert.equal((await state()).scenario.horn_count,0);
  await page.locator('#research-launch').click();await page.locator('[data-action="study_horn"]').click();await page.locator('#research-execute').click();
  await until(async()=>(await state()).scenario?.study.phase==='observing');await page.waitForTimeout(400);await shot('04-actual-horn-result');
  assert.equal((await state()).scenario.horn_count,1);
  await until(async()=>(await state()).scenario?.completed);await page.waitForTimeout(400);await shot('05-complete');if(english)assert.equal(/[가-힣]/.test(await page.locator('#research-ending-summary').textContent()),false);
  await page.locator('#research-ending-home').click();await page.waitForTimeout(800);assert.equal(await page.locator('#research-ending').isVisible(),false);
  await page.setViewportSize({width:390,height:844});await shot('06-mobile');assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.locator('#settings-open').click();await page.locator('#settings-sheet').waitFor();await shot('07-settings');
  assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
  fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({errors,failed,verified:['explicit choice','3-second cancellation without horn','one physical horn','result and stop','mobile width','result dismiss'],state:await state()},null,2));
  console.log('BROWSER VERIFIED',folder);
 }finally{await browser.close()}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1});

/* Local start-screen fixture: no participant DB or simulator side effects. */
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{createRequire}=require('module');
const req=createRequire(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json'));
const {chromium}=req('playwright');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const page=await browser.newPage({viewport:{width:1194,height:834}}),errors=[],sent=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://start.test/**',async route=>{const u=new URL(route.request().url());
  if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(__dirname,'experiment.html'),'utf8')});
  if(u.pathname==='/state')return route.fulfill({json:{phase:'live',departure_ready:true,scenario:{elapsed_s:0,completed:false}}});
  if(u.pathname==='/api/stt/status')return route.fulfill({json:{state:'ready'}});
  if(u.pathname==='/api/participant/current')return route.fulfill({json:{participant:null}});
  if(u.pathname==='/api/select'){sent.push(route.request().postDataJSON());return route.fulfill({json:{accepted:true}})}
  return route.fulfill({status:204});
 });await page.goto('https://start.test/');
 assert.equal(await page.locator('#rounds button').count(),5);assert.match(await page.locator('h1').evaluate(e=>getComputedStyle(e).fontFamily),/Pretendard/);
 await page.locator('#test').check();await page.locator('#rounds button').nth(2).click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('준비 중'));assert.equal(sent.length,1);assert.equal(sent[0].experiment_index,2);assert.equal(sent[0].open_navigation,true);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(errors,[]);console.log('PASS start typography, anonymous selection payload, five rounds and responsive width');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});

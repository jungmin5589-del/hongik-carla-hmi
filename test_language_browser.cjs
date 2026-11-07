/* Isolated rendering fixture QA. Does not claim CARLA actuation verification. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{createRequire}=require('node:module');
const req=createRequire(process.env.CODEX_QA_NODE_ROOT||path.join(require('node:os').homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','package.json'));
const {chromium}=req('playwright');
async function main(){
 const folder=path.join(__dirname,'validation','english-fixture-'+Date.now());fs.mkdirSync(folder,{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[],failed=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)failed.push([r.status(),r.url()])});
 const scan=()=>page.evaluate(()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),out=[];while(w.nextNode()){const n=w.currentNode;if(!/[가-힣]/.test(n.data)||n.parentElement.closest('script,style,select,#tracks'))continue;const r=document.createRange();r.selectNode(n);if([...r.getClientRects()].some(x=>x.width&&x.height)&&getComputedStyle(n.parentElement).visibility!=='hidden')out.push(n.data.trim())}return [...new Set(out)].filter(Boolean)});
 try{
  await page.goto('http://127.0.0.1:8784/navigation?lang=en');await page.locator('#research-launch').waitFor();await page.waitForTimeout(1500);await page.screenshot({path:path.join(folder,'navigation-en.png')});const mainText=await scan();
  await page.locator('#research-launch').click();await page.waitForTimeout(1200);await page.screenshot({path:path.join(folder,'choices-en.png')});const dialogText=await scan();
  const choices=await page.locator('#research-options strong').allTextContents();assert.deepEqual(choices,['Sound the horn','Increase the following distance','Overtake when safe','Wait at the roadside']);
  const audio=await page.evaluate(()=>{const a=document.getElementById('research-sohee-audio');return a?{url:a.currentSrc,time:a.currentTime}:null});
  assert.ok(audio?.url.endsWith('/api/english-audio/night.wav'));assert.ok(audio.time>0);
  await page.locator('[data-action="study_horn"]').click();await page.waitForTimeout(400);await page.screenshot({path:path.join(folder,'confirmation-en.png')});const confirmText=await scan();
  await page.locator('#research-close').click();await page.locator('#settings-open').click();await page.waitForTimeout(300);const settingsText=await scan();await page.screenshot({path:path.join(folder,'settings-en.png')});
  await page.goto('http://127.0.0.1:8784/?lang=en');await page.waitForTimeout(500);await page.screenshot({path:path.join(folder,'selector-en.png'),fullPage:true});const homeText=await scan();
  await page.goto('http://127.0.0.1:8784/navigation?lang=ko');await page.locator('#research-launch').waitFor();await page.locator('#research-launch').click();await page.waitForTimeout(300);assert.equal(await page.locator('#research-options strong').first().textContent(),'클락션');
  const result={mainText,dialogText,confirmText,settingsText,homeText,choices,audio,errors,failed,scope:'Rendering fixture; no driving control'};fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));console.log(folder);
  assert.deepEqual([...mainText,...dialogText,...confirmText,...homeText,...settingsText],[]);assert.deepEqual(errors,[]);
 }finally{await browser.close()}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1});

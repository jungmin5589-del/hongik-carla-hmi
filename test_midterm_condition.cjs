/* Actual A-condition UI: passive card and fixed requests, no active invitation. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{createRequire}=require('node:module');
const req=createRequire(process.env.CODEX_QA_NODE_ROOT||path.join(require('node:os').homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','package.json'));
const {chromium}=req('playwright');
async function main(){
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];
 const folder=path.join(__dirname,'validation','midterm-condition-a-'+Date.now());fs.mkdirSync(folder,{recursive:true});page.on('pageerror',e=>errors.push(e.message));
 const get=async()=>(await page.request.get('http://127.0.0.1:8774/state')).json();
 try{
  await page.goto('http://127.0.0.1:8774/');await page.locator('#condition').selectOption('A');await page.locator('[data-profile="rattle"]').click();await page.waitForURL('**/navigation',{timeout:90000});await page.locator('#passenger-depart').waitFor();await page.locator('#passenger-depart').click();
  const end=Date.now()+30000;while(!(await get()).scenario?.onset){if(Date.now()>end)throw Error('No rattle onset');await page.waitForTimeout(250)}await page.waitForTimeout(600);
  assert.equal(await page.locator('#research-launch').isVisible(),false);assert.equal(await page.locator('#research-fixed-help').isVisible(),true);assert.equal(await page.locator('#research-fixed-stop').isVisible(),true);assert.equal(await page.locator('#midterm-passive').isVisible(),true);await page.screenshot({path:path.join(folder,'passive-only.png')});
  await page.locator('#research-fixed-stop').click();await page.locator('#research-execute').click();await page.locator('#research-countdown').waitFor();await page.screenshot({path:path.join(folder,'fixed-request-countdown.png')});await page.locator('#research-pending-cancel').click();await page.waitForTimeout(500);assert.equal((await get()).scenario.study.phase,'idle');assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({passed:true,errors,verified:['A no active invitation','passive status','fixed stop explicit confirmation','cancel before actuation']}));console.log('A CONDITION VERIFIED',folder);
 }finally{const s=await get();if(!s.scenario?.completed)await page.request.post('http://127.0.0.1:8774/control',{data:{mode:'paused'}});await browser.close()}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1});

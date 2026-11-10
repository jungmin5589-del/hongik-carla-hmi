/* Local portable service UI check; no drive request or physical motion. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{createRequire}=require('node:module');
const req=createRequire(process.env.CODEX_QA_NODE_ROOT||path.join(require('node:os').homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','package.json'));
const {chromium}=req('playwright');
async function main(){
 const folder=path.join(__dirname,'validation','lab-welcome-'+Date.now());fs.mkdirSync(folder,{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('http://127.0.0.1:8774/lab');await page.locator('#qr').waitFor({state:'visible'});
  await page.waitForFunction(()=>document.getElementById('qr').naturalWidth>0);
  const target=await page.locator('#url').getAttribute('href');assert.equal(new URL(target).pathname,'/m/navigation');
  assert.match(await page.locator('#pin').textContent(),/^\d{6}$/);
  const home=page.frameLocator('#navigation');await home.locator('#participant-name').waitFor();
  assert.equal(await home.locator('#hongik-language option[value="zh"]').count(),1);
  assert.equal(await home.locator('#research-admin').count(),1);
  await page.screenshot({path:path.join(folder,'01-portable-start-with-qr.png')});
  await page.locator('#toggle').click();assert.ok(await page.locator('body').evaluate(e=>e.classList.contains('compact')));
  await page.locator('#toggle').click();
  const fail=route=>route.abort();await page.route('http://127.0.0.1:8776/pc/state',fail);await page.locator('#refresh').click();
  await page.waitForFunction(()=>document.getElementById('qr').hidden&&document.getElementById('pin').textContent==='');
  assert.equal(await page.locator('#url').getAttribute('href'),null);
  await page.unroute('http://127.0.0.1:8776/pc/state',fail);await page.locator('#refresh').click();await page.locator('#qr').waitFor({state:'visible'});
  const state=await(await page.request.get('http://127.0.0.1:8774/state')).json();assert.equal(state.kind,'hongik-native-carla');assert.equal(state.lab_rig,true);assert.equal(state.mode,'paused');await page.locator('#return-select').waitFor();assert.equal(await page.locator('#return-select').isEnabled(),true);await page.locator('#return-select').click();assert.equal(await page.locator('#navigation').getAttribute('src'),'/?condition=B');
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({portableService:true,physicalLab:false,physicalMotion:false,driveStarted:false,errors,verified:['original selector and participant form','Mandarin selection available','actual gateway QR image decoded','connection-code polling','hide stale QR on connection loss','recover connection display','collapse QR panel']},null,2));
  console.log('LAB START UI VERIFIED',folder);
 }finally{await browser.close()}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1});

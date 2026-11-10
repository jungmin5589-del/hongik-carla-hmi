/* Real UI, SQLite and cached audio in an isolated server; not physical driving. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{createRequire}=require('node:module');
const req=createRequire(process.env.CODEX_QA_NODE_ROOT||path.join(require('node:os').homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','package.json'));
const {chromium}=req('playwright');
async function main(){
 const server=spawn('C:\\CARLA_0.9.16\\diagnostics\\nurec-env\\Scripts\\python.exe',['-u','research_preview.py'],{cwd:__dirname,stdio:['ignore','pipe','pipe']});let browser;
 try{
  const port=await new Promise((resolve,reject)=>{let out='',error='';const timer=setTimeout(()=>reject(Error('Preview timeout '+error)),20000);server.stderr.on('data',b=>error+=b);server.stdout.on('data',b=>{out+=b;const m=out.match(/PREVIEW=(.+})/);if(m){clearTimeout(timer);resolve(JSON.parse(m[1]).port)}});server.on('exit',c=>{clearTimeout(timer);reject(Error('Preview exited '+c+': '+error))})});
  browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1194,height:834}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const scan=()=>page.evaluate(()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),out=[];while(w.nextNode()){const n=w.currentNode;if(!/[가-힣]/.test(n.data)||n.parentElement.closest('script,style,select,#tracks,[data-no-translate]'))continue;const r=document.createRange();r.selectNode(n);if([...r.getClientRects()].some(x=>x.width&&x.height)&&getComputedStyle(n.parentElement).visibility!=='hidden')out.push(n.data.trim())}return [...new Set(out)].filter(Boolean)});
  const folder=path.join(__dirname,'validation','research-browser-'+Date.now());fs.mkdirSync(folder,{recursive:true});const origin='http://127.0.0.1:'+port;
  await page.goto(origin+'/?lang=zh');await page.locator('#participant-name').waitFor();assert.equal(await page.locator('[data-profile="night"]').isDisabled(),true);
  await page.locator('#participant-name').fill('QA-테스트-P001');await page.locator('#participant-save').click();await page.waitForFunction(()=>!document.querySelector('[data-profile="night"]').disabled);
  assert.ok((await page.locator('#participant-status').textContent()).includes('QA-테스트-P001'));
  assert.deepEqual(await scan(),[]);await page.screenshot({path:path.join(folder,'01-chinese-registration.png')});await page.locator('[data-profile="night"]').click();await page.waitForURL('**/navigation');
  await page.locator('#settings-open').click();assert.deepEqual(await scan(),[]);await page.locator('#settings-close').click();await page.locator('#passenger-depart').click();await page.locator('#research-launch').click();await page.locator('[data-action="study_horn"]').waitFor({state:'visible'});
  await page.waitForFunction(()=>document.getElementById('research-sohee-audio')?.currentTime>.1);
  const source=await page.locator('#research-sohee-audio').getAttribute('src');assert.ok(source.includes('/api/chinese-audio/'));
  assert.equal(/[가-힣]/.test(await page.locator('#research-dialog').innerText()),false);
  await page.screenshot({path:path.join(folder,'02-chinese-dialog.png')});
  await page.locator('[data-action="study_horn"]').click();await page.waitForFunction(()=>document.getElementById('research-feedback-audio')?.currentTime>.1);
  assert.ok((await page.locator('#research-feedback-audio').getAttribute('src')).includes('zh_choice'));
  await page.locator('#research-execute').click();await page.waitForFunction(()=>document.getElementById('research-feedback-audio')?.currentSrc.includes('zh_horn'));
  assert.equal(await page.evaluate(()=>[...document.querySelectorAll('audio')].filter(a=>!a.paused&&!a.ended).length),1);
  await page.locator('#research-ending').waitFor({state:'visible'});await page.waitForFunction(()=>document.getElementById('research-feedback-audio')?.currentSrc.includes('zh_complete'));
  await page.locator('#research-ending-home').click();await page.waitForURL(u=>u.pathname==='/');assert.equal(new URL(page.url()).searchParams.get('lang'),'zh');
  await page.locator('#research-admin').click();await page.locator('#rows tr').waitFor();assert.equal(await page.locator('#rows tr').count(),1);
  const cells=await page.locator('#rows tr td').allTextContents();assert.equal(cells[0],'QA-테스트-P001');assert.ok(cells.includes('17.25초'));assert.ok(cells.includes('7.25초'));assert.ok(cells.includes('18.00초'));
  await page.screenshot({path:path.join(folder,'03-admin-records.png')});await page.locator('#rows tr').click();await page.locator('#detail').waitFor({state:'visible'});await page.screenshot({path:path.join(folder,'04-event-timeline.png')});
  const response=await page.request.get(origin+'/admin/export?kind=events');assert.equal(response.status(),200);assert.ok((await response.text()).includes('navigation_study_choice'));
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({fixture:true,physicalDrive:false,errors,verified:['registration required','name preserved','Chinese interface and Mandarin voice','choice and outcome speech','one speaker at a time','return preserves language','SQLite timing and admin timeline','CSV export']},null,2));
  console.log('RESEARCH UI VERIFIED',folder);
 }finally{await browser?.close();server.kill()}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1});

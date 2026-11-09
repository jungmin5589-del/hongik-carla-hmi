/* Real LAN HTTP + original cockpit + live read-only geometry. Commands are fixtures. */
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {spawn}=require('node:child_process'),{createRequire}=require('node:module');
const req=createRequire(process.env.CODEX_QA_NODE_ROOT||path.join(require('node:os').homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','package.json'));
const {chromium}=req('playwright');
async function main(){
 const folder=path.join(__dirname,'validation','tablet-browser-'+Date.now());fs.mkdirSync(folder,{recursive:true});
 const py=path.join(__dirname,'..','mobile-env','Scripts','python.exe');
 const server=spawn(py,['-u','-c',`
import io,json,tempfile,urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer
from mobile_gateway import Gateway,handler,local_ip
import tablet_navigation
with urllib.request.urlopen('http://127.0.0.1:8774/api/state',timeout=4) as r:data=json.load(r)
data['session']['navigation']['research_event']['active']=True
data['nurec']['scenario']['onset']=True
temporary=tempfile.TemporaryDirectory()
gateway=Gateway(Path(temporary.name),address=local_ip(),fetcher=lambda:data)
gateway.poll_once()
def queue(body,source='hongik_tablet'):
 with open(${JSON.stringify(path.join(folder,'commands.jsonl'))},'a',encoding='utf-8') as f:f.write(json.dumps(dict(action=body.get('action'),source=source))+chr(10))
 return dict(session_id=body['session_id'],command_id='fixture-command')
gateway.queue_command=queue
original=tablet_navigation.backend
def backend(route,**kwargs):
 if route.startswith('/api/reply'):return io.BytesIO(b'{"accepted":true,"message":"fixture only"}')
 if route=='/control':return io.BytesIO(b'{"accepted":true}')
 return original(route,**kwargs)
tablet_navigation.backend=backend
server=ThreadingHTTPServer(('0.0.0.0',0),handler(gateway))
print('FIXTURE='+json.dumps(dict(port=server.server_port,address=gateway.address,pin=gateway.pairing.pin)),flush=True)
server.serve_forever()
 `],{cwd:__dirname,stdio:['ignore','pipe','pipe']});
 let browser;
 try{
  const fixture=await new Promise((resolve,reject)=>{let output='',error='';const timer=setTimeout(()=>reject(Error('Fixture startup timeout')),20000);server.stderr.on('data',b=>error+=b);server.stdout.on('data',b=>{output+=b;const m=output.match(/FIXTURE=(.+})/);if(m){clearTimeout(timer);resolve(JSON.parse(m[1]))}});server.once('exit',c=>{clearTimeout(timer);reject(Error('Fixture exited '+c+': '+error))})});
  browser=await chromium.launch({channel:'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1194,height:834},hasTouch:true,isMobile:true,userAgent:'Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1'});
  const page=await context.newPage(),errors=[],bad=[];page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)bad.push({status:r.status(),path:new URL(r.url()).pathname})});
  const origin='http://'+fixture.address+':'+fixture.port;
  await page.goto(origin+'/m/navigation');await page.locator('#code').fill(fixture.pin);await page.locator('#connect').click();
  await page.waitForURL('**/navigation');await page.locator('#research-launch').waitFor({state:'visible'});
  assert.equal(await page.locator('#scene canvas').count(),1);assert.equal(await page.locator('#navigation-map').count(),1);assert.equal(await page.locator('.music-dock').count(),1);
  assert.equal(await page.evaluate(()=>isSecureContext),false);assert.equal(await page.evaluate(()=>typeof crypto.randomUUID),'function');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(folder,'01-full-ipad-navigation.png')});
  await page.locator('#zoom-in').click();await page.locator('#overhead').click();
  await page.locator('#play').click();await page.waitForFunction(()=>[...document.querySelectorAll('audio')].some(a=>a.currentSrc.includes('/media/')&&a.currentTime>0));
  await page.locator('#play').click();
  await page.locator('#research-launch').click();await page.locator('#research-options button').first().waitFor({state:'visible'});
  await page.waitForFunction(()=>document.getElementById('research-sohee-audio')?.currentTime>.1);
  await page.screenshot({path:path.join(folder,'02-ai-and-choices.png')});
  const selectedAction=await page.locator('#research-options button').first().getAttribute('data-action');
  await page.locator('#research-options button').first().click();await page.locator('#research-execute').waitFor({state:'visible'});
  await page.locator('#research-execute').click();await page.waitForTimeout(500);
  const commands=fs.readFileSync(path.join(folder,'commands.jsonl'),'utf8').trim().split(String.fromCharCode(10)).map(JSON.parse);
  assert.ok(commands.some(c=>c.action===selectedAction));assert.ok(commands.every(c=>c.source==='hongik_tablet'));
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({physicalDrive:false,deviceEmulation:true,realIP:true,errors,bad,commands,verified:['paired full cockpit','LAN HTTP UUID compatibility','Three.js canvas','map controls','music playback','cached Sohee playback','choices and confirmed request']},null,2));
  console.log('TABLET UI VERIFIED',folder,'optional unavailable responses',JSON.stringify(bad));
 }finally{await browser?.close();server.kill()}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1});

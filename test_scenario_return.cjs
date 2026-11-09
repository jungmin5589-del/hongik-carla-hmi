/* Real app UI + isolated fixture states: never starts CARLA or moves a vehicle. */
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {spawn}=require('node:child_process'),{createRequire}=require('node:module');
const req=createRequire(process.env.CODEX_QA_NODE_ROOT||path.join(require('node:os').homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','package.json'));
const {chromium}=req('playwright');
async function main(){
 const py=process.env.HONGIK_TEST_PYTHON||'C:\\CARLA_0.9.16\\diagnostics\\nurec-env\\Scripts\\python.exe';
 const server=spawn(py,['-u','-c',`
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
import native_carla
from preview_language import fixture
value=fixture()
bridge=SimpleNamespace(presentation='midterm',navigation=SimpleNamespace(state=lambda:value,atlas=lambda:dict(map='CARLA',roads=[],destinations=[],buildings=[])),state=dict(phase='live',profile='night',frames=3,width=1280,height=720,measured_fps=0),scenario=None)
server=ThreadingHTTPServer(('127.0.0.1',0),native_carla.handler(bridge))
native_carla.PORT=server.server_port
print('FIXTURE_PORT='+str(server.server_port),flush=True)
server.serve_forever()
 `],{cwd:__dirname,stdio:['ignore','pipe','pipe']});
 let browser;
 try{
  const port=await new Promise((resolve,reject)=>{let output='',error='';const timer=setTimeout(()=>reject(Error('Fixture startup timeout')),20000);server.stderr.on('data',b=>error+=b);server.stdout.on('data',b=>{output+=b;const match=output.match(/FIXTURE_PORT=(\d+)/);if(match){clearTimeout(timer);resolve(Number(match[1]))}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+': '+error))})});
  const origin='http://127.0.0.1:'+port;
  browser=await chromium.launch({channel:'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1280,height:720}});
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const seed=await(await page.request.get(origin+'/api/state')).json();
  let state=structuredClone(seed),hubProfile='night',selections=[];
  await page.route(url=>url.pathname==='/api/state',r=>r.fulfill({json:state}));
  await page.route(url=>url.pathname==='/state',r=>r.fulfill({json:{phase:'live',profile:hubProfile,frames:3,width:1280,height:720,measured_fps:0}}));
  await page.route('**/api/select',r=>{const body=r.request().postDataJSON();selections.push(body);hubProfile=body.profile;r.fulfill({json:{accepted:true}})});
  const folder=path.join(__dirname,'validation','scenario-return-'+Date.now());fs.mkdirSync(folder,{recursive:true});
  const verified=[];
  for(const kind of ['action','duration'])for(const lang of ['ko','en']){
   const condition=lang==='en'?'A':'B';
   state=structuredClone(seed);state.session.session_id+='-'+kind+'-'+lang;
   state.session.navigation.research_event.condition=condition;
   await page.goto(origin+'/navigation?voice=0&lang='+lang);
   await page.waitForFunction(()=>!document.querySelector('#research-ui').hidden);
   assert.equal(await page.locator('#research-ending').isVisible(),false);
   assert.equal(await page.locator('#research-return-home').isVisible(),false);
   const event=state.session.navigation.research_event;
   event.active=false;event.outcome={phase:'observing',summary:'',message:''};
   await page.waitForTimeout(500);assert.equal(await page.locator('#research-ending').isVisible(),false);
   state.nurec.scenario.completed=true;
   state.nurec.scenario.completion_reason=kind==='action'?'action_outcome':'duration_end';
   event.outcome={phase:kind==='action'?'complete':'idle',summary:'',message:''};
   await page.locator('#research-ending').waitFor({state:'visible'});
   assert.equal(await page.locator('#research-ending-home').textContent(),lang==='en'?'Back to scenario selection':'시나리오 선택으로');
   assert.equal(await page.locator('#research-fixed-stop').isVisible(),false);
   await page.waitForTimeout(800);assert.equal(new URL(page.url()).pathname,'/navigation');
   if(kind==='duration'){
    await page.locator('#research-ending-close').click();
    await page.locator('#research-return-home').waitFor({state:'visible'});
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(folder,kind+'-'+lang+'.png')});
    await page.locator('#research-return-home').click();
   }else{
    await page.screenshot({path:path.join(folder,kind+'-'+lang+'.png')});
    await page.locator('#research-ending-home').click();
   }
   await page.waitForURL(url=>url.pathname==='/');
   assert.equal(new URL(page.url()).searchParams.get('lang'),lang);
   assert.equal(await page.locator('#condition').inputValue(),condition);
   assert.equal(await page.locator('[data-profile]').count(),7);
   const before=selections.length;await page.waitForTimeout(800);assert.equal(selections.length,before);
   await page.locator('[data-profile="fog"]').click();await page.waitForURL('**/navigation');
   assert.deepEqual(selections.at(-1),{profile:'fog',presentation:'midterm',condition});
   verified.push(kind+' / '+lang+' / condition '+condition);
   await page.setViewportSize({width:1280,height:720});
  }
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({fixture:true,physicalDrive:false,verified,errors},null,2));
  console.log('SCENARIO RETURN VERIFIED',folder,verified);
 }finally{await browser?.close();server.kill()}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1});

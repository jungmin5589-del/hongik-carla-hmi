/* Browser regression fixtures; no claim of CARLA actuation or live audio QA. */
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {createRequire}=require('module');
const req=createRequire(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json'));
const {chromium}=req('playwright');
const {spawnSync}=require('child_process');
const output=path.join(__dirname,'validation/pilot-feedback');fs.mkdirSync(output,{recursive:true});
const py=process.env.HONGIK_TEST_PYTHON||'python';
const generated=spawnSync(py,['-X','utf8','-c',"import sys,json;sys.path.insert(0,sys.argv[1]);from english_locale import catalog as en;from chinese_locale import catalog as zh;print(json.dumps({'en':en(),'zh':zh()},ensure_ascii=False))",__dirname],{encoding:'utf8'});
if(generated.status!==0)throw Error(generated.stderr);
for(const [lang,pack] of Object.entries(JSON.parse(generated.stdout)))fs.writeFileSync(path.join(output,lang+'.json'),JSON.stringify(pack));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true,args:['--use-angle=swiftshader']});
 try{
  for(const lang of ['en','zh']){
   const page=await browser.newPage({viewport:{width:1280,height:800}}),errors=[],sent=[];
   let staged=false;
   const fixture=()=>({connected:true,session:{session_id:'qa',stage:'running',navigation:{id:'qa-nav',research_event:{condition:'B',active:true,pending:false,feedback:'',title:'농무 상황',situation:'안개가 점점 짙어져 전방 시야가 제한되고 있어요.',vehicle_action:'감속하고 있어요.',options:[{action:'study_horn',label:'클락션',detail:'앞차에 경적을 한 번 짧게 울려요.'},{action:'study_slow',label:'더 천천히 가기',detail:'속도를 더 낮추고 앞차와의 거리를 확보해요.'}],staged_options:staged,study:{phase:'idle'},outcome:{phase:'idle'}}}},nurec:{scenario:{id:'congestion_long',completed:false}},actors:[]});
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('https://pilot.test/**',async route=>{
    const url=new URL(route.request().url());
    if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:'<!doctype html><html><head><meta charset="utf-8"><script src="/language.js"></script><style>[hidden]{display:none!important}</style></head><body><div id="route-card"></div><button id="music" aria-label="번역없는 노래">Music</button><div id="music-menu" hidden></div><script>document.getElementById("music").onclick=()=>{const n=document.getElementById("music-menu");n.hidden=!n.hidden;n.setAttribute("title","번역없는 노래");n.textContent="음악을 선택하세요"}</script><script src="/midterm_panel.js"></script></body></html>'});
    if(url.pathname==='/api/language/'+lang)return route.fulfill({contentType:'application/json',body:fs.readFileSync(path.join(__dirname,'validation/pilot-feedback',lang+'.json'))});
    if(url.pathname==='/api/state')return route.fulfill({json:fixture()});
    if(url.pathname==='/api/command'){sent.push(route.request().postDataJSON());return route.fulfill({json:{accepted:true,session_id:'qa',command_id:'q'}})}
    if(url.pathname==='/api/reply')return route.fulfill({json:{accepted:true,message:'요청을 받았어요.'}});
    const file=path.join(__dirname,url.pathname.slice(1));if(fs.existsSync(file))return route.fulfill({path:file});
    return route.fulfill({status:204});
   });
   const refresh=()=>page.evaluate(async()=>window.CockpitUpdate(await(await fetch('/api/state')).json()));
   await page.goto('https://pilot.test/?lang='+lang);await page.evaluate(()=>HongikLocale.ready);await refresh();
   // Unknown Korean attributes must not create an unbounded observer loop.
   for(let i=0;i<5;i++){await page.locator('#music').click();await page.waitForTimeout(40)}
   assert.equal(await page.evaluate(()=>1+1),2);
   await page.locator('#research-launch').click();await page.locator('[data-action="study_horn"]').waitFor();
   await page.locator('[data-action="study_horn"]').click();await page.locator('#research-execute').waitFor();
   assert.equal(sent.some(x=>x.action==='study_horn'),false,'choice must not execute');
   await page.locator('#research-execute').click();assert.equal(sent.filter(x=>x.action==='study_horn').length,1);
   await page.waitForFunction(()=>document.getElementById('research-feedback').textContent.length>0&&!/[가-힣]/.test(document.getElementById('research-feedback').textContent),null,{timeout:4000});
   const text=await page.locator('#research-feedback').textContent();assert.equal(/[가-힣]/.test(text),false,'request acknowledgement is localized');
   await page.screenshot({path:path.join(__dirname,'validation/pilot-feedback',lang+'-confirmation.png')});
   await page.evaluate(()=>window.CockpitUpdate({connected:false}));
   assert.equal(await page.locator('#research-launch').isVisible(),true,'connection glitch must not remove AI control');
   assert.equal(await page.locator('#research-launch').isDisabled(),true,'stale commands are disabled');
   await refresh();assert.equal(await page.locator('#research-launch').isEnabled(),true);
   // Missing explanation audio cannot permanently hide staged options.
   staged=true;await page.reload();await page.evaluate(()=>HongikLocale.ready);await refresh();
   await page.locator('#research-launch').click();await page.locator('[data-action="study_horn"]').waitFor({state:'visible',timeout:7000});
   assert.equal(await page.locator('[data-action="study_horn"]').isEnabled(),true);
   assert.deepEqual(errors,[]);console.log('PASS',lang,'music remains responsive; choices; explicit execute; localized reply; missing audio recovery');
   await page.close();
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});

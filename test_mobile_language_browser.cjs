/* Local mobile rendering fixture. No phone pairing, notification or drive is changed. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{createRequire}=require('node:module'),{execFileSync}=require('node:child_process');
const req=createRequire(process.env.CODEX_QA_NODE_ROOT||path.join(require('node:os').homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','package.json'));
const {chromium}=req('playwright');
async function main(){
 const pack=JSON.parse(execFileSync(process.env.HONGIK_PYTHON||'C:/CARLA_0.9.16/diagnostics/nurec-env/Scripts/python.exe',['-c','import json;from english_locale import catalog;print(json.dumps(catalog(),ensure_ascii=True))'],{cwd:__dirname,encoding:'utf8'}));
 const folder=path.join(__dirname,'validation','mobile-english-fixture-'+Date.now());fs.mkdirSync(folder,{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:390,height:844}});let paired=false;const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const state={connected:true,session:'render-only',navigation_id:'render-only-weaving',destination:'목적지',speed_kph:30,remaining_m:1000,gap_m:6.5,stage:'running',event:{study:{phase:'idle'},condition:'B',active:true,title:'앞차가 차선을 넘나들고 있어요',description:'앞 차량이 좌우로 흔들리며 차선 경계에 접근하고 있어요.',options:[{action:'study_horn',label:'클락션',detail:'앞차에 경적을 한 번 짧게 울려요.'}],narration:{cached:true,url:'/m/audio/night.wav'}}};
 await page.route('http://127.0.0.1:8784/m/**',async route=>{
  const url=new URL(route.request().url()),p=url.pathname;
  if(p==='/m/language/en')return route.fulfill({json:pack});
  if(p==='/m/api/state')return route.fulfill(paired?{json:state}:{status:401,json:{error:'연결이 필요합니다.'}});
  if(p==='/m/api/pair'){paired=true;return route.fulfill({json:{ok:true}})}
  if(p.startsWith('/m/api/'))return route.fulfill({json:{accepted:true}});
  if(p==='/m/sw.js')return route.fulfill({contentType:'application/javascript',body:''});
  if(p.startsWith('/m/english-audio/'))return route.fulfill({response:await page.request.get('http://127.0.0.1:8774/api/english-audio/'+p.split('/').pop())});
  const map={'/m/':'mobile/index.html','/m/app.css':'mobile/app.css','/m/app.js':'mobile/app.js','/m/language.js':'language.js'};
  if(!map[p])return route.fulfill({status:204});let body=fs.readFileSync(path.join(__dirname,map[p]));if(p==='/m/')body=Buffer.from(body.toString().replace('</head>','<script src="/m/language.js"></script></head>'));
  return route.fulfill({body,contentType:p.endsWith('.js')?'application/javascript':p.endsWith('.css')?'text/css':'text/html'});
 });
 const scan=()=>page.evaluate(()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),out=[];while(w.nextNode()){const n=w.currentNode;if(!/[가-힣]/.test(n.data)||n.parentElement.closest('script,style,select'))continue;const r=document.createRange();r.selectNode(n);if([...r.getClientRects()].some(x=>x.width&&x.height))out.push(n.data.trim())}return [...new Set(out)].filter(Boolean)});
 try{
  await page.goto('http://127.0.0.1:8784/m/?lang=en');await page.waitForTimeout(500);const pairingText=await scan();await page.locator('#settings').click();await page.waitForTimeout(150);const settingsText=await scan();await page.screenshot({path:path.join(folder,'settings-en.png'),fullPage:true});await page.locator('#pref-close').click();
  await page.locator('#code').fill('123456');await page.locator('#pair-form button').click();await page.locator('#dashboard').waitFor();await page.locator('#launch').click();await page.waitForTimeout(300);const choicesText=await scan();await page.screenshot({path:path.join(folder,'choices-en.png'),fullPage:true});
  await page.locator('[data-action="study_horn"]').click();await page.waitForTimeout(100);const confirmText=await scan();
  const result={pairingText,settingsText,choicesText,confirmText,errors,scope:'Mobile rendering fixture only; no actual phone or push delivery'};fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));console.log(folder);
  assert.deepEqual([...pairingText,...settingsText,...choicesText,...confirmText],[]);assert.deepEqual(errors,[]);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 }finally{await browser.close()}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1});

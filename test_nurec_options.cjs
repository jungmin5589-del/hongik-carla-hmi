/* Headless app QA only. No CARLA, NuRec GPU or motion hardware is simulated. */
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert/strict'),{createRequire}=require('module');
const req=createRequire(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json'));
const {chromium}=req('playwright');
(async()=>{const server=http.createServer((request,response)=>{
 const route=new URL(request.url,'http://fixture.local').pathname;
 const send=(code,type,body)=>{response.writeHead(code,{'Content-Type':type});response.end(body)};
 if(route==='/api/status')return send(200,'application/json',JSON.stringify({phase:'idle',ssd_connected:false,drive:null}));
 if(route==='/api/select')return send(400,'application/json',JSON.stringify({error:'NuRec 원본 SSD를 연결해 주세요.'}));
 if(route==='/font.woff2')return send(200,'font/woff2',fs.readFileSync(path.join(__dirname,'course_ui/vendor/PretendardVariable.woff2')));
 if(route==='/')return send(200,'text/html; charset=utf-8',fs.readFileSync(path.join(__dirname,'render_options.html')));
 send(404,'text/plain','not found');
 });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:920}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const folder=path.join(__dirname,'validation','nurec-options-'+Date.now());fs.mkdirSync(folder,{recursive:true});
 await page.goto(origin+'/');await page.getByText('연결 필요',{exact:true}).waitFor();
 assert.equal(await page.locator('[data-engine="nurec"]').getAttribute('aria-pressed'),'true');
 assert.equal(await page.locator('#open').isVisible(),false);
 const rect=await page.locator('.screens').boundingBox();assert.ok(Math.abs(rect.width/rect.height-16/3)<.02);
 await page.screenshot({path:path.join(folder,'01-options-desktop.png'),fullPage:true});
 const popupPromise=page.waitForEvent('popup');await page.locator('[data-profile="congestion"]').click();const popup=await popupPromise;
 await page.waitForFunction(()=>document.querySelector('#status').classList.contains('error'));
 assert.ok(/SSD|외장|NuRec 원본/.test(await page.locator('#status').textContent()));
 await page.waitForFunction(()=>!document.querySelector('[data-profile="congestion"]').disabled);
 assert.equal(popup.isClosed(),true);
 await page.screenshot({path:path.join(folder,'02-missing-ssd.png'),fullPage:true});
 await page.locator('[data-engine="carla"]').click();assert.equal(await page.locator('#quality').isDisabled(),true);assert.equal(await page.locator('#limits').isVisible(),false);
 await page.setViewportSize({width:768,height:1024});await page.screenshot({path:path.join(folder,'03-options-tablet.png'),fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 const waiting=await browser.newPage();
 await waiting.route('**/api/status',r=>r.fulfill({json:{phase:'ready',operation:'old-operation',ssd_connected:false,drive:{phase:'live'},message:'old'}}));
 await waiting.goto(origin+'/?waiting=1&operation=new-operation');
 await waiting.waitForTimeout(200);assert.ok(waiting.url().startsWith(origin));await waiting.close();
 assert.deepEqual(errors,[]);console.log('PASS: desktop/tablet layout, missing-SSD guard, delayed-navigation operation identity; no GPU-render claim.');console.log(folder);
}finally{await browser.close();server.close()}})().catch(e=>{console.error(e);process.exitCode=1});

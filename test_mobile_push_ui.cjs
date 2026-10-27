// Synthetic browser checks; these do not grant permissions or pair a real phone.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'mobile','app.js'),'utf8');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function screen({secure=true,installed=true,paired=true,permission='default',api=true,workerFailure=false,workerPending=false}={}){
 const elements=new Map(),calls=[];
 function element(id){if(!elements.has(id))elements.set(id,{textContent:'',hidden:false,disabled:false,dataset:{},classList:{toggle(){}},setAttribute(){},replaceChildren(){},children:[]});return elements.get(id);}
 const state={connected:false,session:null,event:{},stage:'ready',public_key:'unused-test-key',push_enabled:false};
 const sub={toJSON:()=>({endpoint:'synthetic-test-only'})};
 const registration={pushManager:{getSubscription:async()=>sub,subscribe:async()=>{throw Error('An existing test subscription should be reused');}}};
 const notifications={get permission(){return permission},requestPermission:()=>{calls.push('permission');permission='granted';return Promise.resolve(permission)}};
 const navigator={userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)',standalone:installed,serviceWorker:{
  register:()=>workerFailure?Promise.reject(Error('synthetic worker failure')):Promise.resolve(registration),
  ready:workerPending?new Promise(()=>{}):Promise.resolve(registration)
 }};
 const window=api?{Notification:notifications,PushManager:function(){}}:{};
 const context={window,navigator,isSecureContext:secure,Notification:api?notifications:undefined,matchMedia:()=>({matches:installed}),
  document:{getElementById:element,addEventListener(){},visibilityState:'visible'},
  location:{hostname:'192.168.0.30',origin:(secure?'https://192.168.0.30:8777':'http://192.168.0.30:8776'),hash:'',pathname:'/m/',search:''},
  crypto:{randomUUID:()=> 'synthetic-id'},history:{replaceState(){}},URLSearchParams,AbortController,
  setTimeout:(callback,ms)=>ms===10000?setTimeout(callback,5):0,clearTimeout,
  fetch:async(url,options)=>{calls.push(url);const authorized=paired||!url.endsWith('/state');return {ok:authorized,status:authorized?200:401,json:async()=>authorized?(options?.method==='POST'?{subscribed:true}:state):{error:'연결 필요'}}}
 };
 vm.runInNewContext(source,context,{filename:'mobile/app.js'});await tick();await tick();
 return {elements,el:element,calls,click:()=>element('push-enable').onclick()};
}
test('Safari tab explains Home Screen before missing PushManager',async()=>{
 const ui=await screen({installed:false,api:false});
 assert.equal(ui.el('push-enable').disabled,true);
 assert.match(ui.el('push-status').textContent,/브라우저 탭.*홈 화면/);
 assert.match(ui.el('push-check-installed').textContent,/필요/);
 assert.ok(!ui.calls.includes('permission'));
});
test('HTTP provides the HTTPS link instead of requesting permission',async()=>{
 const ui=await screen({secure:false});assert.equal(ui.el('push-enable').disabled,true);
 assert.match(ui.el('push-status').textContent,/HTTP/);
 assert.equal(ui.el('push-secure-link').hidden,false);
 assert.equal(ui.el('push-secure-link').href,'https://192.168.0.30:8777/m/');
 await ui.click();assert.ok(!ui.calls.includes('permission'));
});
test('A Home Screen app without its own pairing explains reconnecting',async()=>{
 const ui=await screen({paired:false});assert.equal(ui.el('push-enable').disabled,true);
 assert.match(ui.el('push-status').textContent,/이 홈 화면 앱.*PC 연결/);
 assert.match(ui.el('push-check-paired').textContent,/필요/);
});
test('An eligible tap requests permission and registers an existing subscription',async()=>{
 const ui=await screen();assert.equal(ui.el('push-enable').disabled,false);
 assert.ok(!ui.calls.includes('permission'));ui.calls.length=0;
 const result=ui.click();assert.equal(ui.calls[0],'permission');await result;
 assert.ok(ui.calls.includes('/m/api/subscribe'));
 assert.equal(ui.el('push-test').disabled,false);
 assert.equal(ui.el('push-enable').textContent,'시스템 알림 연결됨');
});
test('Denied permission explains the iPhone setting instead of another prompt',async()=>{
 const ui=await screen({permission:'denied'});assert.equal(ui.el('push-enable').disabled,true);
 assert.match(ui.el('push-status').textContent,/설정 → 알림 → 홍익 AI/);
 await ui.click();assert.ok(!ui.calls.includes('permission'));
});
test('Worker registration failure is visible and does not leave the button busy',async()=>{
 const ui=await screen({workerFailure:true});assert.match(ui.el('push-status').textContent,/연결 준비에 실패/);
 await ui.click();assert.equal(ui.el('push-enable').disabled,false);
 assert.equal(ui.el('push-test').disabled,true);
});
test('A worker that never becomes ready reports a bounded failure',async()=>{
 const ui=await screen({workerPending:true});await ui.click();
 assert.match(ui.el('toast').textContent,/준비가 지연/);
 assert.equal(ui.el('push-enable').disabled,false);
 assert.equal(ui.el('push-test').disabled,true);
});

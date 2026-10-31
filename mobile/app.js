(()=>{'use strict';
const $=id=>document.getElementById(id);let state=null,paired=false,busy=false,opened=false,selection=null,openedSession=null,seen=null,exposed=null,presented=null,audio=null,toastTimer=null,beeper=null,optionsReady=false,explanationDone=false;
const id=()=>crypto.randomUUID?.()||`${Date.now()}-${Math.random().toString(36).slice(2)}`;
const standalone=()=>matchMedia('(display-mode: standalone)').matches||navigator.standalone===true;
let pushBusy=false,workerRegistration=null,workerError='';
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,5000)}
async function request(path,body){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),7000);try{const r=await fetch('/m/api/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal:controller.signal,cache:'no-store'});const value=await r.json();if(!r.ok){const e=Error(value.error||'연결을 확인해 주세요.');e.status=r.status;throw e}return value}finally{clearTimeout(timer)}}
function stopAudio(){if(audio){audio.pause();audio.removeAttribute('src');audio=null}$('read').textContent='설명 다시 듣기'}
function read(){stopAudio();const voice=state?.event?.narration;if(!voice?.cached||!voice.url)return;audio=new Audio(voice.url);audio.onended=()=>{stopAudio();revealChoices()};audio.play().then(()=>$('read').textContent='읽기 멈춤').catch(()=>{});}
async function revealChoices(){explanationDone=true;if(busy||!opened||!state?.event.active||state.event.pending)return;busy=true;render();try{await send('study_options',{options_visible:true});optionsReady=true}catch(e){toast(e.message)}finally{busy=false;render()}}
function armSound(){try{const C=window.AudioContext||window.webkitAudioContext;if(C&&!beeper)beeper=new C();beeper?.resume()}catch{}}
function ping(){try{if(!beeper||beeper.state!=='running')return;const o=beeper.createOscillator(),g=beeper.createGain();o.frequency.value=660;g.gain.setValueAtTime(.035,beeper.currentTime);g.gain.exponentialRampToValueAtTime(.001,beeper.currentTime+.18);o.connect(g).connect(beeper.destination);o.start();o.stop(beeper.currentTime+.2)}catch{}}
async function send(action,details={}){if(!state?.connected)throw Error('PC와 연결된 뒤 다시 선택해 주세요.');return request('command',{action,session_id:state.session,navigation_id:state.navigation_id,request_id:id(),client_event:{source:'hongik_mobile',client_ms:performance.now(),options_visible:opened,phase:selection?'confirm':'options',event_visible:state.event.active,...details}})}
function pushSetup(){
 const ios=/iPad|iPhone|iPod/.test(navigator.userAgent)||(/Macintosh/.test(navigator.userAgent)&&navigator.maxTouchPoints>1);
 const installed=!ios||standalone(),supported='serviceWorker'in navigator&&'PushManager'in window&&'Notification'in window;
 const permission='Notification'in window?Notification.permission:'unavailable';
 const checks={secure:isSecureContext,installed,paired:paired&&!!state,permission:permission==='granted',requiresHome:ios};
 // iOS browser tabs may hide PushManager: explain Home Screen installation first.
 if(!checks.secure)return {checks,reason:'secure',message:'지금은 일반 HTTP 주소예요. 아래 보안 주소를 Safari로 열고, 그 주소로 홈 화면에 추가해 주세요.'};
 if(!installed)return {checks,reason:'install',message:'지금은 브라우저 탭으로 열려 있어요. Safari의 공유 → 홈 화면에 추가 후, 홈 화면의 홍익 AI 아이콘으로 다시 열어 주세요.'};
 if(!supported)return {checks,reason:'unsupported',message:'이 화면에서 시스템 알림 기능을 사용할 수 없어요. 아이폰은 iOS 16.4 이상에서 보안 주소로 추가한 홈 화면 앱이 필요해요.'};
 if(!checks.paired)return {checks,reason:'pair',message:'이 홈 화면 앱에서는 PC 연결이 아직 확인되지 않았어요. 설정을 닫고 PC의 현재 QR 또는 연결 코드로 연결해 주세요. Safari 탭의 연결과 다를 수 있어요.'};
 if(permission==='denied')return {checks,reason:'denied',message:'이 앱의 알림이 차단돼 있어요. 아이폰 설정 → 알림 → 홍익 AI에서 알림 허용을 켠 뒤 이 앱을 다시 열어 주세요.'};
 return {checks,reason:'ready',message:workerError||'준비됐어요. 아래 버튼을 누르고 아이폰의 알림 허용을 선택해 주세요.'};
}
function updatePush(){
 const setup=pushSetup(),enabled=!!state?.push_enabled,button=$('push-enable');
 button.disabled=pushBusy||setup.reason!=='ready'||enabled;
 button.textContent=pushBusy?'알림 연결 중…':enabled?'시스템 알림 연결됨':'아이폰 시스템 알림 켜기';
 button.setAttribute('aria-describedby','push-status');
 $('push-test').disabled=pushBusy||!enabled;$('push-disable').disabled=pushBusy||!enabled;
 const message=enabled?'시스템 알림이 등록되어 있어요. ‘알림 받아보기’로 실제 수신을 확인해 주세요.':setup.message;
 if($('push-status').textContent!==message)$('push-status').textContent=message;
 for(const [key,label] of Object.entries({secure:'HTTPS 보안 주소',installed:setup.checks.requiresHome?'아이폰 홈 화면 앱으로 실행':'브라우저 실행 환경',paired:'이 화면에서 PC 연결',permission:'알림 권한 허용'})){
  const item=$('push-check-'+key);item.textContent=(setup.checks[key]?'✓ 완료 · ':'○ 필요 · ')+label;item.dataset.ready=String(setup.checks[key]);
 }
 $('push-address').textContent=location.origin;
 $('push-secure-link').hidden=setup.reason!=='secure';$('push-secure-link').href=`https://${location.hostname}:8777/m/`;
}
function prepareWorker(){
 if(!workerRegistration){workerError='';workerRegistration=navigator.serviceWorker.register('/m/sw.js',{scope:'/m/'}).catch(error=>{
  workerRegistration=null;workerError='알림 연결 준비에 실패했어요. PC 연결을 확인한 뒤 앱을 다시 열거나 알림 켜기를 다시 눌러 주세요.';updatePush();throw error;
 });}
 return workerRegistration;
}
async function readyWorker(){
 let timer;try{return await Promise.race([prepareWorker().then(()=>navigator.serviceWorker.ready),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('알림 준비가 지연되고 있어요. PC 연결을 확인하고 앱을 다시 열어 주세요.')),10000)})]);}finally{clearTimeout(timer)}
}
function render(){
 $('pair').hidden=paired;$('dashboard').hidden=!paired;updatePush();if(!state||!paired)return;
 const s=state,e=s.event||{},out=e.outcome||{},resolving=out.phase&&out.phase!=='idle';
 $('destination').textContent=s.destination||'내 주행';$('connection').textContent=s.connected?'PC와 연결됨':'PC 연결을 기다리는 중';$('dot').classList.toggle('online',!!s.connected);$('speed').textContent=s.connected?Math.round(s.speed_kph):'—';$('remaining').textContent=s.remaining_m==null?'—':s.remaining_m>=1000?(s.remaining_m/1000).toFixed(1)+' km':Math.round(s.remaining_m)+' m';$('gap').textContent=s.gap_m==null?'':`앞차 간격 약 ${s.gap_m} m`;$('beam').hidden=!s.high_beam_on;
 $('status-label').textContent=s.completed?'차량이 정차했습니다':resolving?'선택한 행동의 결과 확인 중':s.stage==='running'?'주행 중':'출발 대기';$('status-copy').textContent=out.summary||e.feedback||(s.stage==='running'?'상황이 생기면 홍익 AI가 알려드릴게요.':'PC에서 주행을 시작해 주세요.');
 const unread=!!s.connected&&!!e.active&&seen!==s.session&&!resolving;$('banner').hidden=!unread;$('launch').classList.toggle('unread',unread);$('launch-copy').textContent=s.completed?'행동 결과 보기':resolving?'행동 결과 확인 중':unread?'새 상황 · 눌러서 확인':'상황 살펴보기';
 if(unread&&exposed!==s.session&&document.visibilityState==='visible'){exposed=s.session;ping();navigator.vibrate?.([50]);}
 if(unread&&presented!==s.session&&document.visibilityState==='visible'){presented=s.session;send('study_presented').catch(()=>{});}
 if(!opened)return;
 $('title').textContent=s.completed?'차량이 정차했습니다':e.title||'현재 주행';$('description').textContent=out.phase==='complete'?out.message:e.description||'차량에 연결되면 상황을 확인할 수 있어요.';$('live-detail').textContent=e.live_detail||'';$('feedback').textContent=out.summary||e.feedback||'';$('read').hidden=!!resolving||!e.narration?.cached;
 $('caption').textContent=resolving?'선택한 행동의 결과':'현재 상황과 차량의 판단';$('choices').hidden=!e.active||!!selection||!!resolving||Boolean(e.staged_options&&!explanationDone);$('options-open').hidden=!e.staged_options||explanationDone||!!resolving;$('options-open').disabled=busy;$('direct-done').hidden=!e.direct_pending;$('direct-done').textContent=e.direct_label||'대화 완료';$('direct-done').disabled=busy;$('confirm').hidden=!selection||!!resolving;
 for(const b of $('options').children)b.disabled=busy||!s.connected||!optionsReady||Boolean((e.options||[]).find(o=>o.action===b.dataset.action)?.disabled);
 $('execute').disabled=busy||!s.connected||Boolean((e.options||[]).find(o=>o.action===selection?.action)?.disabled);$('cancel').disabled=busy;
}
async function poll(){try{const next=await request('state');if(state?.session!==next.session){stopAudio();opened=false;optionsReady=false;selection=null;openedSession=null;$('dialog').hidden=true;seen=null;presented=null;exposed=null;}state=next;paired=true;render();if(opened&&next.event.active&&!next.event.pending&&!optionsReady&&!busy&&(!next.event.staged_options||explanationDone)){busy=true;try{await send('study_options',{options_visible:true});optionsReady=true}catch(e){toast(e.message)}finally{busy=false;render()}}}catch(e){if(e.status===401){paired=false;stopAudio();opened=false;$('dialog').hidden=true;}else if(state)state={...state,connected:false};render();}finally{setTimeout(poll,500)}}
async function pair(code){$('pair-error').textContent='';try{await request('pair',{code});paired=true;armSound();toast('PC와 연결했어요. 주행을 시작하면 함께 알려드릴게요.');}catch(e){$('pair-error').textContent=e.message}}
$('pair-form').onsubmit=async e=>{e.preventDefault();armSound();await pair($('code').value)};
async function open(){if(!paired||busy)return;armSound();opened=true;optionsReady=false;explanationDone=!state?.event.staged_options;openedSession=state?.session;seen=state?.session;selection=null;$('dialog').hidden=false;$('options').replaceChildren();for(const option of state?.event?.options||[]){const button=document.createElement('button'),strong=document.createElement('strong'),small=document.createElement('small');strong.textContent=option.label;small.textContent=option.disabled_reason||option.detail;button.dataset.action=option.action;button.append(strong,small);button.onclick=()=>choose(option);$('options').append(button);}busy=true;render();read();try{await send('study_open',{options_visible:!state.event.staged_options});optionsReady=state.event.active&&!state.event.staged_options}catch(e){toast(e.message)}finally{busy=false;render();if(explanationDone&&state?.event.staged_options)revealChoices();$('close').focus();}}
async function close(){if(!opened)return;stopAudio();opened=false;selection=null;$('dialog').hidden=true;if(state?.session===openedSession)send('study_close').catch(()=>{});render()}
async function choose(option){if(busy||state?.event?.pending||option.disabled||(state?.event?.options||[]).find(o=>o.action===option.action)?.disabled)return;busy=true;stopAudio();render();try{await send('study_choice',{choice:option.action});selection=option;$('confirm-title').textContent=option.label+' 요청을 실행할까요?';$('confirm-copy').textContent=option.detail;}catch(e){toast(e.message)}finally{busy=false;render()}}
$('execute').onclick=async()=>{if(busy||!selection||(state?.event?.options||[]).find(o=>o.action===selection.action)?.disabled)return;busy=true;render();const action=selection.action;try{await send(action,{choice:action});selection=null;toast('요청을 전달했어요. PC 주행 화면에서 결과를 확인해 주세요.')}catch(e){toast(e.message)}finally{busy=false;render()}};
$('cancel').onclick=async()=>{if(busy)return;busy=true;try{await send('study_cancel',{choice:selection?.action});selection=null}catch(e){toast(e.message)}finally{busy=false;render()}};
$('direct-done').onclick=async()=>{if(busy||!state?.event.direct_pending)return;busy=true;render();try{await send('study_direct_done')}catch(e){toast(e.message)}finally{busy=false;render()}};$('options-open').onclick=revealChoices;
$('launch').onclick=open;$('banner').onclick=open;$('close').onclick=close;$('read').onclick=()=>audio?stopAudio():read();$('settings').onclick=()=>{updatePush();$('preferences').hidden=false};$('pref-close').onclick=()=>$('preferences').hidden=true;
$('push-enable').onclick=async()=>{
 const setup=pushSetup();if(pushBusy||setup.reason!=='ready'){toast(setup.message);return;}
 pushBusy=true;updatePush();try{
  // Request permission directly from the tap, before waiting for worker/network work.
  const permission=await Notification.requestPermission();if(permission!=='granted')throw Error('아이폰 알림을 허용한 뒤 다시 시도해 주세요.');
  const reg=await readyWorker();let sub=await reg.pushManager.getSubscription();
  if(!sub){const key=state.public_key;const data=Uint8Array.from(atob(key.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:data})}
  await request('subscribe',{subscription:sub.toJSON()});state={...state,push_enabled:true};toast('시스템 알림을 연결했어요. 알림 받아보기로 확인해 주세요.');
 }catch(e){toast(e.message)}finally{pushBusy=false;updatePush()}
};
$('push-test').onclick=async()=>{try{const r=await request('push-test',{});toast(r.sent?'알림 제공자에게 전송했어요. 실제 수신도 확인해 주세요.':'전송 상태를 확인하지 못했어요.')}catch(e){toast(e.message)}};
$('push-disable').onclick=async()=>{try{await request('unsubscribe',{});const reg=await navigator.serviceWorker.ready;const sub=await reg.pushManager.getSubscription();await sub?.unsubscribe();toast('시스템 알림을 껐어요.')}catch(e){toast(e.message)}};
$('arm').onclick=()=>{armSound();$('arm').textContent='앱 안의 알림 소리 준비됨';toast('이 화면을 열어둔 동안 상황 알림 소리를 준비했어요.')};
document.addEventListener('visibilitychange',()=>{if(document.hidden){stopAudio();if(opened)close();}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){close();$('preferences').hidden=true}});
if(isSecureContext&&'serviceWorker'in navigator)prepareWorker().catch(()=>{});
const secureLink=$('https-open');secureLink.href=`https://${location.hostname}:8777/m/`;secureLink.textContent=secureLink.href;
const code=new URLSearchParams(location.hash.slice(1)).get('pair');if(code){history.replaceState(null,'',location.pathname+location.search);pair(code).then(poll)}else poll();
})();

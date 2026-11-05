/* Click-only Hongik: invitation -> explanation and choices -> confirm -> feedback.
 * Authentic cached Sohee only; no microphone, wake-word or voice inference.
 */
(()=>{
'use strict';
const root=document.createElement('div');root.id='research-ui';root.hidden=true;
root.innerHTML=`<button id="research-launch" type="button" aria-label="홍익 AI 상황 살펴보기" aria-expanded="false" aria-controls="research-dialog">
 <span class="hongik-orb" aria-hidden="true"></span><span><strong>홍익 AI</strong><small id="research-badge">상황 살펴보기</small></span><i id="research-unread" hidden></i></button>
 <section id="research-dialog" hidden role="dialog" aria-modal="false" aria-labelledby="research-title">
 <header><span class="hongik-panel-name"><span class="hongik-orb" aria-hidden="true"></span>홍익 AI</span><button type="button" id="research-close" aria-label="홍익 AI 닫기">×</button></header>
 <div class="research-dialog-content"><p id="research-caption">현재 상황</p><h2 id="research-title"></h2>
 <p id="research-description"></p><p id="research-live-detail"></p>
 <div class="research-voice"><button id="research-read" type="button">설명 다시 듣기</button><small id="research-voice-status" role="status">Sohee</small></div>
 <div id="research-feedback" role="status" hidden></div>
 <button id="research-direct-done" type="button" class="research-primary" hidden>대응 완료</button>
 <button id="research-options-open" type="button" class="research-primary" hidden>대응 방법 보기</button>
 <p id="research-options-label">어떻게 할까요?</p><div id="research-options" role="group" aria-labelledby="research-options-label"></div>
 <div id="research-confirmation" hidden><p id="research-confirm-copy"></p><div class="research-confirm-actions">
 <button id="research-back" type="button">선택 취소</button><button id="research-execute" type="button" class="research-primary">실행</button></div></div>
 </div></section>
 <section id="research-ending" hidden role="status" aria-live="polite"><small>홍익 AI</small><h2>주변 상황을 확인했어요</h2><p id="research-ending-message"></p><p id="research-ending-summary"></p><button id="research-ending-home" type="button">확인</button></section>`;
document.body.appendChild(root);
const $=id=>document.getElementById(id),launch=$('research-launch'),dialog=$('research-dialog');
let current=null,event=null,session=null,seen=null,unread=false,phase='options',selected=null;
let busy=false,dialogReady=false,optionsReady=false,opening=false,generation=0,lastFocus=null,signature=null;
let sendTail=Promise.resolve(),localFeedback='',feedbackBaseline='';
const content=$('research-dialog').querySelector('.research-dialog-content');
const left=document.createElement('div'),right=document.createElement('div');left.className='midterm-explanation';right.className='midterm-choices';
left.append($('research-caption'),$('research-title'));
const now=document.createElement('section');now.className='midterm-info-card';now.innerHTML='<h3>지금 상황</h3>';now.append($('research-description'));left.append(now);
const vehicle=document.createElement('section');vehicle.className='midterm-info-card';vehicle.innerHTML='<h3>차가 하고 있는 일</h3><p id="research-vehicle-action"></p>';left.append(vehicle,$('research-live-detail'),content.querySelector('.research-voice'));
left.append($('research-feedback'));left.insertAdjacentHTML('beforeend','<section id="research-inspect-view" hidden><small>현재 차량 주변 위치</small><canvas id="research-surroundings" width="360" height="180" aria-label="실제 CARLA 주변 차량 위치"></canvas></section><img id="research-result-frame" alt="실제 주행 결과 화면" hidden>');
right.append($('research-direct-done'),$('research-options-open'),$('research-options-label'),$('research-options'));
right.insertAdjacentHTML('beforeend','<button id="research-maintain" type="button">그냥 둘게요</button>');right.append($('research-confirmation'));
right.insertAdjacentHTML('beforeend','<div id="research-countdown" hidden><strong id="research-countdown-number">3</strong><p>초 뒤 실행합니다</p><button id="research-pending-cancel" type="button">요청 취소</button></div><button id="research-repeat" type="button" hidden>한 번 더</button>');
content.replaceChildren(left,right);
root.insertAdjacentHTML('beforeend','<button id="research-fixed-help" class="midterm-fixed" type="button">도움 요청</button><button id="research-fixed-stop" class="midterm-fixed" type="button">정차 요청</button>');
const passive=document.createElement('div');passive.id='midterm-passive';passive.innerHTML='<small>차량 상태</small><strong id="midterm-passive-title"></strong><p id="midterm-passive-body"></p>';$('route-card').append(passive);
const endClose=document.createElement('button');endClose.id='research-ending-close';endClose.type='button';endClose.textContent='×';endClose.setAttribute('aria-label','결과 닫기');$('research-ending').append(endClose);
const previous=window.CockpitUpdate;
let player=null,speechTurn=0;
let explanationFinished=false,endingDismissed=false,viewAcknowledged=false,latestData=null;
let voiceEnabled=true;try{
 voiceEnabled=localStorage.getItem('nurec-sohee-enabled')!=='false'&&localStorage.getItem('carla-navigation-voice')!=='off';
 const query=new URLSearchParams(location.search);if(query.has('voice')){
  voiceEnabled=query.get('voice')!=='0';localStorage.setItem('nurec-sohee-enabled',String(voiceEnabled));
 }
}catch{}
addEventListener('hongik-voice-enabled',e=>{voiceEnabled=Boolean(e.detail);try{localStorage.setItem('nurec-sohee-enabled',String(voiceEnabled))}catch{}if(!voiceEnabled)stopSpeech()});
const voiceClient=crypto.randomUUID();
const voiceChannel=typeof BroadcastChannel==='function'?new BroadcastChannel('nurec-hongik-sohee'):null;
if(voiceChannel)voiceChannel.onmessage=message=>{if(message.data?.claim!==voiceClient)stopSpeech()};
function stopSpeech(){
 speechTurn++;if(player){player.pause();player.removeAttribute('src');player.load();player.remove?.();player=null}
 window.passengerNarration?.setDuck?.(1);
 $('research-read').textContent='설명 다시 듣기';$('research-voice-status').textContent=voiceEnabled?'Sohee':'음성 꺼짐';
}
function readExplanation(){
 stopSpeech();if(!voiceEnabled)return;
 const voice=event?.narration;
 if(!voice?.cached||!/^\/api\/narration\/audio\/(blockade|congestion|night|fog|normal|complete|yield|city_yield|city_carpool|city_rattle|city_fog|city_cargo)\.wav$/.test(voice.url||'')){
  $('research-voice-status').textContent='Sohee 음성을 준비하지 못했어요.';return;
 }
 const turn=speechTurn;voiceChannel?.postMessage({claim:voiceClient});
 try{
  player=new Audio(voice.url);player.volume=1;player.id='research-sohee-audio';player.hidden=true;root.appendChild(player);
  player.onplaying=()=>{if(turn===speechTurn){window.passengerNarration?.setDuck?.(.16);$('research-read').textContent='읽기 멈춤';$('research-voice-status').textContent='설명 중'}};
  player.onended=()=>{if(turn===speechTurn){stopSpeech();if(event?.staged_options&&phase==='explanation'){explanationFinished=true;revealOptions()}}};
  player.onerror=()=>{if(turn===speechTurn){stopSpeech();$('research-voice-status').textContent='음성을 재생하지 못했어요. 다시 눌러 주세요.'}};
  const playback=player.play();playback?.catch(()=>{if(turn===speechTurn){stopSpeech();$('research-voice-status').textContent='다시 듣기를 눌러 주세요.'}});
 }catch{stopSpeech();$('research-voice-status').textContent='음성을 재생하지 못했어요.'}
}

// Order open/choice/cancel/close acknowledgements; execute remains explicit.
function post(action,details={}){
 const snapshot=session,nav=current;
 if(!snapshot||!nav)return Promise.reject(Error('주행 연결을 확인해 주세요.'));
 const body={session_id:snapshot.session_id,navigation_id:nav.id,action,request_id:crypto.randomUUID(),
  client_event:{phase,client_ms:performance.now(),event_visible:event?.active===true,
   source:'hongik_click_panel',...details}};
 const task=sendTail.catch(()=>{}).then(async()=>{
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),4000);
  try{
   const response=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:controller.signal});
   const result=await response.json();if(!response.ok)throw Error(result.error||'요청을 전달하지 못했습니다.');
   return result;
  }finally{clearTimeout(timer)}
 });sendTail=task;return task;
}
function record(action,details={}){post(action,details).catch(()=>{})}
function feedback(text){$('research-feedback').textContent=text;$('research-feedback').hidden=!text}
function showError(error){localFeedback=error.message||'요청을 확인하지 못했습니다.';feedbackBaseline=event?.feedback||'';render()}
function isCurrent(token){return token===generation&&!dialog.hidden}
function render(){
 if(!event)return;
 const outcome=event.outcome||{},resolving=outcome.phase&&outcome.phase!=='idle';
 if(outcome.phase==='complete'&&!endingDismissed)dialog.hidden=true;
 if(resolving){phase='result';selected=null;optionsReady=false}
 $('research-ending').hidden=outcome.phase!=='complete'||endingDismissed;
 $('research-ending-message').textContent=outcome.message||'';
 $('research-ending-summary').textContent=outcome.summary||'';
 const stages={applying:'요청한 대응을 진행하고 있어요',observing:'주변의 반응을 확인하고 있어요',stopping:'서서히 정차하고 있어요',complete:'주변 확인 완료'};
 $('research-title').textContent=event.title;
 $('research-description').textContent=event.situation||event.description;
 $('research-vehicle-action').textContent=event.vehicle_action||event.description;
 $('research-live-detail').textContent=event.live_detail||'';
 $('research-caption').textContent=stages[outcome.phase]||(event.active?'현재 상황과 차량의 판단':'현재 주행');
 $('research-badge').textContent=resolving?(outcome.phase==='complete'?'주변 확인 완료':'주변 반응 확인 중'):unread?'새 상황 · 눌러서 확인':'상황 살펴보기';
 $('research-read').parentElement&&( $('research-read').parentElement.hidden=Boolean(resolving));
 $('research-unread').hidden=!unread;
 launch.classList.toggle('has-update',unread&&Boolean(event.active)&&dialog.hidden);
 const showOptions=Boolean(event.active)&&phase==='options';
 $('research-options-open').hidden=!event.staged_options||phase!=='explanation'||!event.active||Boolean(event.pending);
 $('research-options-open').disabled=busy;
 $('research-direct-done').hidden=!event.direct_pending;
 $('research-direct-done').textContent=event.direct_label||'대응 완료';
 $('research-direct-done').disabled=busy;
 $('research-options').hidden=!showOptions;
 $('research-options-label').hidden=!showOptions;
 $('research-confirmation').hidden=phase!=='confirm';
 $('research-execute').disabled=busy||Boolean(event.pending)||(!event.active&&!selected?.fixed)||Boolean((event.options||[]).find(o=>o.action===selected?.action)?.disabled);
 $('research-back').disabled=busy;
 if(localFeedback&&event.feedback!==feedbackBaseline){localFeedback='';feedbackBaseline=event.feedback||''}
 feedback(busy?'요청을 확인하고 있어요.':outcome.summary||localFeedback||event.feedback||'');
 const nextSignature=JSON.stringify(event.options||[]);
 if(signature!==nextSignature){
  signature=nextSignature;$('research-options').replaceChildren();
  for(const option of event.options||[]){
   if(option.action==='study_maintain')continue;
   const button=document.createElement('button');button.type='button';button.className='research-option';button.dataset.action=option.action;
   const label=document.createElement('strong'),detail=document.createElement('small');
   label.textContent=option.label;detail.textContent=option.disabled_reason||option.detail;button.append(label,detail);
   button.dataset.unavailable=option.disabled?'true':'false';
   button.onclick=()=>choose(option);$('research-options').appendChild(button);
  }
 }
 $('research-maintain').hidden=!showOptions;
 const study=event.study||{};const queued=study.phase==='queued';$('research-countdown').hidden=!queued;$('research-countdown-number').textContent=Math.max(1,Math.ceil(study.countdown_s||0));$('research-repeat').hidden=!study.repeatable;
 const inspecting=study.action==='inspect'&&['applying','observing'].includes(study.phase)&&!dialog.hidden;
 $('research-inspect-view').hidden=!inspecting;if(inspecting){drawSurroundings();if(!viewAcknowledged){viewAcknowledged=true;post('study_view_opened').catch(()=>{viewAcknowledged=false})}}
 $('research-result-frame').hidden=inspecting||!['observing','complete'].includes(study.phase)||dialog.hidden;
 for(const button of $('research-options').children)button.disabled=button.dataset.unavailable==='true'||busy||!optionsReady||Boolean(event.pending)||!event.active;
}
async function prepareOptions(){
 if(opening||busy||!dialogReady||optionsReady||dialog.hidden||!event?.active||event.pending||phase==='explanation')return;
 const token=generation;opening=true;busy=true;render();
 try{await post('study_options',{options_visible:true});if(isCurrent(token))optionsReady=true}
 catch(error){if(isCurrent(token))showError(error)}
 finally{if(isCurrent(token)){opening=false;busy=false;render()}}
}
async function open(){
 if(!session||!event)return;
 const token=++generation;lastFocus=document.activeElement;phase=event.staged_options?'explanation':'options';selected=null;explanationFinished=false;
 dialogReady=false;optionsReady=false;opening=true;busy=true;localFeedback='';feedbackBaseline=event.feedback||'';
 dialog.hidden=false;unread=false;launch.setAttribute('aria-expanded','true');render();$('research-close').focus();
 if(!event.pending)readExplanation();
 try{
  const exposed=Boolean(event.active)&&!event.pending&&!event.staged_options;
  await post('study_open',{options_visible:exposed});
  if(isCurrent(token)){dialogReady=true;optionsReady=exposed}
 }catch(error){if(isCurrent(token))showError(error)}
 finally{if(isCurrent(token)){opening=false;busy=false;render();if(explanationFinished)revealOptions();else prepareOptions()}}
}
async function revealOptions(){
 if(!event?.staged_options||phase!=='explanation'||dialog.hidden)return;
 if(!dialogReady||busy){explanationFinished=true;return}
 stopSpeech();phase='options';render();await prepareOptions();
}
function close(){
 if(dialog.hidden)return;
 stopSpeech();
 if(event?.study?.cancellable)record('study_cancel_pending',{reason:'explicit close'});
 record('study_close',{choice:selected?.action||'',phase});generation++;
 dialog.hidden=true;phase='options';selected=null;busy=false;opening=false;dialogReady=false;optionsReady=false;
 launch.setAttribute('aria-expanded','false');lastFocus?.focus();render();
}
async function choose(option){
 if(busy||!optionsReady||!event?.active||event.pending||option.disabled)return;
 stopSpeech();
 const token=generation;busy=true;render();
 try{
  await post('study_choice',{choice:option.action});if(!isCurrent(token))return;
  selected=option;phase='confirm';$('research-confirm-copy').textContent=option.label+' 요청을 실행할까요? '+option.detail;
 }catch(error){if(isCurrent(token))showError(error)}
 finally{if(isCurrent(token)){busy=false;render();if(phase==='confirm')$('research-execute').focus()}}
}
async function cancel(){
 if(busy)return;const token=generation;busy=true;render();
 try{await post('study_cancel',{choice:selected?.action});if(isCurrent(token)){phase='options';selected=null}}
 catch(error){if(isCurrent(token))showError(error)}
 finally{if(isCurrent(token)){busy=false;render()}}
}
async function execute(){
 if(!selected||busy||event?.pending||(!event?.active&&!selected.fixed)||(event.options||[]).find(o=>o.action===selected.action)?.disabled)return;
 const token=generation,action=selected.action,expected=session.session_id;
 busy=true;render();
 try{
  const queued=await post(action,{choice:action});let result=null;
  for(let i=0;i<40;i++){
   if(!isCurrent(token)||session?.session_id!==expected)return;
   result=await(await fetch(`/api/reply?session=${encodeURIComponent(queued.session_id)}&id=${encodeURIComponent(queued.command_id)}`,{cache:'no-store'})).json();
   if(result.accepted===false)throw Error(result.message||'요청이 실행되지 않았습니다.');
   if(result.accepted===true)break;
   await new Promise(resolve=>setTimeout(resolve,100));
  }
  if(!isCurrent(token))return;
  if(result?.accepted!==true)throw Error('차량 응답을 확인하지 못했습니다. 현재 상태를 확인해 주세요.');
  phase='result';selected=null;optionsReady=false;localFeedback=result.message||'';feedbackBaseline=event.feedback||'';
 }catch(error){if(isCurrent(token)){phase='options';selected=null;showError(error)}}
 finally{if(isCurrent(token)){busy=false;render()}}
}
function fixedRequest(action,label){if(busy||!event||event.pending)return;selected={action,label,fixed:true};phase='confirm';dialogReady=true;optionsReady=false;dialog.hidden=false;endingDismissed=true;$('research-confirm-copy').textContent=label+'을 실행할까요? 실행 후에도 3초 안에 취소할 수 있어요.';render();}
$('research-fixed-help').onclick=()=>fixedRequest('study_fixed_help','도움 요청');$('research-fixed-stop').onclick=()=>fixedRequest('study_fixed_stop','정차 요청');
$('research-maintain').onclick=()=>choose((event?.options||[]).find(o=>o.action==='study_maintain'));
$('research-pending-cancel').onclick=async()=>{try{await post('study_cancel_pending');close();}catch(error){showError(error)}};
$('research-repeat').onclick=async()=>{try{await post('study_repeat');viewAcknowledged=false;}catch(error){showError(error)}};
$('research-ending-close').onclick=()=>{endingDismissed=true;dialog.hidden=true;render()};
function drawSurroundings(){const c=$('research-surroundings').getContext('2d');c.clearRect(0,0,360,180);c.fillStyle='#f3f6fa';c.fillRect(0,0,360,180);c.strokeStyle='#cbd3dd';c.lineWidth=1;c.setLineDash([7,9]);for(let x=75;x<360;x+=70){c.beginPath();c.moveTo(x,0);c.lineTo(x,180);c.stroke()}c.setLineDash([]);for(const a of latestData?.actors||[]){if(a.forward_m < -10||a.forward_m>60)continue;c.fillStyle=a.role==='lead'?'#3e6ae1':'#8c98a8';c.fillRect(173+a.right_m*16,140-a.forward_m*2.5,14,a.kind==='pedestrian'?8:24)}c.fillStyle='#252d38';c.fillRect(173,140,14,25);}
setInterval(()=>{if(!$('research-result-frame').hidden)$('research-result-frame').src='/frame.jpg?t='+Date.now()},600);
launch.onclick=()=>dialog.hidden?open():close();
$('research-close').onclick=close;$('research-back').onclick=cancel;$('research-execute').onclick=execute;
$('research-options-open').onclick=()=>{explanationFinished=true;revealOptions()};
$('research-direct-done').onclick=async()=>{if(busy||!event?.direct_pending)return;const token=generation;busy=true;render();try{await post('study_direct_done')}catch(error){if(isCurrent(token))showError(error)}finally{if(isCurrent(token)){busy=false;render()}}};
$('research-read').onclick=()=>player?stopSpeech():readExplanation();
$('research-ending-home').onclick=()=>{endingDismissed=true;dialog.hidden=true;launch.setAttribute('aria-expanded','false');render()};
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!dialog.hidden){e.preventDefault();close()}});
function notify(){
 if(event?.active&&seen!==current.id&&document.visibilityState==='visible'){
  seen=current.id;unread=dialog.hidden;
  record('study_presented',{alert_presented:true,phase:dialog.hidden?'button':'explanation_and_options'});
 }
 render();
}
document.addEventListener('visibilitychange',()=>{if(document.visibilityState!=='visible')stopSpeech();notify()});
window.addEventListener?.('pagehide',stopSpeech);
window.addEventListener?.('nurec-exit',stopSpeech);
window.CockpitUpdate=data=>{
 previous?.(data);
 const next=data.session?.navigation?.research_event;
 const live=Boolean(next&&data.connected&&['ready','running'].includes(data.session?.stage));
 root.hidden=!live;document.body.classList.toggle('research-driving',live);
 if(!live){stopSpeech();generation++;dialog.hidden=true;seen=null;session=null;current=null;event=null;busy=false;opening=false;dialogReady=false;optionsReady=false;return}
 if(session?.session_id!==data.session.session_id){
  endingDismissed=false;viewAcknowledged=false;
  stopSpeech();
  generation++;seen=null;unread=false;phase='options';selected=null;busy=false;opening=false;dialogReady=false;optionsReady=false;
  dialog.hidden=true;localFeedback='';feedbackBaseline='';signature=null;launch.setAttribute('aria-expanded','false');
 }
 session=data.session;current=session.navigation;event=next;latestData=data;launch.disabled=false;
 document.body.classList.add('midterm-study');launch.hidden=event.condition==='A';
 $('midterm-passive-title').textContent=data.nurec?.scenario?.completed?'차량이 정차했어요':data.passive?.title||event.title;$('midterm-passive-body').textContent=event.outcome?.summary||data.passive?.body||event.vehicle_action||event.description;
 if(event.study?.phase==='queued')viewAcknowledged=false;
 if(!event.active&&!selected?.fixed){unread=false;if(!event.staged_options||dialog.hidden)phase='options';selected=null;optionsReady=false}
 if(event.pending||event.outcome?.phase==='complete'){unread=false;stopSpeech()}
 notify();prepareOptions();
};
})();

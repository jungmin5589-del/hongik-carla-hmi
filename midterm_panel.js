/* Click-only Hongik: invitation -> explanation and choices -> confirm -> feedback.
 * Authentic cached Sohee only; no microphone, wake-word or voice inference.
 */
(()=>{
'use strict';
const root=document.createElement('div');root.id='research-ui';root.hidden=true;
root.innerHTML=`<button id="research-launch" type="button" aria-label="홍익이 상황 살펴보기" aria-expanded="false" aria-controls="research-dialog">
 <svg class="hongik-wave" viewBox="0 0 1440 60" preserveAspectRatio="none" aria-hidden="true" focusable="false">
 <defs><linearGradient id="hongik-wave-gradient"><stop offset="0" stop-color="var(--wave-a)"/><stop offset=".45" stop-color="var(--wave-b)"/><stop offset="1" stop-color="var(--wave-c)"/></linearGradient></defs>
 <path class="wave-back" d="M-160 44 C80 4 220 58 440 30 S820 7 1030 32 S1320 10 1600 30 L1600 80 L-160 80Z"/>
 <path class="wave-front" d="M-160 48 C60 58 220 18 440 40 S780 57 1010 30 S1300 53 1600 33 L1600 80 L-160 80Z"/>
 </svg><span class="wave-label"><strong>홍익이</strong><small id="research-badge">눌러서 상황·대응 보기</small></span><i id="research-unread" hidden></i></button>
 <section id="research-dialog" hidden role="dialog" aria-modal="false" aria-labelledby="research-title">
 <header><span class="hongik-panel-name"><span class="hongik-orb" aria-hidden="true"></span>홍익이</span><button type="button" id="research-close" aria-label="홍익이 닫기">×</button></header>
 <div class="research-dialog-content"><p id="research-caption">현재 상황</p><h2 id="research-title"></h2>
 <p id="research-description"></p><p id="research-live-detail"></p>
 <div class="research-voice"><button id="research-read" type="button">설명 다시 듣기</button><small id="research-voice-status" role="status"></small></div>
 <div id="research-feedback" role="status" hidden></div>
 <button id="research-direct-done" type="button" class="research-primary" hidden>대응 완료</button>
 <button id="research-options-open" type="button" class="research-primary" hidden>대응 방법 보기</button>
 <p id="research-options-label">어떻게 할까요?</p><div id="research-options" role="group" aria-labelledby="research-options-label"></div>
 <div id="research-confirmation" hidden><p id="research-confirm-copy"></p><div class="research-confirm-actions">
 <button id="research-back" type="button">선택 취소</button><button id="research-execute" type="button" class="research-primary">실행</button></div></div>
 </div></section>
 <section id="research-ending" hidden role="status" aria-live="polite"><small>홍익이</small><h2>주변 상황을 확인했어요</h2><p id="research-ending-message"></p><p id="research-ending-summary"></p><button id="research-ending-home" type="button">시나리오 선택으로</button></section>`;
document.body.appendChild(root);
const $=id=>document.getElementById(id),launch=$('research-launch'),dialog=$('research-dialog');
let current=null,event=null,session=null,seen=null,unread=false,phase='options',selected=null,linkLive=false;
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
right.insertAdjacentHTML('beforeend','<div id="research-countdown" hidden><p id="research-request-name"></p><strong id="research-countdown-number">3</strong><p>초 뒤 실행합니다</p><button id="research-pending-cancel" type="button">요청 취소</button></div><button id="research-repeat" type="button" hidden>한 번 더</button>');
content.replaceChildren(left,right);
root.insertAdjacentHTML('beforeend','<button id="research-fixed-help" class="midterm-fixed" type="button">도움 요청</button><button id="research-fixed-stop" class="midterm-fixed" type="button">정차 요청</button>');
const passive=document.createElement('div');passive.id='midterm-passive';passive.innerHTML='<small>차량 상태</small><strong id="midterm-passive-title"></strong><p id="midterm-passive-body"></p>';$('route-card').append(passive);
const endClose=document.createElement('button');endClose.id='research-ending-close';endClose.type='button';endClose.textContent='×';endClose.setAttribute('aria-label','결과 닫기');$('research-ending').append(endClose);
const replay=document.createElement('button');replay.id='research-replay';replay.type='button';replay.textContent='같은 상황 다시 확인';$('research-ending').append(replay);let replayBusy=false;
const returnHome=document.createElement('button');returnHome.id='research-return-home';returnHome.type='button';returnHome.textContent='시나리오 선택으로';returnHome.hidden=true;root.append(returnHome);
const notice=document.createElement('section');notice.id='research-notice';notice.hidden=true;notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');
notice.innerHTML='<span class="notice-accent" aria-hidden="true"></span><small>홍익이</small><p id="research-notice-copy" class="ko-subtitle"></p><button id="research-notice-more" type="button">자세히 보기 <span aria-hidden="true">›</span></button><button id="research-notice-close" type="button" aria-label="상황 알림 닫기">×</button>';
root.append(notice);let noticeTimer=null,noticeToken=0;
function hideNotice(){noticeToken++;clearTimeout(noticeTimer);notice.hidden=true}
async function showNotice(){
 const token=++noticeToken,sid=session?.session_id,profile=latestData?.nurec?.profile;
 if(!profile||!dialog.hidden||latestData?.experiment&&(!latestData.experiment.ai_enabled||latestData.experiment.practice))return;
 try{
  const lang=window.HongikLocale?.lang||'ko';const pack=await(await fetch('/api/research-voice?lang='+lang)).json();
  if(token!==noticeToken||sid!==session?.session_id||!event?.active||!dialog.hidden)return;
  const voice=pack.voices?.['alert_'+profile];
  $('research-notice-copy').textContent=voice?.text||event.situation||event.title;
  notice.hidden=false;clearTimeout(noticeTimer);noticeTimer=0;
  notice.dataset.audioState='requested';
  const played=await window.HongikFeedback?.say('alert_'+profile);
  if(token===noticeToken)notice.dataset.audioState=played?'playback-started':'not-started';
 }catch{if(token===noticeToken&&event?.active&&dialog.hidden){$('research-notice-copy').textContent=event.situation||event.title;notice.hidden=false;noticeTimer=0}}
}
$('research-notice-close').onclick=hideNotice;
$('research-notice-more').onclick=()=>{hideNotice();launch.click()};
const previous=window.CockpitUpdate;
let player=null,speechTurn=0;
let explanationTimer=null;
function scheduleChoices(){clearTimeout(explanationTimer);explanationTimer=setTimeout(()=>{if(!dialog.hidden&&phase==='explanation'){if(player&&!player.paused&&player.currentTime>0)return;explanationFinished=true;revealOptions()}},5000)}
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
 $('research-read').textContent='설명 다시 듣기';$('research-voice-status').textContent=voiceEnabled?'':'음성 꺼짐';
}
function readExplanation(){
 window.HongikFeedback?.stop();
 stopSpeech();if(!voiceEnabled)return;
 const voice=event?.narration;
 if(!voice?.cached||(!/^\/api\/(?:english-audio|chinese-audio)\/[a-z_]+\.wav$/.test(voice.url||'')&&!/^\/api\/narration\/audio\/(blockade|congestion|night|fog|normal|complete|yield|city_yield|city_carpool|city_rattle|city_fog|city_cargo)\.wav$/.test(voice.url||''))){
  $('research-voice-status').textContent='음성을 준비하지 못했어요.';return;
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
window.HongikStudyVoice={read:readExplanation};

// Order open/choice/cancel/close acknowledgements; execute remains explicit.
function post(action,details={}){
 const snapshot=session,nav=current;
 if(!linkLive||!snapshot||!nav)return Promise.reject(Error('주행 연결을 확인해 주세요.'));
 const body={session_id:snapshot.session_id,navigation_id:nav.id,action,request_id:crypto.randomUUID(),
  client_event:{phase,client_ms:performance.now(),event_visible:event?.active===true,
   source:'hongik_click_panel',language:window.HongikLocale?.lang||'ko',...details}};
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
function scenarioComplete(){return latestData?.nurec?.scenario?.completed===true||event?.outcome?.phase==='complete'}
function returnToSelection(confirmedHorn=false){
 if(confirmedHorn!==true&&!scenarioComplete())return;
 if(window.HongikSurvey?.require())return;
 stopSpeech();
 if(latestData?.experiment){location.assign(window.HONGIK_TABLET?'/navigation':'/experiment');return;}
 const target=new URL('/',location.href);
 if(['A','B'].includes(event?.condition))target.searchParams.set('condition',event.condition);
 const lang=window.HongikLocale?.lang;if(['ko','en','zh'].includes(lang))target.searchParams.set('lang',lang);
 location.assign(target.pathname+target.search);
}
function render(){
 if(!event)return;
 const outcome=event.outcome||{},resolving=outcome.phase&&outcome.phase!=='idle',complete=scenarioComplete();
 if(complete&&!endingDismissed)dialog.hidden=true;
 if(resolving){phase='result';selected=null;optionsReady=false}
 $('research-ending').hidden=!complete||endingDismissed;
 replay.hidden=!complete;replay.disabled=replayBusy;
 if(complete||!dialog.hidden||!event.active)hideNotice();
 returnHome.hidden=!complete||!endingDismissed;
 $('research-fixed-help').hidden=complete;$('research-fixed-stop').hidden=complete;
 $('research-ending-message').textContent=outcome.message||(complete?'주행이 끝났어요. 다른 상황을 선택할 수 있어요.':'');
 $('research-ending-summary').textContent=outcome.summary||'';
 $('research-ending').querySelector('h2').textContent=latestData?.nurec?.scenario?.completion_reason==='horn_audio_finished'?'주행 종료':'주변 상황을 확인했어요';
 const stages={applying:'요청한 대응을 진행하고 있어요',observing:'주변의 반응을 확인하고 있어요',stopping:'서서히 정차하고 있어요',complete:'주변 확인 완료'};
 $('research-title').textContent=event.title;
 $('research-description').textContent=event.situation||event.description;
 $('research-vehicle-action').textContent=event.vehicle_action||event.description;
 $('research-live-detail').textContent=event.live_detail||'';
 $('research-caption').textContent=stages[outcome.phase]||(event.active?'현재 상황과 차량의 판단':'현재 주행');
 $('research-badge').textContent=resolving?(outcome.phase==='complete'?'주변 확인 완료':'주변 반응 확인 중'):unread?'새 상황 · 눌러서 대응 선택':'눌러서 상황·대응 보기';
 $('research-read').parentElement&&( $('research-read').parentElement.hidden=Boolean(resolving));
 if(unread&&event.active)$('research-badge').textContent=event.title+' · 눌러서 확인';
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
 $('research-confirmation').hidden=true;
 $('research-execute').disabled=busy||Boolean(event.pending)||(!event.active&&!selected?.fixed)||Boolean((event.options||[]).find(o=>o.action===selected?.action)?.disabled);
 $('research-back').disabled=busy;
 if(localFeedback&&(event.feedback||'')!==feedbackBaseline){localFeedback='';feedbackBaseline=event.feedback||''}
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
 const study=event.study||{};const requested=(event.options||[]).find(o=>o.action==='study_'+study.action);$('research-request-name').textContent=requested?.label||(study.action==='support'?'도움 요청':study.action==='safe_stop'?'정차 요청':'');const queued=study.phase==='queued';$('research-countdown').hidden=!queued;$('research-countdown-number').textContent=Math.max(1,Math.ceil(study.countdown_s||0));$('research-repeat').hidden=!study.repeatable;
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
 if(event.staged_options)scheduleChoices();
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
function hidePanel(){if(dialog.hidden)return;clearTimeout(explanationTimer);stopSpeech();generation++;dialog.hidden=true;phase='options';selected=null;busy=false;opening=false;dialogReady=false;optionsReady=false;launch.setAttribute('aria-expanded','false');render()}
window.HongikPanel={hide:hidePanel,isOpen:()=>!dialog.hidden};
function close(){
 clearTimeout(explanationTimer);
 if(dialog.hidden)return;
 stopSpeech();
 if(event?.study?.cancellable)record('study_cancel_pending',{reason:'explicit close'});
 record('study_close',{choice:selected?.action||'',phase});generation++;
 dialog.hidden=true;phase='options';selected=null;busy=false;opening=false;dialogReady=false;optionsReady=false;
 launch.setAttribute('aria-expanded','false');lastFocus?.focus();render();
}
async function choose(option){
 if(!option||busy||!optionsReady||!event?.active||event.pending||option.disabled)return;
 stopSpeech();
 const token=generation;busy=true;render();
 try{
  await post('study_choice',{choice:option.action});if(!isCurrent(token))return;
  selected=option;
  phase='confirm';$('research-confirm-copy').textContent=option.label+' 요청을 실행할까요? '+option.detail;
 // The execution acknowledgement names the action when the request is queued.
 }catch(error){if(isCurrent(token))showError(error)}
 finally{if(isCurrent(token)){busy=false;render();if(phase==='confirm')execute()}}
}
async function cancel(){
 if(busy)return;const token=generation;busy=true;render();
 try{await post('study_cancel',{choice:selected?.action});if(isCurrent(token)){phase='options';selected=null}}
 catch(error){if(isCurrent(token))showError(error)}
 finally{if(isCurrent(token)){busy=false;render()}}
}
async function execute(){
 if(!selected||busy||event?.pending||(!event?.active&&!selected.fixed)||(event.options||[]).find(o=>o.action===selected.action)?.disabled)return;
 const token=generation,action=selected.action,requestedLabel=selected.label,expected=session.session_id;
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
  phase='result';selected=null;optionsReady=false;localFeedback=requestedLabel+' · '+(result.message||'요청을 받았어요.');feedbackBaseline=event.feedback||'';
 }catch(error){if(isCurrent(token)){phase='options';selected=null;showError(error)}}
 finally{if(isCurrent(token)){busy=false;render()}}
}
function fixedRequest(action,label){if(busy||!event||event.pending)return;selected={action,label,fixed:true};phase='confirm';dialogReady=true;optionsReady=false;dialog.hidden=false;endingDismissed=true;$('research-confirm-copy').textContent=label+'을 실행할까요? '+(action==='study_fixed_help'?'지원 요청을 기록하며, 실제 상담원 연결은 보장되지 않아요.':'정차할 공간을 확인한 뒤 서서히 이동해요.')+' 실행 전까지 취소할 수 있어요.';render();execute();}
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
replay.onclick=async()=>{
 if(replayBusy||!scenarioComplete()||window.HongikSurvey?.require({testingReplay:true}))return;
 replayBusy=true;replay.disabled=true;
 try{
  const p=latestData?.experiment;
  const body=p?{experiment_index:p.index,option_order:p.option_order}:{profile:latestData.nurec.profile,condition:event.condition||'B',presentation:'midterm'};
  body.language=window.HongikLocale?.lang||'ko';
  const r=await fetch('/api/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'다시 준비하지 못했어요.');
  stopSpeech();location.reload();
 }catch(error){$('research-ending-message').textContent=error.message;replayBusy=false;replay.disabled=false}
};
$('research-ending-home').onclick=returnToSelection;returnHome.onclick=returnToSelection;
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!dialog.hidden){e.preventDefault();close()}});
function notify(){
 if(event?.active&&seen!==current.id&&document.visibilityState==='visible'){
  seen=current.id;unread=dialog.hidden;
  launch.setAttribute('aria-label',window.HongikLocale?.t?.(event.title+' · 눌러서 상황·대응 보기')||event.title);
  launch.title=event.title;
  if(unread)showNotice();
  record('study_presented',{alert_presented:true,phase:dialog.hidden?'button':'explanation_and_options'});
 }
 render();
}
document.addEventListener('visibilitychange',notify);
window.addEventListener?.('pagehide',stopSpeech);
window.addEventListener?.('nurec-exit',stopSpeech);
window.addEventListener?.('hongik-feedback-speaking',stopSpeech);
window.CockpitUpdate=data=>{
 previous?.(data);
 const next=data.session?.navigation?.research_event;
 const live=Boolean(next&&data.connected&&['ready','running'].includes(data.session?.stage));
 linkLive=live;
 if(!live&&session&&data.connected===false){
  root.hidden=false;launch.disabled=true;$('research-badge').textContent='차량 연결을 확인하고 있어요.';
  for(const button of [...$('research-options').children,$('research-execute'),$('research-fixed-help'),$('research-fixed-stop')])button.disabled=true;
  feedback('차량 연결이 끊겼어요. 다시 연결된 뒤 선택해 주세요.');return;
 }
 const fault=Boolean(data.nurec?.drive_guard);root.dataset.fault=String(fault);
 $('research-fixed-help').disabled=fault;$('research-fixed-stop').disabled=fault;
 root.hidden=!live;document.body.classList.toggle('research-driving',live);
 if(!live){hideNotice();stopSpeech();generation++;dialog.hidden=true;seen=null;session=null;current=null;event=null;busy=false;opening=false;dialogReady=false;optionsReady=false;return}
 if(session?.session_id!==data.session.session_id){
  hideNotice();endingDismissed=false;viewAcknowledged=false;
  stopSpeech();
  generation++;seen=null;unread=false;phase='options';selected=null;busy=false;opening=false;dialogReady=false;optionsReady=false;
  dialog.hidden=true;localFeedback='';feedbackBaseline='';signature=null;launch.setAttribute('aria-expanded','false');
 }
 session=data.session;current=session.navigation;event=next;latestData=data;launch.disabled=false;
 document.body.classList.add('midterm-study');launch.hidden=event.condition==='A';
 $('midterm-passive-title').textContent=data.nurec?.scenario?.completed?'차량이 정차했어요':data.passive?.title||event.title;$('midterm-passive-body').textContent=event.outcome?.summary||data.passive?.body||event.vehicle_action||event.description;
 if(event.study?.phase==='queued')viewAcknowledged=false;
 if(!event.active&&!selected?.fixed){unread=false;if(!event.staged_options||dialog.hidden)phase='options';selected=null;optionsReady=false}
 if(event.pending||scenarioComplete()){unread=false;stopSpeech()}
 notify();prepareOptions();if(fault)$('research-badge').textContent='주행 중단 · 다시 준비해 주세요';
};
})();

/* Passenger layer (2026-11-25 design review): passenger vs operator view, one status
 * bar, trip info instead of driver info, 76px touch targets, 16px minimum text, and
 * a ready-to-depart step. Operator view: ?operator=1, or hold the DRIVE wordmark 2 s. */
(()=>{
'use strict';
const $=id=>document.getElementById(id),body=document.body;
const qs=new URLSearchParams(location.search);
if(qs.has('operator'))sessionStorage.setItem('hongik-operator',qs.get('operator')==='0'?'0':'1');
function setMode(op){body.classList.toggle('operator-mode',op);body.classList.toggle('passenger-mode',!op);sessionStorage.setItem('hongik-operator',op?'1':'0');fitText();setTimeout(()=>dispatchEvent(new Event('resize')),50)}
const mark=document.querySelector('.wordmark');
if(mark){const flag=document.createElement('span');flag.id='operator-flag';flag.textContent='진행자 화면';mark.after(flag);let t=0;
 mark.addEventListener('pointerdown',()=>{t=setTimeout(()=>setMode(!body.classList.contains('operator-mode')),2000)});
 for(const e of ['pointerup','pointerleave','pointercancel'])mark.addEventListener(e,()=>clearTimeout(t));}
// scene sound needs a tap; in the passenger view any first tap arms it
document.addEventListener('pointerdown',()=>{const b=$('scene-audio-enable');if(b&&!b.hidden&&body.classList.contains('passenger-mode'))b.click()},true);

const icons={
 waiting:'<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7v5l3 2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
 normal:'<circle cx="12" cy="12" r="10" fill="currentColor"/><path d="M7.5 12.5l3 3 6-6.5" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
 situation:'<path d="M12 3l10 18H2z" fill="currentColor"/><path d="M12 10v5M12 17.6v.4" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>',
 request:'<circle cx="12" cy="12" r="10" fill="currentColor"/><path d="M7 12h9M13 8l4 4-4 4" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
 stopped:'<circle cx="12" cy="12" r="10" fill="currentColor"/><rect x="8.5" y="8.5" width="7" height="7" rx="1" fill="#fff"/>'};
const status=document.createElement('div');status.id='passenger-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
document.querySelector('header')?.append(status);
const trip=document.createElement('div');trip.id='passenger-trip';document.querySelector('.visualization')?.append(trip);
const ready=document.createElement('div');ready.id='passenger-ready';ready.hidden=true;
ready.innerHTML=`<div class="ready-card" role="dialog" aria-modal="true" aria-labelledby="ready-title"><h2 id="ready-title">출발할까요?</h2>
<dl><dt>목적지</dt><dd id="ready-destination">목적지</dd><dt>예상 시간</dt><dd id="ready-time">출발하면 계산해요</dd></dl>
<button type="button" class="belt" aria-pressed="false"><i aria-hidden="true"></i>안전벨트를 맸어요</button>
<button type="button" class="go" disabled>출발</button></div>`;
body.append(ready);
const belt=ready.querySelector('.belt'),go=ready.querySelector('.go');
belt.onclick=()=>{const on=belt.getAttribute('aria-pressed')!=='true';belt.setAttribute('aria-pressed',String(on));go.disabled=!on};
go.onclick=()=>{go.disabled=true;$('passenger-depart')?.click()};

let shown='',readySession=null;
function minutesLeft(data){const m=data.route?.remaining_m;if(!(m>0))return null;const v=Math.max(Number(data.nurec?.speed_kph)||0,0);return Math.max(1,Math.round(m/((v>=5?v:30)/3.6)/60))}
function clock(min){const d=new Date(Date.now()+min*60000);return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')}
function state(data){
 const n=data.nurec||{},s=n.scenario||{},ev=data.session?.navigation?.research_event,off=body.classList.contains('experiment-off')||ev?.condition==='A';
 const departBtn=$('passenger-depart'),waiting=departBtn&&!departBtn.hidden;
 if(!data.connected)return ['waiting','차량 연결 중'];
 if(waiting)return ['waiting','출발 대기'];
 const phase=ev?.outcome?.phase,study=ev?.study?.phase;
 if(s.completed||phase==='complete'||phase==='stopping'||(Number(n.speed_kph)||0)<.5)return ['stopped',phase==='stopping'?'정차하는 중':'정차 중'];
 if(!off&&(['applying','observing'].includes(phase)||['queued','applying','observing'].includes(study))){const name=window.HongikRequestName?.(ev?.study?.action)||'요청',o=ev?.outcome||{},left=Math.max(0,Math.ceil((o.observe_s||20)-(o.observed_s??o.observed??0)));return ['request',study==='queued'?name+' 실행 준비 중':study==='observing'||phase==='observing'?name+' 실행, 주변 반응 확인 중 '+left+'초':name+' 실행 중']}
 if(!off&&ev?.active)return ['situation','상황 확인 중'+(ev.title&&!body.classList.contains('docked')?': '+ev.title:'')];
 return ['normal','정상 주행'];
}
function update(data){
 if(!data)return;
 const [key,label]=state(data);const sig=key+label;
 if(sig!==shown){shown=sig;status.dataset.state=key;status.innerHTML=`<svg viewBox="0 0 24 24" aria-hidden="true">${icons[key]}</svg><span></span>`;status.querySelector('span').textContent=label}
 const min=minutesLeft(data),done=data.nurec?.scenario?.completed;
 trip.innerHTML=min&&!done?`<b>${clock(min)} 도착</b>남은 시간 약 ${min}분`:'';
 if($('route-eta'))$('route-eta').textContent=done?'도착':min?clock(min):'출발하면 계산해요';
 if($('route-time'))$('route-time').textContent=done?'0분':min?min+'분':'출발하면 계산해요';
 const departBtn=$('passenger-depart'),waiting=Boolean(departBtn&&!departBtn.hidden&&data.connected);
 const sid=data.session?.session_id||data.nurec?.scenario?.session||'';
 if(waiting&&readySession!==sid){readySession=sid;belt.setAttribute('aria-pressed','false');go.disabled=true}
 ready.hidden=!waiting||!body.classList.contains('passenger-mode');
 $('ready-destination').textContent=$('route-name')?.textContent||'목적지';
 $('ready-time').textContent=min?'약 '+min+'분':'출발하면 계산해요';
 const stop=$('research-fixed-stop');if(stop&&waiting)stop.hidden=true;
 fitText();
}
// 2. no text under 16px in the passenger view
let fitQueued=false;
function fitText(){if(fitQueued)return;fitQueued=true;setTimeout(()=>{fitQueued=false;
 for(const e of document.querySelectorAll('body *')){
  if(e.closest('svg,canvas,script,style'))continue;
  const own=[...e.childNodes].some(c=>c.nodeType===3&&c.textContent.trim())||/^(INPUT|SELECT|BUTTON)$/.test(e.tagName);if(!own)continue;
  if(!body.classList.contains('passenger-mode')){if(e.dataset.fitText){e.style.fontSize='';delete e.dataset.fitText}continue}
  if(e.dataset.fitText)continue;
  if(parseFloat(getComputedStyle(e).fontSize)<16){e.style.fontSize='16px';e.dataset.fitText='1'}
 }})}
function install(){
 setMode(sessionStorage.getItem('hongik-operator')==='1');
 const previous=window.CockpitUpdate;window.CockpitUpdate=data=>{previous?.(data);try{update(data)}catch(e){console.warn('passenger layer',e)}};
 new MutationObserver(fitText).observe(body,{childList:true,subtree:true});
}
if(document.readyState==='complete')install();else window.addEventListener('load',install);
})();

/* Screen proposals (2026-11-25 review, screens 03 to 08): situation notice, cause marker in 3D,
 * shorter explanation with live numbers, choice outcomes, countdown ring and preview, request
 * steps, result hand-off to the status bar, and the end-of-drive summary. */
(()=>{
'use strict';
const $=id=>document.getElementById(id),body=document.body;
let data=null,lastPhase='',lastAction='',ringTotal=0,requested='';
const NAMES={horn:'경적',widen:'거리 넓히기',distance:'거리 넓히기',merge:'1차로 진입',pass:'앞지르기',notify:'알림',safe_stop:'갓길 정차',end_ride:'근처에서 내리기',slow:'더 천천히 가기',inspect:'주변 보기',maintain:'그냥 두기',fixed_help:'도움 요청',fixed_stop:'정차 요청',support:'도움 요청'};
window.HongikRequestName=a=>NAMES[String(a||'').replace(/^study_/,'')]||'';
const EFFECT={
 horn:p=>p==='congestion'?'약 2초 경적, 속도와 차로는 그대로':'약 1초 경적, 속도와 차로는 그대로',
 widen:p=>p==='night'?'약 10초 동안 감속, 간격 28m까지':'약 10초 동안 감속해 간격을 넓힘',
 distance:()=>'약 10초 동안 감속해 간격을 넓힘',
 merge:()=>'틈이 날 때까지 차로 유지, 진입에 약 5초',
 pass:()=>'틈이 나면 왼쪽 차로로, 앞차보다 9m 앞설 때까지',
 notify:()=>'차는 그대로, 상황이 바뀌면 바로 알림',
 safe_stop:()=>'약 20초 동안 감속해 갓길에 정차',
 end_ride:()=>'정차할 곳을 찾아 멈춘 뒤 이용 종료',
 slow:()=>'속도를 낮추고 간격을 더 확보',
 inspect:()=>'주변 차량 위치를 화면에 보여줌'};
const ev=()=>data?.session?.navigation?.research_event;
const aiOn=()=>!body.classList.contains('experiment-off')&&ev()?.condition!=='A';
function addOnce(id,html,place){if($(id))return $(id);const t=document.createElement('template');t.innerHTML=html.trim();const n=t.content.firstElementChild;place(n);return n}

// 03-1, 03-4: notice drops from the status bar, flashes the screen edge, and the whole card opens Hongiki
const notice=$('research-notice');
if(notice){notice.addEventListener('click',e=>{if(e.target.closest('#research-notice-close,#research-notice-more'))return;$('research-notice-more')?.click()});
 new MutationObserver(()=>{if(!notice.hidden&&body.classList.contains('passenger-mode')){body.classList.add('alert-flash');setTimeout(()=>body.classList.remove('alert-flash'),2400)}}).observe(notice,{attributes:true,attributeFilter:['hidden']});}

// 03-2: outline and label the vehicle that causes the situation
const mark=document.createElement('div');mark.id='cause-mark';mark.hidden=true;mark.innerHTML='<span></span>';body.append(mark);
const CAUSE={congestion:'느리게 가는 앞차',night:'차선을 넘나드는 앞차',fog:'앞차'};
function placeMark(){requestAnimationFrame(placeMark);const S=window.CockpitScene,e=ev(),p=data?.nurec?.profile;
 const show=S&&e?.active&&aiOn()&&body.classList.contains('passenger-mode')&&!(e.outcome?.phase&&e.outcome.phase!=='idle')&&CAUSE[p];
 if(!show){mark.hidden=true;return}
 const lead=(data.actors||[]).find(a=>a.role==='lead'),entry=lead&&S.objects.get(lead.id);if(!entry){mark.hidden=true;return}
 const box=new S.THREE.Box3().setFromObject(entry.mesh),r=S.host.getBoundingClientRect();let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9,behind=false;
 for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){const v=new S.THREE.Vector3(x,y,z).project(S.camera);if(v.z>1)behind=true;const sx=r.left+(v.x+1)/2*r.width,sy=r.top+(1-v.y)/2*r.height;x0=Math.min(x0,sx);x1=Math.max(x1,sx);y0=Math.min(y0,sy);y1=Math.max(y1,sy)}
 if(behind||x1<r.left||x0>r.right||y1<r.top||y0>r.bottom){mark.hidden=true;return}
 const pad=10;mark.hidden=false;mark.style.left=(x0-pad)+'px';mark.style.top=(y0-pad)+'px';mark.style.width=(x1-x0+pad*2)+'px';mark.style.height=(y1-y0+pad*2)+'px';mark.firstChild.textContent=CAUSE[p]}
requestAnimationFrame(placeMark);

function panel(){
 const e=ev();if(!e)return;const st=e.study||{},out=e.outcome||{},profile=data.nurec?.profile,phaseNow=st.phase||'idle';
 // 04-2: keep-as-is gets the same weight as the other choices
 const keep=$('research-maintain');if(keep&&!keep.dataset.styled){keep.dataset.styled='1';keep.classList.add('research-option');keep.innerHTML='<strong>그냥 둘게요</strong><small>차가 지금처럼 알아서 대응해요</small><span class="effect">차는 그대로, 언제든 다시 고를 수 있음</span>'}
 const note=addOnce('options-note','<p id="options-note">차가 계속 대응하고 있어요. 바꾸고 싶을 때만 고르세요</p>',n=>$('research-options-label')?.after(n));
 note.hidden=$('research-options-label')?.hidden!==false;
 // 04-3: what each choice does, with time and motion
 for(const b of document.querySelectorAll('#research-options .research-option')){if(b.querySelector('.effect'))continue;const k=String(b.dataset.action).replace(/^study_/,''),f=EFFECT[k];if(!f)continue;const s=document.createElement('span');s.className='effect';s.textContent='예상: '+f(profile);b.append(s)}
 // 04-4: one sentence plus the two numbers that matter
 const tiles=addOnce('situation-metrics','<div id="situation-metrics"><div><small>앞차와 간격</small><b id="metric-gap">—</b></div><div><small>지금 속도</small><b id="metric-speed">—</b></div></div>',n=>$('research-title')?.after(n));
 const lead=(data.actors||[]).find(a=>a.role==='lead')||(data.actors||[]).filter(a=>a.kind==='vehicle'&&a.forward_m>(data.ego?.forward_m||0)&&Math.abs(a.right_m-(data.ego?.right_m||0))<(data.lane_width_m||3.5)*.48).sort((a,b)=>a.forward_m-b.forward_m)[0];
 $('metric-gap').textContent=lead?Math.max(0,Math.round(lead.forward_m-(data.ego?.forward_m||0)))+'m':'—';
 const v=data.ego?.speed_kmh??data.nurec?.speed_kph;$('metric-speed').textContent=v==null?'—':Math.round(v)+' km/h';
 // 07-4: request, run, check, done in one line
 const steps=addOnce('request-steps','<ol id="request-steps"><li>요청</li><li>실행</li><li>확인</li><li>완료</li></ol>',n=>document.querySelector('#research-dialog .midterm-choices')?.prepend(n));
 const idx={queued:0,applying:1,observing:2,stopping:3,complete:3}[out.phase==='complete'?'complete':phaseNow];
 steps.hidden=idx==null;[...steps.children].forEach((li,i)=>{li.className=i<idx?'done':i===idx?'now':''});
 // 06-1: ring around the countdown; 05-3: preview of what will happen
 const cd=$('research-countdown');
 if(cd&&!$('countdown-ring')){const num=$('research-countdown-number');const wrap=document.createElement('div');wrap.id='countdown-ring';wrap.innerHTML='<svg viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="52" class="track"/><circle cx="60" cy="60" r="52" class="bar"/></svg>';num.before(wrap);wrap.append(num)}
 if(phaseNow==='queued'){const c=Number(st.countdown_s)||0;if(lastPhase!=='queued'||c>ringTotal)ringTotal=Math.max(c,1);const bar=document.querySelector('#countdown-ring .bar');if(bar){const L=2*Math.PI*52;bar.style.strokeDasharray=L;bar.style.strokeDashoffset=L*(1-Math.min(1,c/ringTotal))}}
 const pv=addOnce('request-preview','<figure id="request-preview"><svg viewBox="0 0 320 120" aria-hidden="true"></svg><figcaption></figcaption></figure>',n=>$('research-countdown')?.append(n));
 const key=String(st.action||'').replace(/^study_/,'');if(pv.dataset.key!==key){pv.dataset.key=key;drawPreview(pv,key,profile)}
 // 07-2: name what "once more" repeats
 const rep=$('research-repeat');if(rep){const n=NAMES[key];rep.textContent=n?n+' 한 번 더':'한 번 더'}
 // 07-3: say what the result frame shows
 const frame=$('research-result-frame');const cap=addOnce('result-caption','<p id="result-caption">실제 주행 화면: 요청한 뒤 주변 차량의 반응</p>',n=>frame?.after(n));cap.hidden=!frame||frame.hidden;
 // 07-1: once the request runs, close the panel and let the status bar carry it
 if(phaseNow==='applying'&&lastPhase==='queued'&&key!=='inspect'&&body.classList.contains('passenger-mode')&&!body.classList.contains('docked'))window.HongikPanel?.hide();
 if(['queued','applying'].includes(phaseNow)&&key)requested=key;
 body.classList.toggle('request-active',['queued','applying','observing','stopping'].includes(phaseNow)||out.phase==='complete');
 lastPhase=phaseNow;
 ending(e,out);
}
function drawPreview(fig,key,profile){
 const svg=fig.querySelector('svg'),cap=fig.querySelector('figcaption');
 const car=(x,y,c,dash)=>`<rect x="${x}" y="${y}" width="44" height="22" rx="5" fill="${dash?'none':c}" stroke="${dash?'#3e6ae1':'none'}" stroke-dasharray="${dash?'5 4':''}" stroke-width="2"/>`;
 const lanes='<line x1="0" y1="40" x2="320" y2="40" stroke="#cfd7e3" stroke-dasharray="10 8"/><line x1="0" y1="80" x2="320" y2="80" stroke="#cfd7e3" stroke-dasharray="10 8"/>';
 const arrow=(x1,y1,x2,y2)=>`<path d="M${x1} ${y1} L${x2} ${y2}" stroke="#3e6ae1" stroke-width="2.5" fill="none" marker-end="url(#pv-arrow)"/>`;
 const defs='<defs><marker id="pv-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#3e6ae1"/></marker></defs>';
 let art='',text='';
 if(key==='widen'||key==='distance'||key==='slow'){art=car(40,49,'#26354c')+car(150,49,'#9aa6b8')+car(230,49,'#9aa6b8',true)+arrow(196,60,226,60);text='앞차와 간격이 늘어나요'}
 else if(key==='merge'||key==='pass'){art=car(40,49,'#26354c')+car(130,49,'#9aa6b8')+car(200,9,'#26354c',true)+`<path d="M86 60 C120 60 150 20 196 20" stroke="#3e6ae1" stroke-width="2.5" fill="none" marker-end="url(#pv-arrow)"/>`;text=key==='pass'?'왼쪽 차로로 앞질러 가요':'틈이 나면 왼쪽 차로로 들어가요'}
 else if(key==='horn'){art=car(40,49,'#26354c')+car(170,49,'#9aa6b8')+'<path d="M96 48 q10 12 0 24 M108 42 q16 18 0 36 M120 36 q22 24 0 48" stroke="#3e6ae1" stroke-width="2.5" fill="none"/>';text='경적만 울리고 속도와 차로는 그대로'}
 else if(key==='safe_stop'||key==='fixed_stop'||key==='end_ride'){art=car(40,49,'#26354c')+car(210,89,'#26354c',true)+`<path d="M86 60 C140 60 160 100 206 100" stroke="#3e6ae1" stroke-width="2.5" fill="none" marker-end="url(#pv-arrow)"/>`+'<line x1="0" y1="118" x2="320" y2="118" stroke="#9aa6b8"/>';text='오른쪽으로 빠져 천천히 멈춰요'}
 else if(key==='notify'){art=car(40,49,'#26354c')+car(170,49,'#9aa6b8')+'<circle cx="250" cy="60" r="16" fill="none" stroke="#3e6ae1" stroke-width="2.5"/><path d="M250 52v10M250 67v1" stroke="#3e6ae1" stroke-width="3" stroke-linecap="round"/>';text='차는 그대로, 변화가 생기면 알려 줘요'}
 else if(key==='fixed_help'||key==='support'){art='<circle cx="160" cy="60" r="26" fill="none" stroke="#3e6ae1" stroke-width="2.5"/><path d="M150 56a10 10 0 1 1 14 9c-3 2-4 3-4 7M160 79v1" stroke="#3e6ae1" stroke-width="3" fill="none" stroke-linecap="round"/>';text='상담 연결을 요청해요'}
 else {fig.hidden=true;return}
 fig.hidden=false;svg.innerHTML=defs+lanes+art;cap.textContent=text}

// 08: one end-of-drive summary with a single next step
function ending(e,out){
 const card=$('research-ending');if(!card)return;
 const sum=addOnce('ending-summary-list','<dl id="ending-summary-list"><dt>상황</dt><dd id="end-situation"></dd><dt>요청</dt><dd id="end-request"></dd><dt>결과</dt><dd id="end-result"></dd></dl>',n=>card.querySelector('h2')?.after(n));
 addOnce('ending-exit','<ul id="ending-exit"><li>내릴 때는 오른쪽 문을 이용해 주세요</li><li>휴대폰과 소지품을 챙겼는지 확인해 주세요</li></ul>',n=>sum.after(n));
 const next=addOnce('ending-survey','<button id="ending-survey" type="button" class="research-primary">주행 후 설문 작성</button>',n=>$('ending-exit').after(n));
 next.onclick=()=>$('survey-reopen')?.click();
 const reopen=$('survey-reopen');next.hidden=!reopen||reopen.hidden;if(reopen)next.textContent=reopen.textContent;
 $('end-situation').textContent=e.title||'';
 const asked=requested||String(out.action||e.study?.action||'').replace(/^study_/,'');$('end-request').textContent=NAMES[asked]||'요청하지 않음';
 $('end-result').textContent=out.summary||out.message||'주행을 마쳤어요';
}
function install(){const prev=window.CockpitUpdate;window.CockpitUpdate=d=>{prev?.(d);if(!d?.connected)return;if(data?.session?.session_id!==d.session?.session_id){requested='';lastPhase=''}data=d;try{panel()}catch(err){console.warn('screen proposals',err)}}}
if(document.readyState==='complete')install();else window.addEventListener('load',install);
})();

/* Docked layout (2026-11-25 sketch): no pop-ups on the passenger screen. Header shows the time and
 * arrival, the left 40 % is the drive view with the situation card, the right 60 % is the option pane
 * that hosts the ready step, Hongiki's choices and the end summary. Nothing scrolls. */
(()=>{
'use strict';
const $=id=>document.getElementById(id),body=document.body;
if(!document.querySelector('.visualization')||!document.querySelector('.map-panel'))return;
let data=null;
const hhmm=d=>String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');
const header=document.querySelector('header');
const now=document.createElement('strong');now.id='hdr-now';const eta=document.createElement('strong');eta.id='hdr-eta';header?.append(now,eta);
const card=document.createElement('section');card.id='situation-card';card.hidden=true;card.setAttribute('aria-live','polite');
card.innerHTML='<div class="sc-top"><small id="sc-title"></small><button type="button" id="sc-open">가능한 액션 보기</button></div><p id="sc-body" class="ko-subtitle"></p>';
document.querySelector('.visualization')?.append(card);card.addEventListener('animationend',()=>window.KoType?.refresh?.());
const pane=document.createElement('section');pane.id='option-pane';
pane.innerHTML='<h2 id="pane-title">차량 주행 옵션 선택하기</h2><div class="pane-card"><p id="pane-copy" class="ko-subtitle"></p><button type="button" id="pane-open" class="research-primary" hidden>주행 옵션 보기</button></div>';
document.querySelector('.map-panel')?.append(pane);
const foot=document.querySelector('footer');
const help=document.createElement('button');help.id='footer-help';help.type='button';help.textContent='고객센터 연결';
const music=document.createElement('button');music.id='footer-music';music.type='button';music.setAttribute('aria-label','음악');music.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h11M3 11h11M3 16h7M18 4v12.5a2.5 2.5 0 1 1-2-2.45V4h5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg><span id="footer-track"></span>';
const stop=document.createElement('button');stop.id='footer-stop';stop.type='button';stop.textContent='길가에 정차';
foot?.prepend(help);foot?.append(music,stop);
const open=()=>{const l=$('research-launch');if(l&&$('research-dialog')?.hidden)l.click()};
$('sc-open').onclick=open;$('pane-open').onclick=open;
help.onclick=()=>$('research-fixed-help')?.click();
stop.onclick=()=>$('research-fixed-stop')?.click();
// Now Playing widget above the footer music button (Apple home screen widget style)
const svg=d=>`<svg viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
const IC={prev:svg('<path d="M6 5v14" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><path d="M19 5.5v13L9 12z" fill="currentColor"/>'),next:svg('<path d="M18 5v14" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><path d="M5 5.5v13L15 12z" fill="currentColor"/>'),play:svg('<path d="M7 4.5v15l13-7.5z" fill="currentColor"/>'),pause:svg('<rect x="6" y="4.5" width="4.2" height="15" rx="1.2" fill="currentColor"/><rect x="13.8" y="4.5" width="4.2" height="15" rx="1.2" fill="currentColor"/>'),note:svg('<path d="M9 18V6l10-2v12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="6.5" cy="18" r="2.5" fill="currentColor"/><circle cx="16.5" cy="16" r="2.5" fill="currentColor"/>'),low:svg('<path d="M4 9.5h3l4-3.5v12l-4-3.5H4z" fill="currentColor"/>'),high:svg('<path d="M4 9.5h3l4-3.5v12l-4-3.5H4z" fill="currentColor"/><path d="M15 9a4 4 0 0 1 0 6M17.5 6.5a7.5 7.5 0 0 1 0 11" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'),close:svg('<path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>')};
const np=document.createElement('section');np.id='now-playing';np.hidden=true;np.setAttribute('aria-label','음악');
np.innerHTML=`<div class="np-wash" aria-hidden="true"></div>
<div class="np-now"><span class="np-art" id="np-art">${IC.note}</span><div class="np-meta"><strong id="np-title">재생 중 아님</strong><span id="np-artist"></span></div></div>
<div class="np-scrub"><input type="range" id="np-seek" min="0" max="100" step="0.1" value="0" aria-label="재생 위치"><div class="np-time"><span id="np-elapsed">0:00</span><span id="np-duration">-0:00</span></div></div>
<div class="np-controls"><button type="button" id="np-prev" aria-label="이전 곡">${IC.prev}</button><button type="button" id="np-play" class="np-play" aria-label="재생">${IC.play}</button><button type="button" id="np-next" aria-label="다음 곡">${IC.next}</button></div>
<div class="np-volume">${IC.low}<input type="range" id="np-volume" min="0" max="100" value="45" aria-label="음량">${IC.high}</div>`;
document.body.append(np);
// Gear selector as an Apple-style segmented control (P R N D, active gear in a raised pill)
const gearsEl=document.querySelector('.speed-panel .gears');
if(gearsEl&&!gearsEl.querySelector('.gear')){const active=(gearsEl.querySelector('b')?.textContent||'D').trim();gearsEl.setAttribute('role','img');gearsEl.setAttribute('aria-label','기어 '+active);gearsEl.innerHTML=['P','R','N','D'].map(g=>`<span class="gear${g===active?' on':''}">${g}</span>`).join('')}
const glass=document.createElement('div');glass.className='scene-glass';glass.setAttribute('aria-hidden','true');document.querySelector('.visualization')?.prepend(glass);
const au=document.getElementById('audio');const mmss=t=>Number.isFinite(t)?`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`:'0:00';
const fill=el=>el.style.setProperty('--fill',el.value+'%');
function npSync(){const title=$('track-title')?.textContent||'음악을 선택하세요';const picked=title!=='음악을 선택하세요';const playing=!!au&&!au.paused;
 $('np-title').textContent=picked?title:'재생 중 아님';$('np-artist').textContent=picked?($('track-artist')?.textContent||''):'';const bg=$('current-art')?.style.background;
 np.style.setProperty('--np-tint',picked&&bg?bg:'linear-gradient(#e9e9ee,#e9e9ee)');np.classList.toggle('picked',picked);np.classList.toggle('playing',playing);
 $('np-play').innerHTML=playing?IC.pause:IC.play;$('np-play').setAttribute('aria-label',playing?'일시정지':'재생');
 if(au){$('np-elapsed').textContent=mmss(au.currentTime);$('np-duration').textContent='-'+mmss(Math.max(0,(au.duration||0)-(au.currentTime||0)));$('np-seek').value=au.duration?au.currentTime/au.duration*100:0;fill($('np-seek'))}
}
function placeNp(){const r=music.getBoundingClientRect();np.style.left=Math.max(12,Math.min(r.left,innerWidth-np.offsetWidth-12))+'px'}
function toggleNp(show=np.hidden){np.hidden=!show;music.classList.toggle('active',show);if(show){npSync();placeNp()}}
music.onclick=e=>{e.stopPropagation();toggleNp()};
$('np-prev').onclick=()=>$('previous')?.click();$('np-next').onclick=()=>$('next')?.click();$('np-play').onclick=()=>$('play')?.click();
$('np-seek').oninput=()=>{fill($('np-seek'));if(au&&Number.isFinite(au.duration))au.currentTime=+$('np-seek').value/100*au.duration};
$('np-volume').oninput=()=>{fill($('np-volume'));const v=$('volume');if(v){v.value=$('np-volume').value;v.dispatchEvent(new Event('input'))}};fill($('np-volume'));
if(au)for(const ev of ['play','pause','timeupdate','loadedmetadata','emptied'])au.addEventListener(ev,()=>{if(!np.hidden)npSync()});

document.addEventListener('pointerdown',e=>{if(!np.hidden&&!np.contains(e.target)&&!music.contains(e.target))toggleNp(false)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!np.hidden)toggleNp(false)});
addEventListener('resize',()=>{if(!np.hidden)placeNp()});
$('research-close')?.addEventListener('click',e=>{if(body.classList.contains('direct-mode')){e.stopImmediatePropagation();body.classList.remove('direct-mode')}},true);
function setSub(el,text){if(el&&el.dataset.raw!==text){el.dataset.raw=text;el.textContent=text;requestAnimationFrame(()=>window.KoType?.refresh?.())}}
function tick(){now.textContent='현재 시각 '+hhmm(new Date())}tick();setInterval(tick,15000);
function update(d){
 if(!body.classList.contains('passenger-mode'))return;
 const ev=d.session?.navigation?.research_event,off=body.classList.contains('experiment-off')||ev?.condition==='A';
 const complete=d.nurec?.scenario?.completed,m=d.route?.remaining_m,v=Number(d.nurec?.speed_kph)||0;
 const min=m>0?Math.max(1,Math.round(m/((v>=5?v:30)/3.6)/60)):null;
 eta.textContent=complete?'도착':min?'도착 예정 시각 '+hhmm(new Date(Date.now()+min*60000)):'';
 const active=Boolean(ev?.active)&&!off&&!complete,dialogOpen=!$('research-dialog')?.hidden;
 card.hidden=!active;
 if(active){$('sc-title').textContent=ev.title||'';setSub($('sc-body'),ev.situation||ev.description||'');$('sc-open').hidden=dialogOpen}
 const waiting=!$('passenger-ready')?.hidden,ending=!$('research-ending')?.hidden;
 const survey=Boolean($('post-drive-survey')?.open),st=ev?.study?.phase,running=!off&&['queued','applying','observing','stopping'].includes(st);
 $('pane-title').hidden=off&&!waiting&&!ending&&!survey;$('pane-title').textContent=survey?'주행 후 설문':waiting?'출발 준비':ending?'주행 결과':'차량 주행 옵션 선택하기';
 let paneText=off||!active?'차가 경로를 따라 주행하고 있어요':'가능한 액션을 여기에서 고를 수 있어요';
 if(running){paneText=$('passenger-status')?.textContent||'요청을 진행하고 있어요';$('pane-open').textContent='진행 상황 보기'}else $('pane-open').textContent='가능한 액션 보기';
 setSub($('pane-copy'),paneText);
 $('pane-open').hidden=!(active||running)||dialogOpen;
 pane.dataset.covered=String(dialogOpen||waiting||ending||survey);
 const lane=$('lane');if(lane&&lane.innerHTML.includes('왼쪽부터'))lane.innerHTML=lane.innerHTML.replace(' · 왼쪽부터','');
 const back=$('research-close');if(back&&back.dataset.back!=='1'){back.dataset.back='1';back.textContent='‹ 뒤로 가기';back.setAttribute('aria-label','뒤로 가기')}
 const req=$('experiment-request'),opts=$('research-options');
 if(opts&&req&&!req.hidden&&!opts.querySelector('#direct-card')){const c=document.createElement('button');c.type='button';c.id='direct-card';c.className='research-option';c.dataset.unavailable='false';c.innerHTML='<strong>직접 명령하기</strong><small>말이나 글로 요청해요</small>';c.onclick=()=>body.classList.add('direct-mode');opts.append(c)}
 if(!dialogOpen||opts?.hidden&&!body.classList.contains('typing'))body.classList.remove('direct-mode');
 {const tt=$('track-title')?.textContent||'';$('footer-track').textContent=tt&&tt!=='음악을 선택하세요'?tt:''}
 const fh=$('research-fixed-help'),fs=$('research-fixed-stop');
 help.disabled=!fh||fh.disabled||fh.hidden;stop.disabled=!fs||fs.disabled||fs.hidden;
 const typing=!document.querySelector('#experiment-request form')?.hidden||!$('experiment-confirm')?.hidden;
 body.classList.toggle('typing',Boolean(typing));
}
function install(){body.classList.add('docked');const prev=window.CockpitUpdate;window.CockpitUpdate=d=>{prev?.(d);if(!d?.connected)return;data=d;try{update(d)}catch(e){console.warn('docked layout',e)}};setTimeout(()=>dispatchEvent(new Event('resize')),100)}
if(document.readyState==='complete')install();else window.addEventListener('load',install);
})();

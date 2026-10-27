import {GestureLogic,GesturePreviewState,classifyPointGesture} from '/gesture-logic.mjs';
const $=id=>document.getElementById(id),logic=new GestureLogic(),previewState=new GesturePreviewState();
const modes={
 touch:{label:'기존 터치',help:'기존 팝업 제안형·방향 버튼형을 그대로 사용합니다.'},
 gesture_touch:{label:'손들기 · 버튼 선택',help:'손바닥을 0.8초 펼치면 4가지 주행 조정 버튼이 뜹니다. 화면을 눌러 선택하세요.'},
 gesture_swipe:{label:'손가락 방향 제어',help:'다른 손가락을 접고 엄지만 왼쪽·오른쪽으로 가리키면 차선 변경, 검지만 위로 가리키면 10km/h 가속, 아래로 가리키면 10km/h 감속합니다. 0.5초 유지한 뒤 손을 풀어 주세요. 손이 감지되면 카메라 미리보기가 자동으로 열립니다.'},
 voice:{label:'음성 인식',help:'마이크를 켜고 “홍익아”로 호출한 뒤 “앞 상황이 불안해 보여”라고 물어보세요. 제안에 “응, 해줘”라고 동의하면 실행합니다.'},
 gesture_cursor:{label:'공중 커서 · 주먹 선택',help:'손바닥을 0.8초 펼쳐 팝업을 여세요. 펼친 손으로 커서를 옮기고, 버튼 위에서 주먹을 0.4초 유지하면 선택됩니다.'}
};
let mode='touch',preparing=false,enabled=false,stream=null,worker=null,workerBusy=false,workerReady=false,generation=0,frameTimer=null,session=null,requestBusy=false,stateConnected=false;
let cursor=null,frozenButton=null,hoverButton=null,grabbing=false,ctx=null,audioNode=null,voiceBusy=false,preRoll=[],audioChunks=[],speaking=false,speechSession=null,speechStart=0,silentMs=0,voicedMs=0,oldAudioMuted=null,noticeUntil=0;
const modal=$('hand-control-modal'),video=$('gesture-video'),status=$('input-status'),label=$('input-status-label'),buttons=[...document.querySelectorAll('[data-hand-action]')];
const actionLabels={lane_left:'← 왼쪽 차선 변경',lane_right:'→ 오른쪽 차선 변경',speed_up:'↑ 10 km/h 가속',speed_down:'↓ 10 km/h 감속'};
function swipeFeedback(text,error=false){if(mode!=='gesture_swipe')return;$('gesture-action').textContent=text;$('gesture-action').dataset.state=error?'error':'ready'}
function hideGesturePreview(){$('input-preview').hidden=true;previewState.dismiss()}
function drawGesture(data){
 const canvas=$('gesture-overlay'),paint=canvas.getContext('2d');paint.clearRect(0,0,canvas.width,canvas.height);
 if(data.landmarks?.length!==21)return;
 const at=p=>[(1-p.x)*canvas.width,p.y*canvas.height];
 const connections=[[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[0,17],[17,18],[18,19],[19,20]];
 paint.strokeStyle='#62dcb7';paint.lineWidth=3;paint.beginPath();for(const [a,b]of connections){paint.moveTo(...at(data.landmarks[a]));paint.lineTo(...at(data.landmarks[b]))}paint.stroke();
 paint.fillStyle='#fff';for(const p of data.landmarks){paint.beginPath();paint.arc(...at(p),4,0,Math.PI*2);paint.fill()}
}
function message(text,error=false){label.textContent=text;$('input-device-feedback').textContent=text;status.classList.toggle('error',error)}
function active(){return window.cockpitPreview?session?.stage==='driving'&&session?.navigation?.status==='offered':session?.stage==='running'&&[6,7].includes(session?.scenario)&&['encounter','offered'].includes(session?.navigation?.scenario_stage)}
function blockedReason(){
 if(!session||(!stateConnected&&!window.cockpitPreview))return '차량 연결이 없습니다. 36번 앱을 실행해 연결을 복구해 주세요.';
 if(session.stage==='ready'||session.navigation?.status==='ready')return '내비게이션의 주행 시작 버튼을 먼저 눌러 주세요.';
 if(session.navigation?.status==='arrived')return '목적지에 도착했습니다. 새 주행에서 사용할 수 있습니다.';
 if(['stopped','finished'].includes(session.stage))return '주행이 종료됐습니다. 새 주행을 시작해 주세요.';
 if(['cruise','cooldown','resolved'].includes(session.navigation?.scenario_stage))return '상황 대기 중입니다. 상황이 나타나면 조정할 수 있습니다.';
 return '차량이 주행을 조정하고 있습니다. 완료 후 다시 가리켜 주세요.';
}
function validSession(){return session?.stage==='running'||window.cockpitPreview}
function closeModal(resetLogic=true){modal.hidden=true;$('hand-cursor').hidden=true;cursor=null;frozenButton=null;hoverButton=null;grabbing=false;buttons.forEach(b=>b.classList.remove('hand-hover'));if(resetLogic)logic.reset();else{logic.wakeLatched=true;logic.fistLatched=true}}
function openModal(){
 if(!enabled||!validSession())return;
 modal.hidden=false;modal.classList.toggle('cursor-mode',mode==='gesture_cursor');
 $('hand-control-instruction').textContent=mode==='gesture_cursor'?'손을 펼쳐 커서를 옮긴 뒤, 주먹을 쥐어 선택하세요.':'원하는 조정을 선택하세요.';
 $('hand-control-feedback').textContent=active()?'': '상황이 나타나면 조정할 수 있습니다.';
 buttons.forEach(b=>b.disabled=!active()||requestBusy);
}
function restoreAudio(){if(oldAudioMuted!==null){$('audio').muted=oldAudioMuted;oldAudioMuted=null}}
function clearVoice(){preRoll=[];audioChunks=[];speaking=false;speechSession=null;silentMs=0;voicedMs=0}
function stopDevices(){
 generation++;enabled=false;workerReady=false;workerBusy=false;clearInterval(frameTimer);frameTimer=null;
 if(worker){worker.terminate();worker=null}
 if(stream)stream.getTracks().forEach(t=>t.stop());stream=null;
 previewState.reset();drawGesture({landmarks:[]});
 if(ctx){ctx.close().catch(()=>{});ctx=null}audioNode=null;clearVoice();restoreAudio();closeModal();
 status.classList.remove('active');$('input-toggle').textContent='켜기';$('input-device-enable').textContent='입력 장치 켜기';$('input-preview').hidden=true;
}
window.passengerInputMode='touch';
window.setPassengerInputMode=value=>{
 if(!(value in modes))value='touch';
 if(value!==mode)stopDevices();
 mode=value;$('swipe-guide').hidden=value!=='gesture_swipe';window.passengerInputMode=value;$('experience-input-mode').value=value;
 status.hidden=value==='touch';$('input-device-enable').hidden=value==='touch';
 $('input-preview-toggle').hidden=value==='touch'||value==='voice';
 $('input-mode-help').textContent=modes[value].help+(value==='gesture_swipe'?' 손바닥 면을 카메라로 향하고 손목과 손가락이 화면 안에 보이게 해 주세요.':value.startsWith('gesture_')?' 손바닥 면을 카메라로 향하고 손목과 다섯 손가락 전체가 보이게 해 주세요.':'');
 message(modes[value].label+' · '+(enabled?'입력 중':'꺼짐'));
 window.dispatchEvent(new Event('passenger-input-mode-changed'));
};
const previousUpdate=window.CockpitUpdate;
window.CockpitUpdate=data=>{
 previousUpdate?.(data);
 stateConnected=data?.connected===true;
 const next=data?.session;
 if(session?.session_id!==next?.session_id){closeModal();clearVoice()}
 session=next;
 if(!validSession()){closeModal();clearVoice()}
 if(!modal.hidden)buttons.forEach(b=>b.disabled=!active()||requestBusy);
 if(enabled&&!preparing&&performance.now()>noticeUntil&&!requestBusy&&!voiceBusy){
  message(!session&&!window.cockpitPreview?'주행 연결 대기 · '+modes[mode].label:mode==='voice'?'음성 입력 중 · '+(speaking?'말씀을 듣고 있어요':'요청을 말해 주세요'):modes[mode].label+' · 손 인식 중');
 }
};
async function pollJob(queued,token){
 for(let i=0;i<120;i++){
  if(token!==generation)throw Error('입력 설정이 변경되었습니다.');
  await new Promise(r=>setTimeout(r,500));
  const response=await fetch('/api/voice/job?id='+queued.job_id,{cache:'no-store'});
  const result=await response.json();
  if(result.error)throw Error(result.error);
  if(result.status==='complete')return result;
 }
 throw Error('음성 처리 시간이 초과됐습니다.');
}
async function post(path,body){
 const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const result=await response.json();if(!response.ok)throw Error(result.error||'입력을 처리하지 못했습니다.');return result;
}
async function sendIntent(action,{transcript='',startedAt=performance.now()}={}){
 if(requestBusy)return;
 if(!active()){const reason=blockedReason();swipeFeedback('최근 요청: '+actionLabels[action]+' · '+reason,true);message(reason,true);noticeUntil=performance.now()+2500;return}
 const snapshot=session,inputMode=mode,token=generation,recognizedAt=performance.now();
 swipeFeedback(actionLabels[action]+' · 요청 전달 중');requestBusy=true;buttons.forEach(b=>b.disabled=true);$('hand-control-feedback').textContent='요청 전달 중…';message('요청 전달 중…');
 try{
  if(window.cockpitPreview){const error=window.CockpitDemoControl(action);if(error&&error.includes('주행을 시작한 뒤')){swipeFeedback(error,true);message(error,true)}else{swipeFeedback(actionLabels[action]+' · 미리보기 반영 완료');message('미리보기 · '+actionLabels[action]);closeModal(false)}noticeUntil=performance.now()+3500;return}
  const queued=await post('/api/intent',{session_id:snapshot.session_id,navigation_id:snapshot.navigation.id,action,input_mode:inputMode,request_id:crypto.randomUUID(),transcript,input_started_ms:startedAt,recognized_ms:recognizedAt});
  for(let i=0;i<40;i++){
   await new Promise(r=>setTimeout(r,250));
   if(token!==generation||session?.session_id!==snapshot.session_id)return;
   const reply=await(await fetch('/api/reply?session='+queued.session_id+'&id='+queued.command_id,{cache:'no-store'})).json();
   if(reply.accepted!==undefined){
    swipeFeedback('최근 요청: '+actionLabels[action]+' · '+reply.message,reply.accepted!==true);message(reply.message,reply.accepted!==true);$('hand-control-feedback').textContent=reply.message;
    if(reply.accepted)closeModal(false);noticeUntil=performance.now()+3500;return;
   }
  }
  throw Error('차량 응답이 지연되고 있습니다.');
 }catch(error){swipeFeedback(error.message,true);message(error.message,true);$('hand-control-feedback').textContent=error.message;noticeUntil=performance.now()+4000}
 finally{requestBusy=false;buttons.forEach(b=>b.disabled=!active())}
}
buttons.forEach(b=>b.onclick=()=>sendIntent(b.dataset.handAction));
$('hand-control-close').onclick=closeModal;
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});
function setHover(button){hoverButton=button;buttons.forEach(b=>b.classList.toggle('hand-hover',b===button))}
function pointerPosition(event){
 if(mode!=='gesture_cursor'||modal.hidden||grabbing)return;
 const card=modal.querySelector('section').getBoundingClientRect();
 // Use a generous central camera region; reach all four buttons without arm extremes.
 const x=card.left+Math.min(1,Math.max(0,(event.x-.18)/.64))*card.width;
 const y=card.top+Math.min(1,Math.max(0,(event.y-.15)/.65))*card.height;
 const alpha=.35;cursor=cursor?{x:cursor.x+(x-cursor.x)*alpha,y:cursor.y+(y-cursor.y)*alpha}:{x,y};
 const el=$('hand-cursor');el.hidden=false;el.style.left=cursor.x+'px';el.style.top=cursor.y+'px';
 const hit=document.elementFromPoint(cursor.x,cursor.y)?.closest('[data-hand-action]');setHover(hit&&!hit.disabled?hit:null);
}
function processGesture(data){
 if(!enabled||!workerReady)return;
 const present=data.landmarks?.length===21;
 if(previewState.update(present,data.time,mode))$('input-preview').hidden=false;
 drawGesture(data);
 const open=data.category==='Open_Palm',recognized=open&&data.score>=(mode==='gesture_swipe' ? .65 : .75);
 const gestureLabel=present?(open?'펼친 손바닥':data.category==='Closed_Fist'?'주먹':'손바닥을 카메라로 향해 주세요.'):'손을 카메라 안에 보여 주세요.';
 const pointAction=mode==='gesture_swipe'?classifyPointGesture(data.landmarks):null;
 $('gesture-readout').textContent=mode==='gesture_swipe'?(pointAction?actionLabels[pointAction]+' · 손모양 감지':present?'엄지만 좌우 / 검지만 위아래로 가리켜 주세요.':'손을 카메라 안에 보여 주세요.'):gestureLabel+(present&&open?' · '+Math.round(data.score*100)+'%'+(recognized?' 인식됨':' · 더 또렷하게 펼쳐 주세요.'):'');
 if(!present){$('gesture-motion-progress').style.width='0%';$('gesture-motion').textContent='손목과 다섯 손가락 전체를 보여 주세요.'}
 for(const event of logic.update(data,data.time,mode)){
  if(event.type==='tracking'&&mode==='gesture_swipe'){
   $('gesture-motion-progress').style.width=Math.round(event.progress*100)+'%';
   $('gesture-motion').textContent=event.phase==='release'?'반복 실행 방지 · 손을 펴거나 내려서 손모양을 풀어 주세요.':event.phase==='cooldown'?'잠시 기다린 뒤 다시 가리켜 주세요.':event.phase==='holding'?actionLabels[event.action]+' · 0.5초 유지해 주세요.':'엄지만 좌우 / 검지만 위아래 · 다른 손가락은 접어 주세요.';
  }
  if(event.type==='pointer'&&data.category!=='Closed_Fist')pointerPosition(event);
  if(event.type==='wake'&&['gesture_touch','gesture_cursor'].includes(mode)&&modal.hidden)openModal();
  if(event.type==='pose'&&mode==='gesture_swipe'){swipeFeedback(actionLabels[event.action]+' · 동작 인식됨');sendIntent(event.action,{startedAt:event.startedAt})}
  if(event.type==='fist_start'){frozenButton=hoverButton;grabbing=true;$('hand-cursor').classList.add('grabbing')}
  if(event.type==='select'&&!modal.hidden&&frozenButton&&!frozenButton.disabled)sendIntent(frozenButton.dataset.handAction,{startedAt:event.startedAt});
  if(event.type==='release'){grabbing=false;frozenButton=null;$('hand-cursor').classList.remove('grabbing')}
  if(event.type==='lost'||event.type==='outside'){
   $('hand-cursor').hidden=true;setHover(null);frozenButton=null;grabbing=false;
   if(mode==='gesture_swipe'){$('gesture-motion-progress').style.width='0%';$('gesture-motion').textContent=event.type==='outside'?'손을 화면 중앙에 조금 더 크게 보여 주세요.':'손을 카메라 안에 보여 주세요.'}
  }
 }
}
async function getMedia(constraints,token){
 const pending=navigator.mediaDevices.getUserMedia(constraints);
 pending.then(s=>{if(token!==generation)s.getTracks().forEach(t=>t.stop())}).catch(()=>{});
 let timer;
 try{return await Promise.race([pending,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('카메라·마이크 권한을 확인해 주세요. 응답이 없으면 Chrome 또는 Edge에서 열어 주세요.')),25000)})])}
 finally{clearTimeout(timer)}
}
async function enableGesture(token){
 worker=new Worker('/gesture-worker.js');
 await new Promise((resolve,reject)=>{
  const timeout=setTimeout(()=>reject(Error('손 인식 모델 준비 시간이 초과됐습니다.')),30000);
  worker.onerror=e=>{clearTimeout(timeout);reject(Error(e.message||'손 인식 오류'))};
  worker.onmessage=({data})=>{
   if(data.type==='ready'){clearTimeout(timeout);workerReady=true;resolve()}
   if(data.type==='result'){workerBusy=false;processGesture(data)}
   if(data.type==='error'){clearTimeout(timeout);workerBusy=false;reject(Error(data.message));message(data.message,true)}
  };
  worker.postMessage({type:'init',base:location.origin+'/vendor/mediapipe'});
 });
 message('손 인식 모델 준비 완료 · 카메라 사용을 허용해 주세요.');console.info('Passenger gesture worker: local model and blank-frame inference passed');
 stream=await getMedia({video:{width:{ideal:640},height:{ideal:480},frameRate:{ideal:15,max:20},facingMode:'user'},audio:false},token);
 if(token!==generation){stream.getTracks().forEach(t=>t.stop());stream=null;return}
 video.srcObject=stream;await video.play();
 if(token!==generation)return;
 frameTimer=setInterval(async()=>{
  if(workerBusy||!workerReady||!enabled||video.readyState<2)return;
  workerBusy=true;
  try{
   const bitmap=await createImageBitmap(video);
   if(token!==generation){bitmap.close();workerBusy=false;return}
   worker.postMessage({type:'frame',bitmap,time:performance.now()},[bitmap]);
  }catch(error){workerBusy=false;message(error.message,true)}
 },100);
}
function wavBase64(chunks,sampleRate){
 const total=chunks.reduce((s,c)=>s+c.length,0),source=new Float32Array(total);let at=0;
 for(const c of chunks){source.set(c,at);at+=c.length}
 const count=Math.floor(total*16000/sampleRate),buffer=new ArrayBuffer(44+count*2),view=new DataView(buffer);
 function word(offset,text){[...text].forEach((c,i)=>view.setUint8(offset+i,c.charCodeAt(0)))}
 word(0,'RIFF');view.setUint32(4,36+count*2,true);word(8,'WAVE');word(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,16000,true);view.setUint32(28,32000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);word(36,'data');view.setUint32(40,count*2,true);
 for(let i=0;i<count;i++){const offset=i*sampleRate/16000,a=Math.floor(offset),u=offset-a;const value=source[a]*(1-u)+(source[Math.min(a+1,total-1)]||0)*u;view.setInt16(44+i*2,Math.max(-1,Math.min(1,value))*32767,true)}
 const bytes=new Uint8Array(buffer);let text='';for(let i=0;i<bytes.length;i+=8192)text+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(text);
}
async function recognizeSpeech(chunks,sampleRate,token,startedAt,snapshot){
 voiceBusy=true;message('음성을 해석하고 있어요…');let transcript='';
 try{
  const result=await pollJob(await post('/api/voice/transcribe',{audio:wavBase64(chunks,sampleRate)}),token);
  if(token!==generation||session?.session_id!==snapshot?.session_id||(!window.hongikAssistantMode&&session?.navigation?.id!==snapshot?.navigation?.id))return;
  transcript=result.text;
  if(window.hongikAssistantMode){window.HongikAssistantTranscript?.(transcript);return}
  if(!result.action){message(transcript?'“'+transcript+'” · 감속·가속·좌우 차선 변경 중 하나로 말해 주세요.':'음성을 확인하지 못했어요. 다시 말해 주세요.');noticeUntil=performance.now()+5000;return}
  message('“'+transcript+'”');await sendIntent(result.action,{transcript,startedAt});
 }catch(error){if(token===generation){message(error.message,true);noticeUntil=performance.now()+5000}}
 finally{voiceBusy=false;clearVoice()}
}
async function enableVoice(token){
 const prepare=await post('/api/voice/prepare',{});await pollJob(prepare,token);
 stream=await getMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false},token);
 if(token!==generation){stream.getTracks().forEach(t=>t.stop());stream=null;return}
 ctx=new AudioContext();await ctx.audioWorklet.addModule('/voice-capture-worklet.js');await ctx.resume();
 const sampleRate=ctx.sampleRate;audioNode=new AudioWorkletNode(ctx,'passenger-recorder');
 const source=ctx.createMediaStreamSource(stream),silent=ctx.createGain();silent.gain.value=0;source.connect(audioNode);audioNode.connect(silent).connect(ctx.destination);
 oldAudioMuted=$('audio').muted;$('audio').muted=true;
 audioNode.port.onmessage=({data:chunk})=>{
  if(token!==generation||!enabled||voiceBusy||requestBusy||window.hongikVoiceEnabled||window.passengerTtsSpeaking||Date.now()<(window.passengerTtsQuietUntil||0)||(!window.hongikAssistantMode&&!active())){clearVoice();return}
  const ms=chunk.length/sampleRate*1000,rms=Math.sqrt(chunk.reduce((s,v)=>s+v*v,0)/chunk.length),loud=rms>.018;
  preRoll.push(chunk);if(preRoll.reduce((s,c)=>s+c.length,0)>sampleRate*.3)preRoll.shift();
  if(!speaking){
   if(loud)voicedMs+=ms;else voicedMs=0;
   if(voicedMs>=100){speaking=true;speechSession=session;speechStart=performance.now()-voicedMs;audioChunks=[...preRoll];silentMs=0}
   return;
  }
  audioChunks.push(chunk);silentMs=loud?0:silentMs+ms;
  if(silentMs>=800||performance.now()-speechStart>=6500){
   const chunks=audioChunks;const startedAt=speechStart,snapshot=speechSession;clearVoice();
   recognizeSpeech(chunks,sampleRate,token,startedAt,snapshot);
  }
 };
}
async function toggleDevices(){
 if(mode==='touch')return;
 if(enabled){stopDevices();message(modes[mode].label+' · 꺼짐');return}
 const token=++generation;enabled=true;preparing=true;message('입력 장치를 준비하고 있어요…');
 $('input-device-enable').disabled=true;$('input-toggle').disabled=true;
 try{
  if(mode==='voice')await enableVoice(token);else await enableGesture(token);
  if(token!==generation)return;
  status.classList.add('active');$('input-toggle').textContent='끄기';$('input-device-enable').textContent='입력 장치 끄기';message(modes[mode].label+' · 준비됐어요');
 }catch(error){if(token===generation){stopDevices();message(error.name==='NotAllowedError'?'카메라·마이크 사용을 허용해 주세요.':error.message,true)}}
 finally{preparing=false;$('input-device-enable').disabled=false;$('input-toggle').disabled=false}
}
$('input-device-enable').onclick=toggleDevices;$('input-toggle').onclick=toggleDevices;
$('input-preview-toggle').onclick=()=>{if(!$('input-preview').hidden)hideGesturePreview();else if(enabled){previewState.dismissed=false;$('input-preview').hidden=false}else message('입력 장치를 먼저 켜 주세요.',true)};
$('gesture-preview-close').onclick=hideGesturePreview;
window.addEventListener('pagehide',stopDevices);
window.setPassengerInputMode($('experience-input-mode').value||'touch');


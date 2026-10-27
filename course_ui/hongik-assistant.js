/* Explicit passenger questions only. Local Whisper; grounded CARLA/YOLO facts. */
(()=>{
'use strict';
const $=id=>document.getElementById(id),dialog=$('hongik-dialog'),launch=$('hongik-launch');
window.hongikAssistantMode=true;document.body.classList.add('hongik-mode');
try{window.researchInteractionMode=String(JSON.parse(localStorage.getItem('carla-experience-settings')||'{}').profile||'').startsWith('research_')}catch{window.researchInteractionMode=false}
let state=null,proposal=null,proposalAt=0,busy=false,conversationUntil=0,voiceGeneration=0,stream=null,ctx=null,micOn=false,micPreparing=false,voiceBusy=false;
function voiceStatus(text,phase='waiting'){ $('hongik-mic-status').textContent=text;if($('hongik-voice-badge')){$('hongik-voice-badge').textContent=text;$('hongik-voice-badge').dataset.phase=phase} }
function wakeCue(){if(!ctx||ctx.state!=='running')return;const tone=ctx.createOscillator(),gain=ctx.createGain();tone.frequency.value=660;gain.gain.setValueAtTime(.035,ctx.currentTime);gain.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+.12);tone.connect(gain).connect(ctx.destination);tone.start();tone.stop(ctx.currentTime+.13);window.passengerTtsQuietUntil=Date.now()+200}
const previous=window.CockpitUpdate;
window.CockpitUpdate=data=>{previous?.(data);if(state?.session?.session_id!==data?.session?.session_id){proposal=null;$('hongik-proposal').hidden=true;conversationUntil=0;if(!dialog.hidden)show('주행 연결이 바뀌었습니다. 앞 상황을 다시 물어봐 주세요.')}state=data;if(data.session?.navigation)window.setResearchInteractionMode?.(Boolean(data.session.navigation.research_event));};
function show(text){window.passengerNarration?.setAssistantActive?.(true);dialog.hidden=false;launch.setAttribute('aria-expanded','true');$('hongik-answer').textContent=text;conversationUntil=Date.now()+60000}
function say(text,speechRole='assistant',parts){const n=window.passengerNarration;if(n){n.arm();n.enqueue({kind:'assistant',speechRole,parts,text,priority:3})}}
function open(){show('무엇을 도와드릴까요? 앞 상황이나 남은 거리를 물어보세요.');$('hongik-input').focus()}
function clearProposal(){proposal=null;$('hongik-proposal').hidden=true}
function close(){dialog.hidden=true;launch.setAttribute('aria-expanded','false');clearProposal();conversationUntil=0;window.passengerNarration?.cancel();window.passengerNarration?.setAssistantActive?.(false)}
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'요청을 처리하지 못했습니다.');return d}
async function ask(text){
 if(busy||!text.trim())return;busy=true;clearProposal();show('주변 차량과 현재 상황을 확인하고 있어요.');$('hongik-question').textContent='나 · '+text;$('hongik-sources').textContent='';$('hongik-details').hidden=true;$('hongik-send').disabled=true;
 try{
  const sid=state?.session?.session_id;
  const answer=window.cockpitPreview?await post('/api/assistant/preview',{text,state:{connected:true,ego:state.ego,actors:state.actors,route:state.route?{destination:state.route.destination,remaining_m:state.route.remaining_m}:null,session:state.session}}):await post('/api/assistant/ask',{text,session_id:sid});
  if(sid!==state?.session?.session_id)throw Error('주행 연결이 바뀌었습니다. 다시 물어봐 주세요.');
  show(answer.text);$('hongik-sources').textContent=(answer.sources||[]).join(' · ');
  $('hongik-evidence').textContent=(answer.details||[]).join(' ');$('hongik-details').hidden=!answer.details?.length;
  proposal=answer.proposal;proposalAt=Date.now();$('hongik-proposal').hidden=!proposal;
  if(proposal)$('hongik-confirm').textContent=proposal.label;
  say(answer.spoken_text||answer.text,answer.speech_role||'briefing',answer.speech_parts);
 }catch(e){show(e.message)}finally{busy=false;$('hongik-send').disabled=false}
}
async function confirm(){
 if(busy)return;
 if(!proposal||Date.now()-proposalAt>45000){clearProposal();show('제안 시간이 지났습니다. 앞 상황을 다시 물어봐 주세요.');return}
 busy=true;$('hongik-confirm').disabled=true;
 try{
  if(proposal.preview){
   if(!window.cockpitPreview||state?.session?.navigation?.status!=='offered')throw Error('미리보기 상황이 바뀌었습니다. 다시 질문해 주세요.');
   const result=window.CockpitDemoControl(proposal.action);clearProposal();show('[미리보기] '+result);say(result);return;
  }
  const sid=state?.session?.session_id,q=await post('/api/assistant/confirm',{token:proposal.token,session_id:sid});
  clearProposal();show('차량에 요청을 전달했습니다. 응답을 확인하고 있어요.');
  for(let i=0;i<40;i++){
   await new Promise(r=>setTimeout(r,250));if(sid!==state?.session?.session_id)throw Error('주행 연결이 바뀌었습니다.');
   const result=await(await fetch(`/api/reply?session=${q.session_id}&id=${q.command_id}`,{cache:'no-store'})).json();
   if(result.accepted!==undefined){show(result.message+(result.accepted?'':' 앞 상황을 다시 물으면 새 제안을 확인할 수 있어요.'));say(result.message);return}
  }
  show('차량 응답이 지연됩니다. 현재 차량 상태를 확인해 주세요.');
 }catch(e){clearProposal();show(e.message)}finally{busy=false;$('hongik-confirm').disabled=false}
}
function transcript(text){
 const {called,question}=parseHongikWake(text);
 if(called){window.passengerNarration?.cancel();if(dialog.hidden)open();conversationUntil=Date.now()+60000;if(!question){show('네, 말씀하세요.');say('네, 말씀하세요.');voiceStatus('Qwen · 응답 중','speaking');return true}}
 if(!called&&(dialog.hidden||Date.now()>conversationUntil))return false;
 if(!question)return true;
 const value=question.replace(/[\s,.!?]/g,'');
 if(/취소|하지마|하지말|그대로|괜찮아|아니/.test(value)){clearProposal();show('현재 주행을 유지합니다.');say('현재 주행을 유지합니다.');return true}
 if(['응','네','좋아','그래','응해줘','네해줘','그래해줘','좋아해줘','해줘','해주세요','추월해줘','왼쪽으로추월해줘','감속해줘'].includes(value)){confirm();return true}
 ask(question);return true;
}
window.HongikAssistantTranscript=transcript;
launch.onclick=()=>{if(dialog.hidden){open();window.passengerNarration?.cancel();if(!micOn&&!micPreparing)toggleMic()}else close()};$('hongik-close').onclick=close;
$('hongik-form').onsubmit=e=>{e.preventDefault();const text=$('hongik-input').value;$('hongik-input').value='';transcript(text)};
$('hongik-confirm').onclick=confirm;$('hongik-cancel').onclick=()=>{clearProposal();show('현재 주행을 유지합니다.')};
$('hongik-details').hidden=true;$('hongik-quick').onclick=()=>ask('현재 앞 상황이 불안해 보여. 상황을 알려줘');
async function job(queued,token){for(let i=0;i<600;i++){if(token!==voiceGeneration)throw Error('음성 입력을 종료했습니다.');const r=await(await fetch('/api/voice/job?id='+queued.job_id,{cache:'no-store'})).json();if(r.error)throw Error(r.error);if(r.status==='complete')return r;await new Promise(r=>setTimeout(r,100))}throw Error('음성 처리가 지연됩니다.')}
function wav(chunks,rate){const total=chunks.reduce((n,c)=>n+c.length,0),source=new Float32Array(total);let at=0;for(const c of chunks){source.set(c,at);at+=c.length}const count=Math.floor(total*16000/rate),buffer=new ArrayBuffer(44+count*2),v=new DataView(buffer);const word=(o,t)=>[...t].forEach((c,i)=>v.setUint8(o+i,c.charCodeAt(0)));word(0,'RIFF');v.setUint32(4,36+count*2,true);word(8,'WAVE');word(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,16000,true);v.setUint32(28,32000,true);v.setUint16(32,2,true);v.setUint16(34,16,true);word(36,'data');v.setUint32(40,count*2,true);for(let i=0;i<count;i++){const x=i*rate/16000,a=Math.floor(x),u=x-a,s=source[a]*(1-u)+(source[Math.min(a+1,total-1)]||0)*u;v.setInt16(44+i*2,Math.max(-1,Math.min(1,s))*32767,true)}let binary='';const bytes=new Uint8Array(buffer);for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(binary)}
function stopMic(){voiceGeneration++;micOn=false;window.hongikVoiceEnabled=false;stream?.getTracks().forEach(t=>t.stop());stream=null;ctx?.close().catch(()=>{});ctx=null;$('hongik-mic').setAttribute('aria-pressed','false');$('hongik-mic').textContent='“홍익아” 호출 켜기';$('hongik-call-toggle')?.setAttribute('aria-pressed','false');voiceStatus('호출 꺼짐','off')}
async function toggleMic(){
 if(window.researchInteractionMode)return;
 if(micPreparing)return;if(micOn){stopMic();return}micPreparing=true;$('hongik-mic').disabled=true;const token=++voiceGeneration;
 try{
  voiceStatus('호출 준비 중…','preparing');await job(await post('/api/voice/prepare',{}),token);
  if(token!==voiceGeneration||window.researchInteractionMode)return;
  stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
  if(token!==voiceGeneration){stream.getTracks().forEach(t=>t.stop());return}
  ctx=new AudioContext();await ctx.audioWorklet.addModule('/voice-capture-worklet.js');
  const rate=ctx.sampleRate,node=new AudioWorkletNode(ctx,'passenger-recorder'),source=ctx.createMediaStreamSource(stream),silent=ctx.createGain();silent.gain.value=0;source.connect(node);node.connect(silent).connect(ctx.destination);
  const capture=new HongikSpeechCapture(rate);
  micOn=true;window.hongikVoiceEnabled=true;$('hongik-mic').setAttribute('aria-pressed','true');$('hongik-mic').textContent='호출 마이크 끄기';$('hongik-call-toggle')?.setAttribute('aria-pressed','true');voiceStatus('홍익아 · 호출 대기');
  const contextStatus=()=>{if(token!==voiceGeneration||!micOn)return;voiceStatus(ctx?.state==='running'?'홍익아 · 호출 대기':'화면을 한 번 누르면 호출이 시작돼요.',ctx?.state==='running'?'waiting':'gesture')};
  ctx.onstatechange=contextStatus;contextStatus();
  // Autoplay policies can leave resume pending until a user gesture; do not block setup.
  ctx.resume().then(contextStatus).catch(()=>{if(token===voiceGeneration)voiceStatus('화면을 한 번 누르면 호출이 시작돼요.','gesture')});
  node.port.onmessage=async({data:c})=>{
   if(document.visibilityState==='hidden'||token!==voiceGeneration||!micOn||voiceBusy||busy||window.passengerTtsSpeaking||Date.now()<(window.passengerTtsQuietUntil||0)){capture.reset();if(micOn&&window.passengerTtsSpeaking)voiceStatus('안내 중 · 버튼으로 말하기','speaking');return}
   const detected=capture.push(c);
   if(detected.phase==='listening'){voiceStatus('듣고 있어요.','listening');return}
   if(detected.phase!=='complete'){voiceStatus(!dialog.hidden&&Date.now()<conversationUntil?'이어 말해 주세요.':'홍익아 · 호출 대기');return}
   const audio=wav(detected.chunks,rate);voiceBusy=true;voiceStatus('들은 말을 확인 중…','processing');
   try{const result=await job(await post('/api/voice/transcribe',{audio,mode:dialog.hidden?'wake':'conversation'}),token);if(token===voiceGeneration){if($('hongik-heard'))$('hongik-heard').textContent=result.text?'들은 말 · '+result.text:'말소리를 확인하지 못했어요.';transcript(result.text||'')}}
   catch(e){if(token===voiceGeneration)voiceStatus(e.message,'error')}
   finally{voiceBusy=false;if(token===voiceGeneration)voiceStatus(!dialog.hidden&&Date.now()<conversationUntil?'이어 말해 주세요.':'홍익아 · 호출 대기')}
  };
 }catch(e){stopMic();voiceStatus(e.name==='NotAllowedError'?'마이크 사용을 허용해 주세요.':e.message,'error')}
 finally{micPreparing=false;$('hongik-mic').disabled=false}
}
$('hongik-mic').onclick=toggleMic;window.addEventListener('pagehide',stopMic);
$('hongik-call-toggle')?.addEventListener('click',toggleMic);
$('hongik-listen-now')?.addEventListener('click',()=>{window.passengerNarration?.cancel();window.passengerTtsQuietUntil=Date.now()+200;if(!micOn&&!micPreparing)toggleMic();else if(micOn)voiceStatus('이어 말해 주세요.','listening')});
let automaticStartPending=true;
function startAutomaticCall(){
 if(window.researchInteractionMode||!automaticStartPending||document.visibilityState==='hidden'||typeof navigator==='undefined')return;
 automaticStartPending=false;
 if(!navigator.mediaDevices?.getUserMedia){voiceStatus('이 화면에서는 마이크를 사용할 수 없어요.','error');return}
 toggleMic();
}
window.setResearchInteractionMode=enabled=>{
 const changed=window.researchInteractionMode!==Boolean(enabled);window.researchInteractionMode=Boolean(enabled);
 if(enabled){if(micOn||micPreparing)stopMic();dialog.hidden=true;clearProposal()}else if(changed){automaticStartPending=true;startAutomaticCall()}
};
function resumeCallFromGesture(){if(micOn&&ctx?.state==='suspended')ctx.resume().catch(()=>voiceStatus('마이크 시작을 다시 눌러 주세요.','error'))}
document.addEventListener('pointerdown',resumeCallFromGesture);
document.addEventListener('keydown',resumeCallFromGesture);
document.addEventListener('visibilitychange',startAutomaticCall);
voiceStatus('호출 준비 중…','preparing');
startAutomaticCall();
})();

/* Korean speech from CARLA route/scenario state, never a YOLO risk claim. */
(()=>{
'use strict';
globalThis.PASSENGER_VOICE_UI='split-voice-20261013';
class NavigationVoicePlan {
 constructor(){this.reset()}
 reset(){this.context=null;this.routeKey=null;this.previous=null;this.started=false;this.arrived=false;this.seen=new Set();this.offRoute=false}
 update(data,route=data?.route){
  if(!data?.connected)return [];
  const session=data.session,nav=session?.navigation||{};
  const context=[data.map,data.ego?.id,session?.session_id||''].join(':');
  if(this.context!==context){this.reset();this.context=context}
  if(session&&(session.stage==='ready'||nav.status==='ready'||['stopped','finished'].includes(session.stage)))return [];
  const key=route?.destination?.id??null;
  if(key!==this.routeKey){this.routeKey=key;this.previous=null;this.started=false;this.arrived=false;this.offRoute=false}
  const messages=[];
  const event=(kind,text,priority=0)=>({kind,text,priority});
  if(!globalThis.hongikAssistantMode&&nav.status==='offered'&&nav.id&&!this.seen.has(nav.id)){
   this.seen.add(nav.id);
   messages.push(event('situation',[nav.title,nav.body].filter(Boolean).join(' '),2));
  }
  if(route?.off_route){
   if(!this.offRoute)messages.push(event('route','경로에서 벗어났습니다. 목적지를 다시 확인해 주세요.',1));
   this.offRoute=true;return messages;
  }
  this.offRoute=false;
  const remaining=route?.remaining_m;
  const physicalJourney=[6,7].includes(session?.scenario);
  if(nav.status==='arrived'||(!physicalJourney&&route?.arrived)){
   if(!this.arrived){this.arrived=true;messages.push(event('arrival',`${route?.destination?.name||'목적지'}에 도착했습니다.`,3))}
   return messages.filter(m=>m.kind==='arrival');
  }
  if(!Number.isFinite(remaining)||remaining<0||this.arrived)return messages;
  const distanceText=m=>m>=1000&&m%1000===0?`${m/1000}킬로미터`:`${m}미터`;
  if(!this.started){
   this.started=true;
   const rounded=Math.max(50,Math.round(remaining/50)*50);
   messages.push(event('route',`${route.destination.name}까지 안내를 시작합니다. 목적지까지 약 ${distanceText(rounded)} 남았습니다.`));
  }else{
   // A delayed frame announces only the closest crossed milestone, never a backlog.
   const crossed=[1000,700,500,300,100,50].filter(m=>this.previous>m&&remaining<=m);
   if(crossed.length){const m=crossed.at(-1);messages.push(event('distance',m===50?'잠시 후 목적지에 도착합니다.':`목적지까지 ${distanceText(m)} 남았습니다.`))}
  }
  this.previous=Math.min(this.previous??remaining,remaining);
  return messages;
 }
}
class NavigationVoice {
 constructor({synth=globalThis.speechSynthesis,Utterance=globalThis.SpeechSynthesisUtterance,audio,onStatus=()=>{}}={}){
  this.synth=synth;this.Utterance=Utterance;this.audio=audio;this.onStatus=onStatus;this.backend=null;this.provider='browser';
  this.plan=new NavigationVoicePlan();this.queue=[];this.current=null;this.enabled=true;this.armed=false;this.generation=0;this.musicVolume=audio?.volume??.45;
  this.lastData=null;this.lastRoute=null;this.watchdog=null;this.assistantActive=false;this.pendingArrival=null;
  this.turnController=null;this.turnRelease=null;this.turnPromise=null;this.pendingUnlock=null;this.tabId=Date.now()+':'+Math.random();
  this.channel=globalThis.document&&globalThis.navigator&&globalThis.BroadcastChannel?new BroadcastChannel('carla-passenger-speech-v1'):null;
  if(this.channel)this.channel.onmessage=({data})=>{if(data?.type==='claim'&&data.tab!==this.tabId)this.cancel()};
  globalThis.document?.addEventListener('visibilitychange',()=>{if(!this.visible())this.cancel()});
  globalThis.addEventListener?.('pagehide',()=>{this.cancel();this.channel?.close()});
 }
 visible(){return globalThis.document?.visibilityState!=='hidden'}
 claim(){this.channel?.postMessage({type:'claim',tab:this.tabId})}
 releaseTurn(){this.turnController?.abort();this.turnController=null;const release=this.turnRelease;this.turnRelease=null;if(this.turnPromise){this.pendingUnlock=this.turnPromise.catch(()=>{});this.turnPromise=null}release?.()}
 setAssistantActive(value){
  if(this.assistantActive===value)return;this.assistantActive=value;
  if(value){this.claim();this.cancel()}
  else if(this.pendingArrival){const message=this.pendingArrival;this.pendingArrival=null;this.enqueue(message)}
 }
 requestTurn(current,token,start){
  const locks=globalThis.document&&globalThis.navigator?.locks;
  if(!locks?.request){start();return}
  const controller=new AbortController();this.turnController=controller;
  const interactive=['assistant','test'].includes(current.message.kind);
  // One playback slot across same-origin tabs. Routine navigation never builds a stale backlog.
  const acquire=()=>{this.turnPromise=locks.request('carla-passenger-speech-v1',interactive?{signal:controller.signal}:{ifAvailable:true},lock=>{
   if(token!==this.generation||this.current!==current)return;
   if(!lock){this.current=null;this.turnController=null;this.mix();this.pump();return}
   return new Promise(resolve=>{this.turnRelease=resolve;start()});
  }).catch(error=>{if(token===this.generation&&this.current===current){this.cancel();this.onStatus('음성 재생 권한을 얻지 못했습니다. '+error.message)}})};
  // Wait for our previous callback to release the slot before requesting an automatic turn.
  if(this.pendingUnlock){const pending=this.pendingUnlock;this.pendingUnlock=null;pending.then(()=>{if(token===this.generation&&this.current===current)acquire()})}else acquire();
 }
 setProvider(value){this.cancel();this.provider=['browser','supertonic','qwen'].includes(value)?value:'qwen';this.voiceLabel=this.provider==='supertonic'?'밝은 안내 · Supertonic F3':'Sohee · Qwen3-TTS';this.backend=this.provider!=='browser'&&globalThis.QwenSpeechTransport?new globalThis.QwenSpeechTransport({provider:this.provider}):null;this.onStatus(this.backend?this.voiceLabel:'기본 Windows 음성')}
 setMusicVolume(volume){this.musicVolume=Math.max(0,Math.min(1,volume));this.mix()}
 mix(){if(this.audio)this.audio.volume=this.musicVolume*(this.current?.started?.value ? .25 : 1)}
 cancel(){
  const activeBackend=this.current?.backend;
  this.generation++;clearTimeout(this.watchdog);this.queue=[];this.current=null;
  activeBackend?.cancel();this.synth?.cancel();this.backend?.cancel();
  this.releaseTurn();
  globalThis.passengerTtsSpeaking=false;globalThis.passengerTtsQuietUntil=Date.now()+650;this.mix();
 }
 reset(){this.cancel();this.pendingArrival=null;this.plan.reset()}
 setEnabled(value){this.enabled=value;this.cancel();this.plan.reset();if(value&&this.armed&&this.lastData)this.update(this.lastData,this.lastRoute)}
 arm(){if(this.armed)return;this.armed=true;if(this.lastData)this.update(this.lastData,this.lastRoute)}
 update(data,route=data?.route){
  this.lastData=data;this.lastRoute=route;
  if(!data?.connected){if(this.current?.message.kind!=='test')this.cancel();return}
  const context=[data.map,data.ego?.id,data.session?.session_id||''].join(':');
  if(this.plan.context&&this.plan.context!==context)this.reset();
  if(this.plan.routeKey!==null&&this.plan.routeKey!==(route?.destination?.id??null)){this.cancel();this.pendingArrival=null}
  if(!this.enabled||!this.armed)return;
  const nav=data.session?.navigation;
  if(['ready','stopped','finished'].includes(data.session?.stage)||nav?.status==='ready'){
   if(!['test','assistant'].includes(this.current?.message.kind)&&(this.current||this.queue.length))this.cancel();return;
  }
  // Drop queued suggestions as soon as the passenger resolves their situation.
  this.queue=this.queue.filter(m=>m.kind!=='situation'||m.navigationId===nav?.id&&nav.status==='offered');
  if(this.current?.message.kind==='situation'&&(this.current.message.navigationId!==nav?.id||nav.status!=='offered'))this.cancel();
  for(const message of this.plan.update(data,route))this.enqueue({...message,navigationId:nav?.id});
 }
 enqueue(message){
  if(!this.enabled||!this.armed||!message.text)return;
  if(!this.visible())return;
  const interactive=['assistant','test'].includes(message.kind);
  if(this.assistantActive&&!interactive){if(message.kind==='arrival')this.pendingArrival=message;return}
  if(!this.backend&&(!this.synth||!this.Utterance)){this.onStatus('이 브라우저는 음성 안내를 지원하지 않습니다.');return}
  if(interactive){this.claim();this.cancel()}
  if(message.priority>=(this.current?.message.priority??Infinity)+1)this.cancel();
  this.queue=this.queue.filter(m=>!(message.kind==='distance'&&m.kind==='distance'));
  if(message.kind==='arrival')this.queue=[];
  this.queue.push(message);this.queue.sort((a,b)=>b.priority-a.priority);this.pump();
 }
 pump(){
  if(this.current||!this.queue.length||!this.enabled)return;
  if(!this.visible()){this.queue=[];return}
  const message=this.queue.shift(),token=this.generation;
  const current={message,started:{value:false}};this.current=current;
  const assistant=message.kind==='assistant';
  const briefing=assistant&&message.speechRole==='briefing';
  current.backend=assistant?(globalThis.QwenSpeechTransport?new globalThis.QwenSpeechTransport({provider:'qwen'}):null):this.backend;
  current.voiceLabel=assistant?(briefing?'홍익 AI · Qwen 저장 브리핑':'홍익 AI · Qwen Sohee'):this.voiceLabel;
  if(assistant&&!current.backend){this.current=null;this.onStatus('AI 목소리를 불러오지 못했습니다. 화면을 새로고침해 주세요.');return}
  this.requestTurn(current,token,()=>{if(token===this.generation&&this.current===current){if(current.backend)this.pumpQwen(message,token,current);else this.pumpBrowser(message,token,current)}});
 }
 pumpBrowser(message,token,current){
  const utterance=new this.Utterance(message.text);
  const voices=this.synth.getVoices();
  utterance.voice=voices.find(v=>/^ko[-_]/i.test(v.lang)&&v.localService)||voices.find(v=>/^ko[-_]/i.test(v.lang))||null;
  utterance.lang='ko-KR';utterance.rate=1;utterance.pitch=1;utterance.volume=1;
  current.utterance=utterance;
  const done=error=>{
   if(token!==this.generation||this.current!==current)return;
   clearTimeout(this.watchdog);this.current=null;globalThis.passengerTtsSpeaking=false;
   this.releaseTurn();
   globalThis.passengerTtsQuietUntil=Date.now()+650;this.mix();
   this.onStatus(error?'음성 안내를 재생하지 못했습니다. 안내 듣기를 눌러 주세요.':'한국어 음성 안내 · 켜짐');this.pump();
  };
  // Block microphone capture before playback begins, including synthesis startup.
  globalThis.passengerTtsSpeaking=true;
  utterance.onstart=()=>{if(token!==this.generation)return;current.started.value=true;this.mix();this.onStatus(message.text)};
  utterance.onend=()=>done(false);utterance.onerror=()=>done(true);
  this.watchdog=setTimeout(()=>{if(token===this.generation){this.synth.cancel();done(true)}},Math.max(15000,message.text.length*500));
  try{this.synth.speak(utterance)}catch{done(true)}
 }
 pumpQwen(message,token,current){
  const backend=current.backend,label=current.voiceLabel;
  this.onStatus(label+' · 음성 준비 중');
  const valid=()=>token===this.generation&&this.current===current;
  const done=error=>{if(!valid())return;clearTimeout(this.watchdog);this.current=null;this.releaseTurn();globalThis.passengerTtsSpeaking=false;globalThis.passengerTtsQuietUntil=Date.now()+650;this.mix();this.onStatus(error?label+' 오류: '+error.message:label+' · 켜짐');this.pump()};
  this.watchdog=setTimeout(()=>{if(valid()){backend.cancel();done(Error('음성 생성 또는 재생 시간 초과'))}},180000);
  backend.speak(message.text,{kind:message.kind,speechRole:message.speechRole,parts:message.parts,onstart:()=>{if(valid()){current.started.value=true;globalThis.passengerTtsSpeaking=true;this.mix();this.onStatus(message.text)}},onend:()=>done(null),onerror:done});
 }
 test(){this.arm();this.enqueue({kind:'test',text:'음성 안내를 시작합니다. 목적지까지 500미터 남았습니다.',priority:3})}
}
globalThis.NavigationVoicePlan=NavigationVoicePlan;globalThis.NavigationVoice=NavigationVoice;
})();

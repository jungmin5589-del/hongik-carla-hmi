/* Native city cases: staged choices, no ETA, synthetic exterior/mechanical audio. */
addEventListener('DOMContentLoaded',()=>{
 let session=null,lastNotice=0,lastKnock=0,ctx=null,mechanical=null,outside=null,lastStep=0,lastVoiceEnd=-1000;
 const speechGate=new CityExteriorSound.SpeechGate();
 const impacts=new Set();
 const client=crypto.randomUUID();
 const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('nurec-hongik-sohee'):null;
 if(channel)channel.onmessage=()=>{outside?.pause()};
 function unlock(){const C=window.AudioContext||window.webkitAudioContext;if(C&&!ctx)ctx=new C();ctx?.resume().catch(()=>{})}
 document.addEventListener('pointerdown',unlock);document.addEventListener('click',unlock);document.addEventListener('keydown',unlock);
 function stop(){outside?.pause();outside?.remove();outside=null;for(const hit of impacts){try{hit.stop()}catch{}}impacts.clear();if(mechanical){mechanical.source.stop();mechanical=null}}
 function ownsSound(){
  if(document.visibilityState!=='visible'||ctx?.state!=='running')return false;
  try{const old=JSON.parse(localStorage.getItem('city-audio-owner')||'null'),now=Date.now();if(old&&old.id!==client&&old.until>now)return false;localStorage.setItem('city-audio-owner',JSON.stringify({id:client,until:now+1600}));return true}catch{return true}
 }
 function voice(key){
  outside?.pause();outside?.remove();outside=new Audio('/api/narration/audio/'+key+'.wav');outside.id='city-exterior-audio';outside.hidden=true;document.body.appendChild(outside);
  outside.dataset.voiceKey=key;outside.onended=()=>{lastVoiceEnd=performance.now()};
  const source=ctx.createMediaElementSource(outside),filter=ctx.createBiquadFilter(),panner=ctx.createStereoPanner(),gain=ctx.createGain(),compressor=ctx.createDynamicsCompressor();
  filter.type='lowpass';filter.frequency.value=2600;panner.pan.value=.8;gain.gain.value=key==='city_notice'?.45:.68;
  compressor.threshold.value=-16;compressor.ratio.value=3;compressor.attack.value=.008;compressor.release.value=.15;
  source.connect(filter).connect(compressor).connect(panner).connect(gain).connect(ctx.destination);outside.play().catch(()=>{});
 }
 function footsteps(){
  if(ctx.currentTime-lastStep<.6)return;lastStep=ctx.currentTime;
  const o=ctx.createOscillator(),g=ctx.createGain(),p=ctx.createStereoPanner();o.frequency.setValueAtTime(105,ctx.currentTime);o.frequency.exponentialRampToValueAtTime(45,ctx.currentTime+.10);
  g.gain.setValueAtTime(.035,ctx.currentTime);g.gain.exponentialRampToValueAtTime(.001,ctx.currentTime+.12);p.pan.value=.8;
  o.connect(g).connect(p).connect(ctx.destination);o.start();o.stop(ctx.currentTime+.13);
 }
 function startMechanical(){
  if(mechanical)return;
  const rate=ctx.sampleRate,buffer=ctx.createBuffer(1,rate*4,rate),a=buffer.getChannelData(0);
  let seed=7231;for(let i=0;i<a.length;i++){seed=(seed*1664525+1013904223)>>>0;const noise=(seed/4294967296)*2-1,t=i/rate;const hit=Math.exp(-((t%.23)/.025));a[i]=.12*Math.sin(t*2*Math.PI*48)+noise*.4*hit;}
  const source=ctx.createBufferSource(),gain=ctx.createGain(),filter=ctx.createBiquadFilter();source.buffer=buffer;source.loop=true;filter.type='lowpass';filter.frequency.value=2100;
  source.connect(filter).connect(gain).connect(ctx.destination);gain.gain.value=.14;source.start();mechanical={source,gain};
 }
 const poll=setInterval(()=>{
  if(!window.CockpitUpdate)return;clearInterval(poll);const update=window.CockpitUpdate;
  window.CockpitUpdate=data=>{
   update(data);const s=data.nurec?.scenario,city=['pedestrian_yield','city_carpool','city_rattle'].includes(s?.id);
   document.body.classList.toggle('city-study',city);
   if(!city){stop();session=null;return}
   const $=id=>document.getElementById(id);
   if(session!==s.session){stop();session=s.session;speechGate.reset();lastNotice=0;lastKnock=0;lastVoiceEnd=-1000}
   const event=data.session.navigation.research_event;
   $('route-eta').textContent='—';$('route-time').textContent='—';$('route-distance').textContent='—';
   $('route-name').textContent=s.completed?'체험 종료':data.session.navigation.map_label;
   $('map-name').textContent=s.id==='pedestrian_yield'?'신호 없는 횡단보도':s.id==='city_carpool'?'동승자 대기 구역':'이상음 주행';
   $('turn-instruction').textContent=s.completed?'대응 결과 확인 완료':s.id==='pedestrian_yield'?({approach:'횡단보도로 접근',mutual_wait:'보행자 횡단 여부 확인 중',crossing:'보행자 횡단 중 · 정차',clearance:'횡단 구간 확인 중',resume:'양보 후 다시 출발',finishing:'체험 마무리',complete:'체험 종료'})[s.yielding.phase]:s.id==='city_carpool'?'문 닫힘 유지 · 동승자 대기':'차량 상태 확인 중';
   $('route-note').textContent=s.outcome.summary||event.description;
   $('drive-mode').textContent=s.completed?'체험 종료':data.nurec.speed_kph<.5?'정차 중':'주행 중';
   const enabled=data.nurec.mode==='auto'&&!s.completed&&ownsSound();
   const speaking=Boolean($('research-sohee-audio')&&!$('research-sohee-audio').paused);
   if(speaking)lastVoiceEnd=performance.now();
   const c=s.context;
   if(!enabled){speechGate.offer(c?.exterior?.voice_cue,s.elapsed_s,false);lastKnock=c?.exterior?.knock_count||0;stop();return}
   speechGate.offer(c?.exterior?.voice_cue,s.elapsed_s,!c?.actor_retreat);
   if(speaking||(c?.actor_retreat&&outside?.dataset.voiceKey!=='city_notice'))outside?.pause();
   const nextVoice=speechGate.take(s.elapsed_s,speaking||Boolean(outside&&!outside.paused&&!outside.ended)||performance.now()-lastVoiceEnd<800);
   if(nextVoice)voice(nextVoice);
   const count=c?.exterior?.knock_count||0;
   if(count>lastKnock){lastKnock=count;if(c.exterior.at_window&&window.CityExteriorSound){const hit=CityExteriorSound.knock(ctx,speaking);impacts.add(hit);hit.onended=()=>impacts.delete(hit)}}
   if(c?.announcement_count>lastNotice){lastNotice=c.announcement_count;speechGate.offer(c?.exterior?.voice_cue,s.elapsed_s,false);outside?.pause();channel?.postMessage({claim:'city-exterior-notice'});voice('city_notice')}
   if(s.id==='city_carpool'&&data.actors.some(a=>a.kind==='pedestrian'&&a.speed_kmh>.3))footsteps();
   if(c?.rattle_active){startMechanical();mechanical.gain.gain.setTargetAtTime(speaking?.025:.14,ctx.currentTime,.15)}
   else if(mechanical){mechanical.source.stop();mechanical=null}
  };
 },100);
 document.addEventListener('visibilitychange',()=>{if(document.visibilityState!=='visible')stop()});
 addEventListener('pagehide',()=>{stop();ctx?.close();channel?.close()});
});

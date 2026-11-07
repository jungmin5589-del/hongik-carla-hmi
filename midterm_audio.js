/* Existing cached voices and recorded mechanical sound, without classic DOM hooks. */
addEventListener('DOMContentLoaded',()=>{
 let session=null,ctx=null,mechanical=null,outside=null,outsideGain=null,outsidePan=null,outsideFilter=null,lastNotice=0,lastKnock=0,lastHorn=0,lastStep=0,lastVoiceEnd=-1000;
 const client=crypto.randomUUID(),gate=new CityExteriorSound.SpeechGate(),hits=new Set();
 const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('nurec-hongik-sohee'):null;
 if(channel)channel.onmessage=()=>outside?.pause();
 function unlock(){const C=window.AudioContext||window.webkitAudioContext;if(C&&!ctx)ctx=new C();ctx?.resume().catch(()=>{});if(ctx)UnderbodySound.prepare(ctx).catch(()=>{});}
 document.addEventListener('pointerdown',unlock);document.addEventListener('keydown',unlock);
 function stop(){outside?.pause();outside?.remove();outside=null;mechanical?.dispose();mechanical=null;for(const hit of hits){try{hit.stop()}catch{}}hits.clear();}
 function owns(){if(document.visibilityState!=='visible'||ctx?.state!=='running')return false;try{const now=Date.now(),old=JSON.parse(localStorage.getItem('city-audio-owner')||'null');if(old&&old.id!==client&&old.until>now)return false;localStorage.setItem('city-audio-owner',JSON.stringify({id:client,until:now+1600}));return true}catch{return true}}
 function voice(key){outside?.pause();outside?.remove();outside=new Audio(window.HongikLocale?.audioURL(key)||'/api/narration/audio/'+key+'.wav');outside.id='city-exterior-audio';outside.hidden=true;document.body.append(outside);outside.onended=()=>{lastVoiceEnd=performance.now()};const source=ctx.createMediaElementSource(outside),filter=ctx.createBiquadFilter(),pan=ctx.createStereoPanner(),gain=ctx.createGain();filter.type='lowpass';filter.frequency.value=2600;pan.pan.value=.8;gain.gain.value=.25;outsideGain=gain;outsidePan=pan;outsideFilter=filter;source.connect(filter).connect(pan).connect(gain).connect(ctx.destination);outside.play().catch(()=>{});}
 function tone(freq,duration,gainValue){const o=ctx.createOscillator(),g=ctx.createGain();o.type='sawtooth';o.frequency.value=freq;g.gain.setValueAtTime(gainValue,ctx.currentTime);g.gain.exponentialRampToValueAtTime(.001,ctx.currentTime+duration);o.connect(g).connect(ctx.destination);o.start();o.stop(ctx.currentTime+duration);}
 const update=window.CockpitUpdate;
 window.CockpitUpdate=data=>{
  update(data);const s=data.nurec?.scenario;if(!s)return;
  const c=s.context;if(session!==s.session){stop();gate.reset();session=s.session;lastHorn=s.horn_count||0;lastNotice=0;lastKnock=0;lastVoiceEnd=-1000;}
  const enabled=data.nurec.mode==='auto'&&!s.completed&&owns(),speaking=document.getElementById('research-sohee-audio')?.paused===false;
  if(speaking)lastVoiceEnd=performance.now();
  if(!enabled){gate.offer(c?.exterior?.voice_cue,s.elapsed_s,false);lastKnock=c?.exterior?.knock_count||0;lastHorn=s.horn_count||0;stop();return;}
  if(s.horn_count>lastHorn){lastHorn=s.horn_count;if(!document.getElementById('nurec-start')){tone(340,.38,.035);tone(425,.4,.03);}}
  gate.offer(c?.exterior?.voice_cue,s.elapsed_s,!c?.actor_retreat);
  if(speaking||c?.actor_retreat)outside?.pause();
  const next=gate.take(s.elapsed_s,speaking||Boolean(outside&&!outside.paused&&!outside.ended)||performance.now()-lastVoiceEnd<800);if(next)voice(next);
  if(outside&&!outside.paused&&c?.exterior&&outsideGain){const ex=c.exterior,d=Math.max(1,Math.hypot((ex.local_forward_m||0)-.9,ex.local_right_m||0));outsideGain.gain.setTargetAtTime(Math.max(.16,Math.min(.68,1.6/d)),ctx.currentTime,.15);outsidePan.pan.setTargetAtTime(Math.max(-.95,Math.min(.95,(ex.local_right_m||0)/d)),ctx.currentTime,.15);outsideFilter.frequency.setTargetAtTime(1200+1400*Math.min(1,4/d),ctx.currentTime,.15);}
  const count=c?.exterior?.knock_count||0;if(count>lastKnock){lastKnock=count;if(c.exterior.at_window){const hit=CityExteriorSound.knock(ctx,speaking);hits.add(hit);hit.onended=()=>hits.delete(hit);}}
  const notices=s.yielding?.announcement_count||c?.announcement_count||0;
  if(notices>lastNotice){lastNotice=notices;channel?.postMessage({claim:'external-announcement'});document.getElementById('research-sohee-audio')?.pause();voice(s.yielding?'yield_notice':'city_taxi_warning');}
  if(c&&data.actors?.some(a=>a.kind==='pedestrian'&&a.speed_kmh>.3)&&ctx.currentTime-lastStep>.6){lastStep=ctx.currentTime;tone(85,.1,.012);}
  if(c?.rattle_active){if(!mechanical)mechanical=new UnderbodySound.Player(ctx);mechanical.update(data.nurec.speed_kph,speaking);}else if(mechanical){mechanical.dispose();mechanical=null;}
 };
 document.addEventListener('visibilitychange',()=>{if(document.visibilityState!=='visible')stop()});addEventListener('pagehide',()=>{stop();ctx?.close();channel?.close()});
});

/* Outcome-gated cached responses, shared with explanation audio ownership. */
addEventListener('DOMContentLoaded',()=>{
 let audio=null,pack=null,last='',session=null,phase=null,enabled=true,turn=0;
 const lang=()=>window.HongikLocale?.lang||'ko';
 try{enabled=localStorage.getItem('carla-navigation-voice')!=='off'&&localStorage.getItem('nurec-sohee-enabled')!=='false'}catch{}
 const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('nurec-hongik-sohee'):null;
 function stop(){turn++;if(audio){audio.pause();audio.removeAttribute('src');audio.load();audio.remove();audio=null}window.passengerNarration?.setDuck?.(1)}
 if(channel)channel.onmessage=()=>stop();
 const load=()=>fetch('/api/research-voice?lang='+lang(),{cache:'no-store'}).then(r=>r.json()).then(p=>pack=p).catch(()=>null);
 const ready=load();
 async function say(key){if(!enabled||document.visibilityState!=='visible')return;const requested=++turn;await ready;if(requested!==turn)return;
  if(key.startsWith('intent:'))key=pack?.intent_actions?.[key.slice(7)]||null;
  if(!key)return;
  if(key.startsWith('result:'))key=pack?.actions?.[key.slice(7)]||'unfulfilled';
  const voice=pack?.voices?.[key];if(!voice?.cached||!voice.url)return;
  stop();dispatchEvent(new Event('hongik-feedback-speaking'));channel?.postMessage({claim:'feedback-'+crypto.randomUUID()});
  const mine=turn;audio=new Audio(voice.url);audio.id='research-feedback-audio';audio.hidden=true;document.body.append(audio);
  audio.onplaying=()=>{if(mine===turn)window.passengerNarration?.setDuck?.(.16)};
  audio.onended=()=>{if(mine===turn)stop()};audio.onerror=()=>{if(mine===turn)stop()};audio.play().catch(()=>{if(mine===turn)stop()});
 }
 window.HongikFeedback={say,stop};
 addEventListener('hongik-voice-enabled',e=>{enabled=Boolean(e.detail);if(!enabled)stop()});
 addEventListener('pagehide',stop);document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
 const previous=window.CockpitUpdate;
 window.CockpitUpdate=data=>{
  previous?.(data);const event=data.session?.navigation?.research_event,study=event?.study;
  if(!data.connected||!study){stop();return;}
  const sid=data.session.session_id;if(session!==sid){stop();session=sid;phase=null;last=''}
  const outcome=event.outcome||{},signature=[sid,study.action,study.phase,outcome.status,study.repeat_count].join(':');
  if(signature===last)return;last=signature;
  const prior=phase;phase=study.phase;
  if(phase==='queued')say('intent:'+study.action);
  else if(phase==='applying'&&prior!=='queued')say('intent:'+study.action);
  else if(phase==='observing')say(outcome.status==='achieved'?'result:'+study.action:outcome.status==='partial'?'partial':'unfulfilled');
  else if(phase==='complete')say('complete');
  else if(phase==='idle'&&prior==='queued')say('cancelled');
 };
});

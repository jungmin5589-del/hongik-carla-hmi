/* Native-only pedestrian trial UI. Existing NuRec pages remain unchanged. */
addEventListener('DOMContentLoaded',()=>{
 let previous=null,announcement=0,exterior=null;
 const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('nurec-hongik-sohee'):null;
 if(channel)channel.onmessage=()=>{exterior?.pause();exterior=null};
 const poll=setInterval(()=>{
  if(!window.CockpitUpdate)return;
  clearInterval(poll);const update=window.CockpitUpdate;
  window.CockpitUpdate=data=>{
   update(data);const s=data.nurec?.scenario;if(s?.id!=='pedestrian_yield')return;
   const $=id=>document.getElementById(id),phase=s.yielding.phase;
   $('map-name').textContent='신호 없는 횡단보도';
   $('route-name').textContent=s.completed?'정차 중':'보행자와 서로 양보';
   $('turn-instruction').textContent=({approach:'횡단보도로 접근',mutual_wait:'보행자 횡단 여부 확인 중',crossing:'보행자 횡단 중 · 정차',clearance:'횡단 구간 확인 중',resume:'양보 후 다시 출발',finishing:'서서히 정차 중',complete:'행동 결과 확인 완료'})[phase];
   $('route-note').textContent=s.outcome.summary||data.session.navigation.research_event.description;
   $('route-time').textContent=s.completed?'완료':phase==='mutual_wait'?`${Math.floor(s.yielding.wait_s)}초 대기`:'—';
   $('route-eta').textContent='—';$('drive-mode').textContent=s.completed?'정차 중':data.nurec.speed_kph<.5?'정차 중':'주행 중';
   if(previous===s.session&&s.yielding.announcement_count>announcement){
    if(document.visibilityState==='visible'){
     channel?.postMessage({claim:'exterior-yield-notice'});exterior?.pause();
     exterior=new Audio('/api/narration/audio/yield_notice.wav');exterior.play().catch(()=>{});
    }
   }
   previous=s.session;announcement=s.yielding.announcement_count;
  };
 },100);
 addEventListener('pagehide',()=>{exterior?.pause();channel?.close()});
});

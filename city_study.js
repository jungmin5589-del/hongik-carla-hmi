/* Classic navigation keeps its layout and shares the background-capable scene audio. */
addEventListener('DOMContentLoaded',()=>{
 const sound=new HongikSceneSound.SceneAudio();
 const credit=document.createElement('div');credit.className='setting';credit.style.display='none';
 credit.innerHTML='<small id="mechanical-audio-status">상황 효과음 · 금속 마찰 <span id="mechanical-playback-status" role="status"></span><br><a href="https://freesound.org/people/Doctor_Jekyll/sounds/254064/" target="_blank" rel="noopener">Metal Scraping.wav · Doctor_Jekyll</a> · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a><br>발췌 · 고음과 음량 조절</small>';
 document.getElementById('settings-sheet')?.appendChild(credit);
 const poll=setInterval(()=>{
  if(!window.CockpitUpdate)return;clearInterval(poll);const update=window.CockpitUpdate;
  window.CockpitUpdate=data=>{
   update(data);const s=data.nurec?.scenario,city=['pedestrian_yield','city_carpool','city_rattle','fallen_cargo'].includes(s?.id);
   document.body.classList.toggle('city-study',city);credit.style.display=s?.id==='city_rattle'?'block':'none';
   if(!city){sound.update(data);return}
   const $=id=>document.getElementById(id);
   const event=data.session.navigation.research_event;
   $('route-eta').textContent='—';$('route-time').textContent='—';$('route-distance').textContent='—';
   $('route-name').textContent=s.id==='city_carpool'?'동승자 대기 장소':'목적지';
   $('map-name').textContent=s.id==='fallen_cargo'?'도로 위 낙하물':s.id==='pedestrian_yield'?'신호 없는 횡단보도':s.id==='city_carpool'?'동승자 대기 구역':'이상음 주행';
   $('turn-instruction').textContent=s.completed?'차량이 정차했습니다':s.id==='fallen_cargo'?(s.cargo.passed?'낙하물 통과 · 주변 확인':s.onset?'전방 낙하물 · 감속':'앞 트럭과 거리 유지'):s.id==='pedestrian_yield'?({approach:'횡단보도로 접근',mutual_wait:'보행자 횡단 여부 확인 중',crossing:'보행자 횡단 중 · 정차',clearance:'횡단 구간 확인 중',resume:'양보 후 다시 출발',finishing:'서서히 정차 중',complete:'정차 중'})[s.yielding.phase]:s.id==='city_carpool'?'문 닫힘 유지 · 동승자 대기':'차량 상태 확인 중';
   $('route-note').textContent=s.outcome.summary||event.description;
   $('drive-mode').textContent=data.nurec.speed_kph<.5?'정차 중':'주행 중';
   sound.update(data);
   const status=sound.mechanical?.status;
   if(status){document.body.dataset.mechanicalSound=status;$('mechanical-playback-status').textContent=({loading:'불러오는 중',ready:'준비됨',playing:'재생 중',unavailable:'파일 확인 필요'})[status]||''}

  };
 },100);
});

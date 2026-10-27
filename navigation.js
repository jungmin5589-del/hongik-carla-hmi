/* Navigation-only controller. The driving window subscribes to the same frames. */
(()=>{
 const $=id=>document.getElementById(id);
 const bar=document.createElement('div');bar.className='nurec-controls';bar.setAttribute('aria-label','야간 주행 체험 조작');
 bar.innerHTML='<span class="nurec-trial-status" id="nurec-status">주행 연결 중</span><button class="primary" id="nurec-start">주행 시작</button><button id="nurec-pause">일시정지</button><button id="nurec-reset">처음으로</button><select id="nurec-quality" aria-label="주행 영상 화질"><option value="smooth">360p · 가볍게</option><option value="balanced">540p · 균형</option><option value="high" selected>720p · 선명하게</option><option value="fullhd">1080p · 고화질</option></select><a href="/drive" target="nurec-driving">큰 주행 화면 ↗</a>';
 document.body.append(bar);
 const home=document.createElement('button');home.id='nurec-home';home.textContent='시나리오 선택';bar.prepend(home);
 const phone=document.createElement('a');phone.href='http://127.0.0.1:8776/connect';phone.target='hongik-mobile-setup';phone.rel='noopener';phone.dataset.phoneConnect='true';phone.textContent='휴대폰 연결 · QR';bar.append(phone);
 const phoneStyle=document.createElement('link');phoneStyle.rel='stylesheet';phoneStyle.href='http://127.0.0.1:8776/pc/phone-link.css';document.head.append(phoneStyle);
 const phoneScript=document.createElement('script');phoneScript.src='http://127.0.0.1:8776/pc/phone-link.js';document.body.append(phoneScript);
 const beam=document.createElement('span');beam.id='nurec-highbeam';beam.hidden=true;beam.setAttribute('role','img');beam.setAttribute('aria-label','상향등 켜짐');beam.style.cssText='color:#1775ff;font-weight:700;white-space:nowrap';beam.innerHTML='<svg width="25" height="21" viewBox="0 0 28 22" aria-hidden="true" style="vertical-align:middle"><path d="M16 4 Q25 4 25 11 Q25 18 16 18 Z M3 4H12 M2 8H12 M2 12H12 M3 16H12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg> 상향등';bar.prepend(beam);
 async function goHome(){window.dispatchEvent(new Event('nurec-exit'));await control({mode:'paused'});location.assign('http://127.0.0.1:8775/')}
 home.onclick=goHome;
 bar.setAttribute('aria-label','주행 체험 조작');
 $('nurec-start').disabled=true;$('nurec-pause').disabled=true;
 const duration=document.createElement('select');duration.id='nurec-duration';duration.setAttribute('aria-label','정체 포함 체험 시간');duration.innerHTML='<option value="300">약 5분</option><option value="450">약 7분 30초</option><option value="600">약 10분</option>';duration.hidden=true;bar.insertBefore(duration,$('nurec-quality'));
 new ResizeObserver(()=>document.documentElement.style.setProperty('--nurec-controls-height',bar.getBoundingClientRect().height+'px')).observe(bar);
 let last=null,busy=false,audio=null,lastHorn=null,lastImpact=null;
 document.addEventListener('pointerdown',()=>{if(!audio){const C=window.AudioContext||window.webkitAudioContext;if(C)audio=new C()}audio?.resume().catch(()=>{})});
 function horn(){if(!audio)return;const start=audio.currentTime;for(const hz of [340,425]){const o=audio.createOscillator(),g=audio.createGain();o.type='sawtooth';o.frequency.value=hz;g.gain.setValueAtTime(0,start);g.gain.linearRampToValueAtTime(.055,start+.025);g.gain.setValueAtTime(.055,start+.32);g.gain.linearRampToValueAtTime(0,start+.40);o.connect(g).connect(audio.destination);o.start(start);o.stop(start+.42)}}
 function impactSound(){
  if(!audio||audio.state!=='running')return;
  const buffer=audio.createBuffer(1,Math.floor(audio.sampleRate*.45),audio.sampleRate),samples=buffer.getChannelData(0);
  for(let i=0;i<samples.length;i++)samples[i]=(Math.random()*2-1)*Math.exp(-i/(audio.sampleRate*.09));
  const source=audio.createBufferSource(),filter=audio.createBiquadFilter(),gain=audio.createGain();
  source.buffer=buffer;filter.type='lowpass';filter.frequency.value=1100;gain.gain.value=.14;
  source.connect(filter).connect(gain).connect(audio.destination);source.start();
 }
 async function control(body){if(busy)return;busy=true;try{const r=await fetch('/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw Error('요청을 반영하지 못했습니다.')}catch(e){$('nurec-status').textContent=e.message}finally{busy=false}}
 $('nurec-start').onclick=()=>control({mode:'auto'});$('nurec-pause').onclick=()=>control({mode:'paused'});$('nurec-reset').onclick=()=>control({reset:true});
 $('nurec-quality').onchange=()=>control({quality:$('nurec-quality').value});
 duration.onchange=()=>control({duration_s:Number(duration.value)});
 const previous=window.CockpitUpdate;
 window.CockpitUpdate=data=>{
  previous?.(data);const n=data.nurec;if(!n)return;
  const s=n.scenario,key=s.session+':'+s.horn_count;
  beam.hidden=!s.high_beam?.on;
  const congestion=s.id==='congestion_long',blockade=s.layout==='four_lane_blockade';duration.hidden=!congestion||blockade;if(congestion&&!blockade&&document.activeElement!==duration)duration.value=s.duration_s;
  const fog=s.id==='dense_fog';
  if(lastHorn&&lastHorn.session===s.session&&s.horn_count>lastHorn.count&&document.visibilityState==='visible')horn();
  lastHorn={session:s.session,count:s.horn_count};
  const impactPhase=s.crash?.phase,impactKey=s.session+':'+impactPhase;
  if(lastImpact?.session===s.session&&lastImpact.key!==impactKey&&s.crash?.primary_collision_verified&&
     ['primary_impact','secondary_impact'].includes(impactPhase)&&document.visibilityState==='visible')impactSound();
  lastImpact={session:s.session,key:impactKey};
  $('map-attribution').innerHTML=data.map_context?'실측 촬영 경로 · © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors · ODbL</a>':'실측 촬영 경로 · NuRec × CARLA';$('scene-source').textContent=data.map_context?.building_count?'실시간 차량 위치 · 주변 건물 지도':'실시간 차량 위치 · 주행 경로';
  $('route-name').textContent=s.completed?'주행 체험 완료':'야간 주행 체험';$('turn-instruction').textContent=s.completed?'주행 체험을 마쳤습니다':s.layout==='two_lane_boundary_weaving'?'같은 차로를 유지하며 직진':'앞차를 따라 주행';
  $('route-note').textContent='현재 주행 창과 같은 차량·상황에 연결되어 있습니다.';
  if(congestion){const remain=Math.ceil(s.remaining_s);const time=`${Math.floor(remain/60)}분 ${remain%60}초`;$('route-name').textContent=s.completed?'주행 체험 완료':'고속도로 서행 체험';$('turn-instruction').textContent=s.completed?'구간 끝에 도착했습니다':'차간 거리를 유지하며 서행';$('route-time').textContent=time;const eta=new Date(Date.now()+remain*1000);$('route-eta').textContent=eta.toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit',hour12:false});$('route-note').textContent=`정체·서행 포함 · 남은 체험 약 ${time} · 일시정지 시간 제외`;}
  $('drive-mode').textContent=n.mode==='paused'?'일시정지':'주행 중';$('map-name').textContent='야간 주행';
  if(congestion)$('map-name').textContent='고속도로 서행';
  if(blockade){$('route-name').textContent='4차로 저속 차량 체험';$('map-name').textContent='4차로 고속도로';$('turn-instruction').textContent=s.completed?'촬영 구간 체험 완료':'앞차 25~35 · 왼쪽 90 km/h';$('route-note').textContent='오른쪽 대형차 3대 · 25~35 km/h로 조금씩 다른 흐름 · 실제 촬영 구간 끝까지';}
  if(fog){const remain=Math.ceil(s.remaining_s),time=`${Math.floor(remain/60)}분 ${remain%60}초`;$('map-name').textContent='고속도로';$('route-name').textContent=s.completed?'주행 체험 완료':'안개 주행 체험';$('route-time').textContent=time;$('route-eta').textContent=new Date(Date.now()+remain*1000).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit',hour12:false});$('turn-instruction').textContent=s.completed?'구간 끝에 도착했습니다':s.fog.stage==='clear'?'경로를 따라 주행':'시야 제한 구간 · 서서히 감속';$('route-note').textContent=`남은 체험 약 ${time} · 현재 주행 창과 같은 차량에 연결되어 있습니다.`;}
  if(s.outcome?.phase&&s.outcome.phase!=='idle'){
   $('route-note').textContent=s.outcome.summary||s.feedback;
   $('turn-instruction').textContent=s.completed?'선택한 행동의 결과를 확인했습니다':s.outcome.phase==='stopping'?'체험 마무리 중':'선택한 행동의 결과 확인 중';
   if(s.completed){$('route-name').textContent='체험 종료';$('route-time').textContent='완료';$('route-eta').textContent='—';$('drive-mode').textContent='체험 종료'}
  }
  if(s.action==='overtake'){
   $('turn-instruction').textContent=s.completed?s.outcome.message:s.crash?.primary_collision_verified?'충돌 발생 · 차량 정지':s.feedback;
   $('route-note').textContent=s.outcome.summary||s.feedback;
  }
  $('nurec-status').textContent=n.phase!=='live'?'영상 준비 중':s.completed?'체험 완료':`${n.width} × ${n.height} · ${n.mode==='paused'?'대기':'주행 중'}`;
  $('nurec-start').disabled=n.phase!=='live'||s.completed||n.mode==='auto';$('nurec-pause').disabled=n.mode==='paused';
  if(document.activeElement!==$('nurec-quality'))$('nurec-quality').value=n.quality;
  last=s;
 };
 $('experience-open').onclick=goHome;
})();

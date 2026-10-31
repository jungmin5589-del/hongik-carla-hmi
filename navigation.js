/* Passenger-facing navigation. Operator controls stay in settings. */
(()=>{
 const $=id=>document.getElementById(id),bar=document.createElement('div');bar.className='nurec-controls';bar.setAttribute('aria-label','주행 설정');
 bar.innerHTML='<strong class="navigation-settings-title">주행 설정</strong><span id="nurec-status">차량 연결 중</span><button class="primary" id="nurec-start">출발</button><button id="nurec-pause">일시정지</button><button id="nurec-reset">출발 위치로</button><select id="nurec-quality" aria-label="화면 선명도"><option value="smooth">가볍게 · 360p</option><option value="balanced">균형 · 540p</option><option value="high" selected>선명하게 · 720p</option><option value="fullhd">고화질 · 1080p</option></select><a href="/drive" target="nurec-driving">주행 화면 열기 ↗</a>';
 $('settings-sheet').append(bar);
 const home=document.createElement('button');home.id='nurec-home';home.textContent='출발 설정';bar.append(home);
 const phone=document.createElement('a');phone.href='http://127.0.0.1:8776/connect';phone.target='hongik-mobile-setup';phone.rel='noopener';phone.dataset.phoneConnect='true';phone.textContent='휴대폰 연결';bar.append(phone);
 for(const [tag,attr,url] of [['link','href','http://127.0.0.1:8776/pc/phone-link.css'],['script','src','http://127.0.0.1:8776/pc/phone-link.js']]){const e=document.createElement(tag);if(tag==='link')e.rel='stylesheet';e[attr]=url;document.head.append(e)}
 const depart=document.createElement('button');depart.id='passenger-depart';depart.textContent='출발';depart.hidden=true;depart.onclick=()=>control({mode:'auto'});document.querySelector('.visualization').append(depart);
 const beam=document.createElement('span');beam.id='nurec-highbeam';beam.hidden=true;beam.setAttribute('aria-label','상향등 켜짐');beam.textContent='≡◖';document.querySelector('.speed-panel').append(beam);
 const duration=document.createElement('select');duration.id='nurec-duration';duration.hidden=true;bar.append(duration);
 let busy=false,audio=null,lastHorn=null,lastImpact=null;
 document.addEventListener('pointerdown',()=>{if(!audio){const C=window.AudioContext||window.webkitAudioContext;if(C)audio=new C()}audio?.resume().catch(()=>{})});
 function horn(){if(!audio)return;const start=audio.currentTime;for(const hz of [340,425]){const o=audio.createOscillator(),g=audio.createGain();o.type='sawtooth';o.frequency.value=hz;g.gain.setValueAtTime(0,start);g.gain.linearRampToValueAtTime(.055,start+.025);g.gain.setValueAtTime(.055,start+.32);g.gain.linearRampToValueAtTime(0,start+.40);o.connect(g).connect(audio.destination);o.start(start);o.stop(start+.42)}}
 function impactSound(){if(!audio||audio.state!=='running')return;const b=audio.createBuffer(1,Math.floor(audio.sampleRate*.45),audio.sampleRate),a=b.getChannelData(0);for(let i=0;i<a.length;i++)a[i]=(Math.random()*2-1)*Math.exp(-i/(audio.sampleRate*.09));const source=audio.createBufferSource(),filter=audio.createBiquadFilter(),gain=audio.createGain();source.buffer=b;filter.type='lowpass';filter.frequency.value=1100;gain.gain.value=.14;source.connect(filter).connect(gain).connect(audio.destination);source.start()}
 async function control(body){if(busy)return;busy=true;try{const r=await fetch('/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'요청을 반영하지 못했습니다.')}catch(e){$('nurec-status').textContent=e.message}finally{busy=false}}
 async function goHome(){window.dispatchEvent(new Event('nurec-exit'));try{const s=await(await fetch('/state')).json();if(!s.scenario?.completed)await control({mode:'paused'})}catch{}location.assign('http://127.0.0.1:8775/')}
 home.onclick=goHome;$('experience-open').onclick=goHome;
 $('nurec-start').disabled=true;$('nurec-pause').disabled=true;
 $('nurec-start').onclick=()=>control({mode:'auto'});$('nurec-pause').onclick=()=>control({mode:'paused'});$('nurec-reset').onclick=()=>control({reset:true});$('nurec-quality').onchange=()=>control({quality:$('nurec-quality').value});
 const previous=window.CockpitUpdate;
 window.CockpitUpdate=data=>{
  previous?.(data);const n=data.nurec;if(!n)return;const s=n.scenario;
  beam.hidden=!s.high_beam?.on;
  if(lastHorn?.session===s.session&&s.horn_count>lastHorn.count&&document.visibilityState==='visible')horn();lastHorn={session:s.session,count:s.horn_count};
  const key=s.session+':'+s.crash?.phase;if(lastImpact?.session===s.session&&lastImpact.key!==key&&s.crash?.primary_collision_verified&&['primary_impact','secondary_impact'].includes(s.crash.phase)&&document.visibilityState==='visible')impactSound();lastImpact={session:s.session,key};
  $('scene-source').textContent='주변 상황';$('map-name').textContent='주행 지도';
  if(!data.map_context)$('map-attribution').textContent='주행 지도';
  const fog=s.id==='dense_fog',traffic=s.layout==='four_lane_blockade'||s.id==='congestion_long';
  $('route-name').textContent=data.route?.destination?.name||'목적지';
  $('turn-instruction').textContent=s.completed?'차량이 정차했습니다':fog&&s.fog?.stage!=='clear'?'시야 제한 구간 · 서서히 감속':traffic?'앞차와 간격을 유지하며 주행':'경로를 따라 주행';
  $('route-note').textContent=s.outcome?.summary||s.feedback||(fog?'전방 시야를 확인하며 주행하고 있어요.':'주변 차량과 도로를 살피며 이동하고 있어요.');
  $('route-eta').textContent='—';$('route-time').textContent='—';
  $('drive-mode').textContent=n.speed_kph<.5?'정차 중':'주행 중';
  if(s.outcome?.phase&&s.outcome.phase!=='idle')$('turn-instruction').textContent=s.completed?'주변 확인 · 정차 중':s.outcome.phase==='stopping'?'서서히 정차 중':'요청한 대응 진행 중';
  if(s.action==='overtake')$('turn-instruction').textContent=s.crash?.primary_collision_verified?'충돌 감지 · 차량 정지':s.feedback;
  $('nurec-status').textContent=n.phase!=='live'?'차량 연결 중':n.mode==='paused'?'정차 중':'주행 중';
  $('nurec-start').disabled=n.phase!=='live'||s.completed||n.mode==='auto';$('nurec-pause').disabled=n.mode==='paused';depart.hidden=n.phase!=='live'||s.completed||n.mode==='auto';
  if(document.activeElement!==$('nurec-quality'))$('nurec-quality').value=n.quality;
 };
})();

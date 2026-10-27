/* Passenger navigation, local audio, and explicitly labelled interactive preview. */
(()=>{
'use strict';
const $=id=>document.getElementById(id);
window.cockpitControlMode=new URLSearchParams(location.search).get('ui')==='controls';
window.setCockpitMode=mode=>{
 window.cockpitControlMode=mode==='controls';
 document.body.classList.toggle('controls-ui',window.cockpitControlMode);
 $('control-panel').hidden=!window.cockpitControlMode;
 const url=new URL(location.href);
 if(window.cockpitControlMode)url.searchParams.set('ui','controls');else url.searchParams.delete('ui');
 history.replaceState(null,'',url);
};
window.setCockpitMode(window.cockpitControlMode?'controls':'popup');
const icons={search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',settings:'<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2" fill="white"/><circle cx="16" cy="12" r="2" fill="white"/><circle cx="7" cy="18" r="2" fill="white"/>',plus:'<path d="M12 5v14M5 12h14"/>',minus:'<path d="M5 12h14"/>',close:'<path d="m6 6 12 12M6 18 18 6"/>',straight:'<path d="M12 21V3m-7 7 7-7 7 7"/>',pin:'<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',music:'<path d="M9 17V5l11-2v12M9 8l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2"/><ellipse cx="17" cy="16" rx="3" ry="2"/>',list:'<path d="M8 6h13M8 12h13M8 18h13M3 6h.1M3 12h.1M3 18h.1"/>',play:'<path d="m8 4 12 8-12 8Z" fill="currentColor" stroke="none"/>',pause:'<path d="M7 5v14M17 5v14" stroke-width="4"/>',next:'<path d="m5 5 10 7-10 7Z" fill="currentColor"/><path d="M19 5v14"/>',previous:'<path d="m19 5-10 7 10 7Z" fill="currentColor"/><path d="M5 5v14"/>',volume:'<path d="M4 9h4l5-4v14l-5-4H4Zm13-1a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',wheel:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="m4 8 5 3m11-3-5 3m-3 4v6"/>',car:'<path d="m4 10 2-5h12l2 5v9h-3v-3H7v3H4Zm0 0h16M7 13h2m6 0h2"/>',stop:'<path d="M8 3h8l5 5v8l-5 5H8l-5-5V8Z"/><path d="M12 7v6m0 3v.1"/>'};
function icon(name){return `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name]||icons.pin}</svg>`}
document.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));
let toastTimer;
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4200)}
const audio=$('audio');let tracks=[],current=-1;
audio.volume=.45;
const narration=new NavigationVoice({audio,onStatus:text=>{$('voice-status').textContent=text;$('experience-voice-status').textContent=text}});
window.passengerNarration=narration;
let ttsProvider='qwen';try{if(localStorage.getItem('carla-tts-bright-trial')==='qwen-cached-v4')ttsProvider=localStorage.getItem('carla-tts-provider')||'qwen';else{localStorage.setItem('carla-tts-bright-trial','qwen-cached-v4');localStorage.setItem('carla-tts-provider','qwen')}}catch{}
narration.setProvider(ttsProvider);$('tts-provider').value=ttsProvider;
$('tts-provider').onchange=()=>{narration.setProvider($('tts-provider').value);try{localStorage.setItem('carla-tts-provider',$('tts-provider').value)}catch{}};
window.setPassengerMusicVolume=value=>narration.setMusicVolume(value);
let voiceEnabled=true;try{voiceEnabled=localStorage.getItem('carla-navigation-voice')!=='off'}catch{}
narration.setEnabled(voiceEnabled);
$('voice-toggle').textContent=voiceEnabled?'켜짐':'꺼짐';$('experience-narration').checked=voiceEnabled;
$('voice-status').textContent=voiceEnabled?'한국어 음성 안내 · 주행 시작 후 재생':'음성 안내 · 꺼짐';
document.addEventListener('pointerdown',()=>narration.arm(),{once:true});
document.addEventListener('keydown',()=>narration.arm(),{once:true});
window.addEventListener('pagehide',()=>narration.cancel());
function setSheet(id,show){$(id).hidden=!show;if(show){['music-sheet','settings-sheet','destination-panel'].filter(x=>x!==id).forEach(x=>$(x).hidden=true)}}
function openLibrary(){setSheet('music-sheet',$('music-sheet').hidden)}
['library-open','current-art','music-footer'].forEach(id=>$(id).onclick=openLibrary);
$('track-info').onclick=e=>{if(!e.target.closest('input'))openLibrary()};
$('track-info').onkeydown=e=>{if(e.key==='Enter')openLibrary()};
$('library-close').onclick=()=>setSheet('music-sheet',false);
function renderTracks(){
 $('tracks').replaceChildren();tracks.forEach((t,i)=>{const b=document.createElement('button');b.className='track-row'+(current===i?' active':'');b.disabled=!t.available;b.setAttribute('aria-label',`${t.artist} ${t.title} 재생`);b.innerHTML=`<span class="track-number">${String(i+1).padStart(2,'0')}</span><span class="album-art" style="background:${t.color}">${icon('music')}</span><span><strong></strong><small></small></span>`;b.querySelector('strong').textContent=t.title;b.querySelector('small').textContent=t.artist+(t.available?'':' · 파일을 찾을 수 없음');b.onclick=()=>selectTrack(i);$('tracks').appendChild(b)})
}
async function selectTrack(i){if(!tracks.length)return;current=(i+tracks.length)%tracks.length;const t=tracks[current];if(!t.available){toast('music 폴더의 음악 파일을 확인해 주세요.');return}audio.src=t.url;$('track-title').textContent=t.title;$('track-artist').textContent=t.artist;$('current-art').style.background=t.color;renderTracks();$('audio-status').textContent='';try{await audio.play()}catch(e){toast('재생 버튼을 눌러 주세요. 브라우저의 오디오 재생 권한을 확인하세요.')}if('mediaSession'in navigator){navigator.mediaSession.metadata=new MediaMetadata({title:t.title,artist:t.artist,album:t.album})}}
$('play').onclick=()=>{if(current<0){selectTrack(0);return}if(audio.paused)audio.play().catch(()=>toast('음악을 재생할 수 없습니다.'));else audio.pause()};
$('previous').onclick=()=>{if(audio.currentTime>3)audio.currentTime=0;else selectTrack(current-1)};$('next').onclick=()=>selectTrack(current+1);
audio.onplay=()=>{$('play').innerHTML=icon('pause');$('play').setAttribute('aria-label','일시정지')};audio.onpause=()=>{$('play').innerHTML=icon('play');$('play').setAttribute('aria-label','재생')};audio.onended=()=>selectTrack(current+1);
const time=s=>Number.isFinite(s)?`${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`:'0:00';
audio.ontimeupdate=()=>{$('elapsed').textContent=time(audio.currentTime);$('duration').textContent=time(audio.duration);$('seek').value=audio.duration?audio.currentTime/audio.duration*100:0};
audio.onloadedmetadata=()=>{$('duration').textContent=time(audio.duration);$('audio-status').textContent=tracks[current]?.album||''};
audio.onerror=()=>{toast('파일 재생에 실패했습니다. D: 드라이브 연결과 브라우저의 FLAC 지원을 확인하세요.');$('audio-status').textContent='음악 파일 재생 오류'};
$('seek').onclick=e=>e.stopPropagation();$('seek').oninput=()=>{if(Number.isFinite(audio.duration))audio.currentTime=+$('seek').value/100*audio.duration};
$('volume').oninput=()=>{narration.setMusicVolume(+$('volume').value/100);audio.muted=false;$('volume-value').textContent=$('volume').value+'%'};
$('mute').onclick=()=>{audio.muted=!audio.muted;$('volume-value').textContent=audio.muted?'음소거':Math.round(narration.musicVolume*100)+'%'};
fetch('/api/library').then(r=>r.json()).then(d=>{tracks=d.tracks;renderTracks()}).catch(()=>toast('음악 목록을 불러오지 못했습니다.'));
if('mediaSession'in navigator){navigator.mediaSession.setActionHandler('play',()=>audio.play());navigator.mediaSession.setActionHandler('pause',()=>audio.pause());navigator.mediaSession.setActionHandler('nexttrack',()=>selectTrack(current+1));navigator.mediaSession.setActionHandler('previoustrack',()=>selectTrack(current-1))}

let state=null,atlas={roads:[],destinations:[]},route=null,atlasKey='',atlasBusy=false,lastAtlas=0,zoom=1,pan=[0,0],previewStarted=0,previewActionAt=0,previewStage='ready',previewEpisode=0,previewSpeedOffset=0,previewLaneOffset=0;
window.cockpitPreview=false;
const canvas=$('navigation-map'),ctx=canvas.getContext('2d');
function mapSize(){const r=canvas.getBoundingClientRect(),d=Math.min(devicePixelRatio,2);if(canvas.width!==Math.round(r.width*d)||canvas.height!==Math.round(r.height*d)){canvas.width=Math.round(r.width*d);canvas.height=Math.round(r.height*d)}ctx.setTransform(d,0,0,d,0,0);return r}
function drawMap(){
 const r=mapSize(),w=r.width,h=r.height;ctx.fillStyle='#e8e9e6';ctx.fillRect(0,0,w,h);
 if(!atlas.roads.length){ctx.strokeStyle='#dfe2dd';ctx.lineWidth=1;for(let x=-h;x<w+h;x+=65){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x+h*.5,h);ctx.stroke()}ctx.fillStyle='#979f98';ctx.font='12px Pretendard';ctx.textAlign='center';ctx.fillText('CARLA 도로 정보를 기다리는 중',w/2,h*.47);return}
 const points=atlas.roads.flatMap(l=>l.points);const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
 const following=!!state?.nurec;
 const scale=(following?Math.min(w,h)/180:Math.min(w/(maxX-minX+100),h/(maxY-minY+100)))*zoom;
 const center=(following||zoom>1.2)&&state?.world_pose?[state.world_pose.x,state.world_pose.y]:[(minX+maxX)/2,(minY+maxY)/2];
 const at=p=>[(p[0]-center[0])*scale+w*.5+pan[0],(p[1]-center[1])*scale+h*.48+pan[1]];
 // Only the actual CARLA lane polylines are drawn; no fabricated map tiles.
 window.NurecMapContext?.drawContext(ctx,atlas,at,scale,w,h);
 for(const color of ['#cbd0ca','#fafbf8']){ctx.strokeStyle=color;ctx.lineJoin='round';ctx.lineCap='round';for(const lane of atlas.roads){ctx.lineWidth=Math.max(2,lane.width*scale)+(color==='#cbd0ca'?2:0);ctx.beginPath();lane.points.forEach((p,i)=>{const q=at(p);i?ctx.lineTo(...q):ctx.moveTo(...q)});ctx.stroke()}}
 if(route){ctx.strokeStyle='#3e6ae1';ctx.lineWidth=5;ctx.beginPath();route.points.slice(route.index||0).forEach((p,i)=>{const q=at(p);i?ctx.lineTo(...q):ctx.moveTo(...q)});ctx.stroke()}
 for(const dest of atlas.destinations){const [x,y]=at(dest.point);ctx.fillStyle=route?.destination.id===dest.id?'#3e6ae1':'#8a9492';ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fill();ctx.font='10px Pretendard';ctx.textAlign='left';ctx.fillStyle='#6f7874';ctx.fillText(dest.name,x+10,y+3)}
 window.NurecMapContext?.drawActors(ctx,state,at,scale,w,h);
 if(state?.world_pose){const [x,y]=at([state.world_pose.x,state.world_pose.y]);ctx.save();ctx.translate(x,y);ctx.rotate((state.world_pose.yaw+90)*Math.PI/180);ctx.shadowColor='#0003';ctx.shadowBlur=5;ctx.fillStyle='#fff';ctx.beginPath();ctx.moveTo(0,-13);ctx.lineTo(10,11);ctx.lineTo(0,6);ctx.lineTo(-10,11);ctx.closePath();ctx.fill();ctx.shadowBlur=0;ctx.fillStyle='#db4149';ctx.beginPath();ctx.moveTo(0,-9);ctx.lineTo(7,8);ctx.lineTo(0,4);ctx.lineTo(-7,8);ctx.closePath();ctx.fill();ctx.restore()}
}
function destinationList(){const query=$('destination-search').value.trim().toLowerCase();$('destinations').replaceChildren();const rows=atlas.destinations.filter(d=>(d.name+' '+d.detail).toLowerCase().includes(query));if(!rows.length){const el=document.createElement('p');el.className='empty-note';el.textContent=atlas.destinations.length?'검색 결과가 없습니다.':'CARLA 시나리오에 연결하면 현재 도로 위 목적지가 표시됩니다. 설정에서 미리보기도 사용할 수 있습니다.';$('destinations').appendChild(el)}for(const d of rows){const b=document.createElement('button');b.className='destination-row';b.innerHTML=`<span class="place-symbol">${icon('pin')}</span><span><strong></strong><small></small></span><em>${(d.distance_m/1000).toFixed(1)} km</em>`;b.querySelector('strong').textContent=d.name;b.querySelector('small').textContent=d.detail;b.onclick=()=>selectDestination(d.id);$('destinations').appendChild(b)}}
function openDestinations(){setSheet('destination-panel',$('destination-panel').hidden);$('destination-search').value='';destinationList();if(!$('destination-panel').hidden){$('route-card').hidden=true;$('destination-search').focus()}else renderRoute()}
['search-open','navigation-footer','route-change'].forEach(id=>$(id).onclick=openDestinations);
$('destination-search').oninput=destinationList;document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{$('destination-search').value=b.dataset.filter;destinationList()});
async function selectDestination(id){try{if(window.cockpitPreview){const d=atlas.destinations.find(d=>d.id===id);route={destination:d,points:previewPaths[id],index:0,remaining_m:d.distance_m,arrived:false}}else{const res=await fetch('/api/route',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});const d=await res.json();if(!res.ok)throw Error(d.error);route=d.route}setSheet('destination-panel',false);renderRoute();drawMap();narration.reset();narration.update(state,route);}catch(e){toast(e.message)}}
$('route-cancel').onclick=async()=>{try{if(!window.cockpitPreview){const r=await fetch('/api/route',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"cancel":true}'});if(!r.ok)throw Error('경로 안내를 종료하지 못했습니다.')}route=null;narration.reset();renderRoute();drawMap()}catch(e){toast(e.message)}};
function renderRoute(){
 const show=!!route;$('route-card').hidden=!show||!$('destination-panel').hidden;$('search-open').hidden=show&&$('destination-panel').hidden;if(!route)return;
 const remaining=route.remaining_m||0,minutes=Math.max(1,Math.ceil(remaining/Math.max(15,state?.ego?.speed_kmh||40)*.06));
 $('route-name').textContent=route.destination.name;$('route-distance').textContent=remaining>=1000?(remaining/1000).toFixed(1)+' km':remaining+' m';$('route-time').textContent=route.arrived?'도착':minutes+'분';$('route-eta').textContent=new Date(Date.now()+minutes*60000).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit',hour12:false});
 let instruction='경로를 따라 계속 주행',dist=remaining;
 const pts=route.points,i=route.index||0;if(i+12<pts.length){const a=pts[i],b=pts[i+5],c=pts[i+12];let angle=Math.atan2(c[1]-b[1],c[0]-b[0])-Math.atan2(b[1]-a[1],b[0]-a[0]);angle=Math.atan2(Math.sin(angle),Math.cos(angle));if(Math.abs(angle)>.35){instruction=angle>0?'오른쪽으로 굽은 도로':'왼쪽으로 굽은 도로';dist=Math.round(Math.hypot(b[0]-a[0],b[1]-a[1]))}}
 if(route.off_route)instruction='경로에서 벗어났습니다';if(route.arrived)instruction='목적지에 도착했습니다';if(!state?.connected)instruction='연결 대기 · 안내 일시정지';
 $('turn-distance').textContent=route.arrived?'도착':dist>=1000?(dist/1000).toFixed(1)+' km':dist+' m';$('turn-instruction').textContent=instruction;
 $('route-note').textContent=window.cockpitPreview?'미리보기 경로 · 가상 주행':route.off_route?'목적지를 다시 선택해 주세요. 시나리오의 주행 경로는 유지됩니다.':'CARLA 도로 안내 · 시나리오 주행 경로가 우선됩니다.';
}
async function loadAtlas(){if(atlasBusy)return;atlasBusy=true;try{const r=await fetch('/api/atlas');if(!r.ok)throw Error();atlas=await r.json();destinationList();drawMap()}catch{}finally{atlasBusy=false}}
function updateLandmarkHud(data){const hud=$('landmark-hud');if(!hud)return;if(!data?.connected){hud.hidden=true;return}const list=data.destinations||atlas.destinations||[];let target=route?.destination||null;if(!target&&data.world_pose){target=list.map(d=>{const dx=d.point[0]-data.world_pose.x,dy=d.point[1]-data.world_pose.y;return{d,dist:Math.hypot(dx,dy)}}).sort((a,b)=>a.dist-b.dist)[0]?.d||null}if(!target){hud.hidden=true;return}const rem=route?.destination?.id===target.id?(route.remaining_m??target.distance_m):Math.round(Math.hypot(target.point[0]-(data.world_pose?.x||0),target.point[1]-(data.world_pose?.y||0)));$('landmark-glyph').className=`landmark-glyph ${target.landmark||'terminal'}`;$('landmark-name').textContent=target.name;$('landmark-detail').textContent=`${target.detail||'목적지 건물형 랜드마크'} · 약 ${rem>=1000?(rem/1000).toFixed(1)+' km':Math.max(0,rem)+' m'}`;$('landmark-kicker').textContent=window.cockpitPreview?'미리보기 · 목적지 랜드마크':'주행 중 · 목적지 랜드마크';hud.hidden=false}
window.CockpitUpdate=data=>{state=data;if(!window.cockpitPreview){if(data.connected){const key=data.map+':'+data.ego.id;if(key!==atlasKey){atlasKey=key;loadAtlas()}route=data.route||null}else if(Date.now()-lastAtlas>4000){lastAtlas=Date.now();loadAtlas()}}if(data.connected&&data.world_pose)window.updateLandmarks?.(data.destinations||atlas.destinations||[],data.world_pose);else if(!data.connected&&!window.cockpitPreview)window.updateLandmarks?.([]);updateLandmarkHud(data);renderRoute();drawMap();narration.update(data,route);$('scene-source').textContent=window.cockpitPreview?'미리보기 · 가상 랜드마크':'CARLA 실시간 차량 위치 · 목적지 랜드마크';$('map-attribution').textContent=window.cockpitPreview?'미리보기 · 서울 목적지 스타일 랜드마크':data.session?.navigation?.map_label?data.session.navigation.map_label+' · © OpenStreetMap contributors':`CARLA ${atlas.map?.split('/').pop()||''} · 목적지 랜드마크는 실험용`;if(window.cockpitPreview){$('connection').className='connection preview-badge';$('connection').textContent='미리보기';$('map-name').textContent='가상 주행'}};
$('zoom-in').onclick=()=>{zoom=Math.min(zoom*1.4,8);drawMap()};$('zoom-out').onclick=()=>{zoom=Math.max(zoom/1.4,state?.nurec ? .15 : .6);drawMap()};$('map-center').onclick=()=>{zoom=1;pan=[0,0];drawMap()};
let drag=null;canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY,...pan];canvas.setPointerCapture(e.pointerId)};canvas.onpointermove=e=>{if(drag){pan=[drag[2]+e.clientX-drag[0],drag[3]+e.clientY-drag[1]];drawMap()}};canvas.onpointerup=()=>drag=null;canvas.onpointercancel=()=>drag=null;
new ResizeObserver(drawMap).observe(canvas);
['settings-open','vehicle-settings'].forEach(id=>$(id).onclick=()=>setSheet('settings-sheet',$('settings-sheet').hidden));$('settings-close').onclick=()=>setSheet('settings-sheet',false);
function toggleVoice(){voiceEnabled=!voiceEnabled;narration.setEnabled(voiceEnabled);$('voice-toggle').textContent=voiceEnabled?'켜짐':'꺼짐';$('experience-narration').checked=voiceEnabled;$('voice-status').textContent=voiceEnabled?'한국어 음성 안내 · 켜짐':'음성 안내 · 꺼짐';try{localStorage.setItem('carla-navigation-voice',voiceEnabled?'on':'off')}catch{}toast(voiceEnabled?'목적지·상황 음성 안내를 켰습니다.':'음성 안내를 껐습니다.')}
$('voice-test').onclick=$('experience-voice-test').onclick=()=>{if(!voiceEnabled)toggleVoice();narration.test()};
$('experience-narration').onchange=()=>{if($('experience-narration').checked!==voiceEnabled)toggleVoice()};
$('voice-toggle').onclick=toggleVoice;$('voice-footer').onclick=toggleVoice;
$('fullscreen').onclick=()=>{if(document.fullscreenElement)document.exitFullscreen();else document.documentElement.requestFullscreen().catch(()=>toast('브라우저의 전체 화면 버튼을 사용하세요.'))};
let temperature=21;function temp(delta){temperature=Math.max(16,Math.min(28,temperature+delta));$('temperature').innerHTML=temperature.toFixed(1)+'<small>°</small>';toast('실험용 공조 표시 · 차량 온도 제어는 연결되지 않았습니다.')}$('temperature-down').onclick=()=>temp(-.5);$('temperature-up').onclick=()=>temp(.5);$('temperature').onclick=()=>toast('실험용 공조 표시입니다.');
const previewPaths={};function previewAtlas(){const roads=[];for(let x=-500;x<=500;x+=100)roads.push({width:9,points:[[x,-600],[x,600]]});for(let y=-600;y<=600;y+=120)roads.push({width:9,points:[[-500,y],[500,y]]});const places=[['홍익대학교','university',350,'캠퍼스 건물형 랜드마크'],['홍대입구역','station',700,'역 입구·표지형 랜드마크'],['서울역','terminal',1150,'유리 역사형 랜드마크']];const destinations=places.map(([name,landmark,d,detail],i)=>{const pts=Array.from({length:d/5+1},(_,n)=>[0,500-n*5]);previewPaths[String(i+1)]=pts;return{id:String(i+1),name,landmark,distance_m:d,point:pts.at(-1),detail,simulation_note:'CARLA Town05 도로 위 실험용 랜드마크'}});return{map:'Preview',roads,destinations}}
$('preview-toggle').onclick=()=>{narration.reset();window.cockpitPreview=!window.cockpitPreview;$('preview-toggle').textContent=window.cockpitPreview?'끄기':'켜기';route=null;pan=[0,0];atlasKey='';if(window.cockpitPreview){atlas=previewAtlas();previewStage='ready';previewStarted=0;previewActionAt=0;previewEpisode=0;previewSpeedOffset=0;previewLaneOffset=0;toast('미리보기입니다. 실제 CARLA 차량에는 명령을 보내지 않습니다.')}else{atlas={roads:[],destinations:[]};window.updateLandmarks?.([]);loadAtlas()}setSheet('settings-sheet',false);destinationList();renderRoute();drawMap()};
window.CockpitDemoAction=action=>{if(action==='emergency_stop'){previewStage='stopped';return}if(action==='start'){previewStage='driving';previewStarted=performance.now();return}if(action==='resolve'){previewActionAt=performance.now();previewStage='executing'}};
window.CockpitDemoControl=action=>{if(previewStage==='ready'||previewStage==='stopped')return '주행을 시작한 뒤 사용해 주세요.';if(action==='speed_down')previewSpeedOffset=Math.max(-30,previewSpeedOffset-10);if(action==='speed_up')previewSpeedOffset=Math.min(30,previewSpeedOffset+10);if(action==='lane_left')previewLaneOffset=Math.max(-1,previewLaneOffset-1);if(action==='lane_right')previewLaneOffset=Math.min(1,previewLaneOffset+1);previewActionAt=performance.now();previewStage='executing';return({speed_down:'목표 속도 10km/h 감속',speed_up:'목표 속도 10km/h 가속',lane_left:'왼쪽 차로 변경',lane_right:'오른쪽 차로 변경'})[action]+' · 미리보기'};
window.CockpitDemoState=()=>{
 const now=performance.now(),t=previewStarted?(now-previewStarted)/1000:0,stopped=['ready','stopped'].includes(previewStage);let speed=stopped?0:Math.max(0,64+previewSpeedOffset);
 const after=previewActionAt?(now-previewActionAt)/1000:0;if(previewStage==='executing'&&after>5)previewStage='resolved';if(previewStage==='resolved'&&after>10){previewEpisode++;previewActionAt=0;previewStage='driving'}
 const offset=previewLaneOffset*3.5;if(previewActionAt&&previewEpisode%3===1)speed=Math.max(0,40+previewSpeedOffset);
 const lanes=[-3.5,0,3.5].map((x,i)=>({id:i,points:Array.from({length:35},(_,n)=>({right_m:x,forward_m:-40+n*5,up_m:0,yaw_deg:0,width_m:3.5}))}));
 const ego={id:999,right_m:offset,forward_m:0,up_m:0,yaw_deg:0,speed_kmh:speed,lane_index:offset<-2?1:2,lane_count:3};
 const hazard=previewEpisode%3;const actors=[{id:1,kind:'vehicle',label:'차량',right_m:0,forward_m:23+(previewActionAt?after*5:0),up_m:0,yaw_deg:0,length_m:hazard===0?9:4.4,width_m:2.3,height_m:hazard===0?3.4:1.5},{id:2,kind:'vehicle',label:'버스',right_m:3.5,forward_m:hazard===1?1+after*5:48,up_m:0,yaw_deg:0,length_m:10,width_m:2.5,height_m:3.2},{id:3,kind:'vehicle',label:hazard===1?'버스':'차량',right_m:-3.5,forward_m:hazard===1?2+after*5:60+(Math.sin(t*.2)*10),up_m:0,yaw_deg:0,length_m:hazard===1?10:4.4,width_m:2,height_m:hazard===1?3:1.5}];
 let nav={id:'preview-start',status:'ready',title:'주행을 시작할까요?',body:'목적지와 음악을 선택한 뒤 가상 주행을 체험하세요.',action:'start',label:'주행 시작'};
 if(previewStage==='stopped')nav={id:'preview-stop',status:'stopped',title:'정지했습니다.',body:'설정에서 미리보기를 껐다 켜면 다시 시작합니다.'};
 else if(previewStage==='executing')nav={id:'preview-'+previewEpisode,status:'executing',title:'주행을 조정하고 있습니다.',body:'미리보기 차량이 이동합니다.'};
 else if(previewStage==='resolved')nav={id:'preview-'+previewEpisode,status:'resolved',title:'주행을 조정했습니다.',body:'다음 상황을 확인하며 계속 주행합니다.'};
 else if(previewStage==='driving')nav={id:'preview-'+previewEpisode,status:t>4?'offered':'monitoring',title:['전방 적재물과 거리를 둘까요?','양옆 버스와 거리를 둘까요?','느린 앞차를 추월할까요?'][hazard],body:['트럭의 적재물이 흔들리고 있습니다. 왼쪽 차로로 이동해 추월할 수 있습니다.','양옆 대형차가 같은 속도로 주행합니다. 속도를 줄여 먼저 보내세요.','주변 교통보다 느린 앞차가 있습니다. 왼쪽 차로를 확인한 뒤 추월합니다.'][hazard],action:t>4?'resolve':null,label:hazard===1?'속도 줄이기':'차로 변경하기'};
 const traveled=stopped?0:t*speed/3.6;const pose={x:offset,y:500-traveled,yaw:-90};if(route){route.index=Math.min(route.points.length-1,Math.floor(traveled/5));route.remaining_m=Math.max(0,Math.round(route.destination.distance_m-traveled));route.arrived=route.remaining_m<10}
 nav.scenario_stage=nav.status==='offered'?'offered':previewStage;nav.assistant_context={kind:['timber','buses','slow'][hazard],cuts:0,target_ids:[1]};
 return{connected:true,schema:2,map:'Preview',frame:Math.floor(now/160),ego,road:{lanes},actors,lane_width_m:3.5,world_pose:pose,destinations:atlas.destinations,session:{session_id:'preview',stage:previewStage,navigation:nav},route}
};
document.addEventListener('keydown',e=>{if(e.key==='Escape'){['music-sheet','settings-sheet','destination-panel'].forEach(id=>$(id).hidden=true);renderRoute()}});
drawMap();
})();

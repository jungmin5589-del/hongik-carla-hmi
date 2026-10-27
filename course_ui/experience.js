/* Destination-led, locally hosted CARLA passenger experience. */
(()=>{
'use strict';
const $=id=>document.getElementById(id);
const setup=$('experience-setup');
if(!setup)return;
const destinations=$('experience-destinations'),situations=$('experience-situations');
const start=$('experience-start'),feedback=$('experience-feedback'),close=$('experience-close');
const seed=$('experience-seed'),yolo=$('experience-yolo'),yoloFeedback=$('experience-yolo-feedback'),yoloIndicator=$('yolo-indicator'),yoloQuick=$('yolo-quick-toggle');
const params=new URLSearchParams(location.search);
const stateUrl='/api/state?voice_ui='+encodeURIComponent(window.PASSENGER_VOICE_UI||'split-voice-20261013');
let catalog=null,selectedDestination=null,lastStatus=null,phase='idle',busy=false,yoloBusy=false,autoResumePending=true,connectionLost=false;
const stored=(()=>{try{return JSON.parse(localStorage.getItem('carla-experience-settings')||'{}')}catch{return {}}})();
function selectedKinds(){return [...situations.querySelectorAll('input:checked')].map(x=>x.value)}
const profiles=['four_lane_loop','research_congestion','research_drowsy','seogang_congestion','seogang_drowsy'];
function isResearch(){return /^(research|seogang)_/.test(chosenProfile())}
function chosenInput(){return isResearch()?'touch':$('experience-input-mode').value}
function chosenProfile(){const value=$('experience-profile')?.value;return profiles.includes(value)?value:'random'}
function updateProfile(){
 const loop=chosenProfile()!=='random';
 destinations.hidden=loop;$('experience-situations-field').hidden=loop;
 const research=isResearch(),night=chosenProfile().endsWith('_drowsy'),street=chosenProfile().startsWith('seogang_');
 document.body.classList.toggle('research-setup',research);
 window.setResearchInteractionMode?.(research);
 $('experience-step').textContent=research?'01 / 주행 체험':'01 / 목적지 선택';
 $('experience-settings-note').textContent=research?'선택한 상황 하나를 독립적으로 실행합니다.':'선택한 상황만 순서를 섞어 반복합니다.';
 for(const id of ['experience-ai-field','experience-voice-field','experience-input-field'])$(id).hidden=research;
 $('experience-input-mode').disabled=research;
 if(research){window.setPassengerInputMode?.('touch');window.setCockpitMode?.('popup')}
 $('experience-heading').textContent=street?(night?'서강로의 밤, 앞차를 살펴보세요':'서강로를 달려볼까요?'):research?(night?'밤길, 앞차의 움직임이 달라집니다':'출발 후, 교통 흐름이 느려집니다'):loop?'4차로 고속도로를 달려볼까요?':'어디로 갈까요?';
 $('experience-intro').textContent=street?'서강로 정밀도로지도에서 복원한 차로를 따라 주행합니다. 차선·보도·가로수·주변 건물이 있는 독립 주행 체험입니다. 왼쪽 아래에서 주행 정보를 확인하고 대응을 선택하세요. 구간 끝에서는 정차합니다.':research?'독립된 주행 체험입니다. 출발 후에는 왼쪽 아래 주행 상태 버튼에서 정보를 확인하고 대응을 선택할 수 있습니다.':loop?'느린 앞차와 나란한 대형차, 촘촘한 왼쪽 차량 흐름이 이어집니다. 반대편도 4차로이며 종료할 때까지 계속 순환합니다.':'목적지를 선택하면 Town05에서 선택한 상황들이 무작위로 나타납니다. 도착 후에도 주행 화면은 열려 있습니다.';
 updateStart();
}
function chosenMode(){if(isResearch())return 'popup';return document.querySelector('input[name="experience-ui"]:checked')?.value||'popup'}
function save(){
 try{localStorage.setItem('carla-experience-settings',JSON.stringify({profile:chosenProfile(),situations:selectedKinds(),ui:chosenMode(),input_mode:chosenInput(),seed:seed.value,yolo:yolo.checked}))}catch{}
}
function syncYoloButton(){yoloQuick.textContent=yolo.checked?'켜짐':'꺼짐';yoloQuick.setAttribute('aria-label','YOLO 감지 '+(yolo.checked?'끄기':'켜기'));yoloQuick.disabled=yoloBusy}
function updateYolo(status){
 if(!status){yoloIndicator.hidden=true;return}
 if(!yoloBusy)yolo.checked=Boolean(status.enabled);
 syncYoloButton();
 yoloIndicator.hidden=!status.enabled;
 if(!status.enabled)return;
 const label=status.status==='active'?`YOLO 감지 · 차량 ${status.vehicles} · 보행자 ${status.pedestrians}`:status.status==='loading'?'YOLO 모델 준비 중':status.status==='error'?'YOLO 오류': 'YOLO 영상 분석 대기 중';
 yoloIndicator.textContent=label;
 yoloIndicator.title=status.status==='error'?(status.error||'추론 오류'):'전방 카메라의 실제 YOLO 감지 결과 · 주행 제안은 시나리오 기반';
 yoloIndicator.classList.toggle('error',status.status==='error');
 if(status.status==='error')yoloFeedback.textContent='YOLO 오류: '+(status.error||'모델을 확인해 주세요.');
}
const previousCockpitUpdate=window.CockpitUpdate;
window.CockpitUpdate=data=>{previousCockpitUpdate?.(data);updateYolo(data.session?.telemetry?.yolo)};
function updateStart(){
 const running=lastStatus?.running;
 const preparing=running&&lastStatus?.stage==='preparing';
 const loop=chosenProfile()!=='random';
 start.disabled=connectionLost||busy||running||(!loop&&(!selectedDestination||!selectedKinds().length));
 start.textContent=connectionLost?'주행 서버 연결 확인 중':busy||preparing?'주행을 준비하고 있어요…':running?'체험이 진행 중입니다':!loop&&!selectedDestination?'목적지를 선택해 주세요':!loop&&!selectedKinds().length?'상황을 하나 이상 선택해 주세요':'주행 시작';
 close.hidden=!running&&phase!=='driving';
}
function render(){
 destinations.replaceChildren();
 for(const d of catalog.destinations){
  const button=document.createElement('button');
  button.type='button';button.className='experience-destination'+(selectedDestination===d.id?' selected':'');
  button.setAttribute('aria-pressed',String(selectedDestination===d.id));
  button.innerHTML='<span class="experience-destination-icon" aria-hidden="true">⌖</span><span class="experience-destination-copy"><strong></strong><small></small></span><span class="experience-destination-distance"></span>';
  button.querySelector('strong').textContent=d.name;
  button.querySelector('small').textContent=d.detail;
  button.querySelector('.experience-destination-distance').textContent=(d.distance_m/1000).toFixed(2)+' km';
  button.onclick=()=>{selectedDestination=d.id;renderDestinationsOnly();updateStart();save()};
  destinations.appendChild(button);
 }
 situations.replaceChildren();
 const savedKinds=Array.isArray(stored.situations)?stored.situations:null;
 for(const s of catalog.situations){
  const label=document.createElement('label');label.className='experience-check';
  const input=document.createElement('input');input.type='checkbox';input.value=s.id;
  input.checked=savedKinds?savedKinds.includes(s.id):true;
  const name=document.createElement('span');name.textContent=s.name;
  label.append(input,name);situations.appendChild(label);
  input.onchange=()=>{save();updateStart()};
 }
 updateStart();
}
function open(manual=true){if(manual)autoResumePending=false;setup.hidden=false;document.body.classList.add('experience-open');$('settings-sheet').hidden=true;updateStart()}
function hide(){setup.hidden=true;document.body.classList.remove('experience-open')}
function statusText(value){feedback.textContent=value;feedback.classList.toggle('is-error',phase==='error'||connectionLost)}
async function load(){
 try{
  const response=await fetch('/api/experience',{cache:'no-store'});
  if(!response.ok)throw Error('체험 설정을 불러오지 못했습니다.');
  const data=await response.json();catalog=data.catalog;lastStatus=data.status;
  selectedDestination=null;
  const mode=stored.ui==='controls'?'controls':params.get('ui')==='controls'?'controls':'popup';
  document.querySelector('input[name="experience-ui"][value="'+mode+'"]').checked=true;
  window.setCockpitMode?.(mode);
  seed.value=/^\d+$/.test(String(stored.seed??''))?stored.seed:'';
  yolo.checked=stored.yolo===true;
  $('experience-input-mode').value=['touch','gesture_touch','gesture_swipe','voice','gesture_cursor'].includes(stored.input_mode)?stored.input_mode:'touch';
  window.setPassengerInputMode?.($('experience-input-mode').value);
  syncYoloButton();
  const profileSelect=$('experience-profile');
  for(const profile of catalog.profiles||[]){if(![...profileSelect.options].some(o=>o.value===profile.id)){const option=document.createElement('option');option.value=profile.id;option.textContent=profile.name;profileSelect.appendChild(option)}}
  render();
  const initialProfile=params.get('profile')||stored.profile;
  $('experience-profile').value=profiles.includes(initialProfile)?initialProfile:'random';
  if(data.status?.running&&data.status.config){
   $('experience-profile').value=data.status.config.profile||'random';
   selectedDestination=data.status.config.destination;
   const selected=new Set(data.status.config.situations);
   situations.querySelectorAll('input').forEach(x=>x.checked=selected.has(x.value));
   yolo.checked=Boolean(data.status.config.yolo);
   $('experience-input-mode').value=data.status.config.input_mode||'touch';
   window.setPassengerInputMode?.($('experience-input-mode').value);
   syncYoloButton();
   renderDestinationsOnly();
   phase='waiting';statusText(data.status.stage==='preparing'?'CARLA 맵과 차량을 준비하고 있어요. 아직 주행이 시작되지 않았습니다.':'진행 중인 주행에 다시 연결하고 있어요.');updateStart();
  }else if(data.status?.started&&data.status.summary?.reason==='arrived'){
   phase='arrived';statusText('목적지에 도착했습니다. 체험을 마친 뒤 다른 목적지로 다시 출발할 수 있어요.');
  }
  updateProfile();
  if(params.has('setup'))open(false);
 }catch(error){open(false);phase='error';statusText(error.message)}
}
function renderDestinationsOnly(){
 destinations.querySelectorAll('button').forEach((button,i)=>{
  const selected=catalog.destinations[i]?.id===selectedDestination;
  button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));
 });
}
document.querySelectorAll('input[name="experience-ui"]').forEach(input=>input.onchange=()=>{
 if(input.checked){window.setCockpitMode?.(input.value);save()}
});
$('experience-input-mode').onchange=()=>{window.setPassengerInputMode?.(chosenInput());save()};
seed.onchange=save;
$('experience-profile').onchange=()=>{updateProfile();save()};
yoloQuick.onclick=()=>{if(!yoloBusy)yolo.click()};
yolo.onchange=async()=>{
 const enabled=yolo.checked;save();syncYoloButton();
 if(!lastStatus?.running){yoloFeedback.textContent=enabled?'다음 주행에서 YOLO가 켜집니다.':'다음 주행에서 YOLO가 꺼집니다.';return}
 yoloBusy=true;yolo.disabled=true;syncYoloButton();yoloFeedback.textContent='차량에 YOLO 설정을 전달하고 있어요…';
 try{
  const snapshot=await(await fetch(stateUrl,{cache:'no-store'})).json();
  if(!snapshot.session?.session_id)throw Error('주행 연결을 확인할 수 없습니다.');
  const response=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:snapshot.session.session_id,action:enabled?'yolo_on':'yolo_off',request_id:crypto.randomUUID()})});
  const queued=await response.json();if(!response.ok)throw Error(queued.error||'YOLO 설정을 전달하지 못했습니다.');
  let reply=null;
  for(let i=0;i<40;i++){
   await new Promise(resolve=>setTimeout(resolve,250));
   reply=await(await fetch(`/api/reply?session=${queued.session_id}&id=${queued.command_id}`,{cache:'no-store'})).json();
   if(reply.accepted!==undefined)break;
  }
  if(reply?.accepted!==true)throw Error(reply?.message||'차량 응답이 지연되고 있습니다.');
  yoloFeedback.textContent=reply.message;
 }catch(error){yolo.checked=!enabled;save();yoloFeedback.textContent=error.message}
 finally{yoloBusy=false;yolo.disabled=false;syncYoloButton()}
};
start.onclick=async()=>{
 if(start.disabled)return;
 const request={profile:chosenProfile(),destination:selectedDestination,situations:selectedKinds(),ui:chosenMode(),input_mode:chosenInput(),yolo:yolo.checked,seed:seed.value===''?null:Number(seed.value)};
 busy=true;phase='waiting';autoResumePending=true;statusText('CARLA와 주행 화면을 준비하고 있어요. 잠시 기다려 주세요.');updateStart();save();
 try{
  const response=await fetch('/api/experience/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
  const data=await response.json();if(!response.ok)throw Error(data.error||'체험을 시작하지 못했습니다.');
  lastStatus=data;window.setCockpitMode?.(request.ui);phase='waiting';
  statusText('CARLA를 연결하는 중입니다. 연결 후 화면에서 출발을 선택해 주세요.');
 }catch(error){phase='error';statusText(error.message)}
 finally{busy=false;updateStart()}
};
close.onclick=hide;
$('experience-open').onclick=()=>open();
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!setup.hidden&&!close.hidden)hide()});
async function poll(){
 if(busy)return;
 if(!catalog){await load();return}
 try{
  const response=await fetch('/api/experience',{cache:'no-store'});if(!response.ok)throw Error('주행 서버 상태를 확인하지 못했습니다.');
  const {status}=await response.json();connectionLost=false;lastStatus=status;updateStart();
  if(status.running&&status.stage==='preparing')statusText('CARLA 맵과 차량을 준비하고 있어요. 아직 주행이 시작되지 않았습니다.');
  if(status.running){
   const snapshot=await(await fetch(stateUrl,{cache:'no-store'})).json();
   if(!yoloBusy&&snapshot.session?.telemetry?.yolo)updateYolo(snapshot.session.telemetry.yolo);
   if(snapshot.session?.navigation?.status==='arrived'){
    phase='driving';statusText('목적지에 도착했습니다. 주행 화면은 그대로 열려 있습니다. 내비게이션에서 체험 마치기를 누르면 종료됩니다.');
   }
  }else updateYolo(null);
  if(status.running&&(phase==='waiting'||autoResumePending)){
   const state=await(await fetch(stateUrl,{cache:'no-store'})).json();
   if(state.connected&&state.session&&['ready','running'].includes(state.session.stage)&&(!status.session_id||status.session_id===state.session.session_id)){
    phase='driving';autoResumePending=false;statusText(state.session.stage==='ready'?'주행 준비가 완료됐습니다. 화면에서 출발을 선택해 주세요.':'주행에 다시 연결됐습니다.');hide();
   }
  }else if(status.started&&!status.running&&phase!=='arrived'&&phase!=='error'){
   const reason=status.summary?.reason;
   if(reason==='arrived'){
    phase='arrived';statusText('목적지에 도착했습니다. 체험을 마쳤으니 다른 목적지로 다시 출발할 수 있어요.');open();
   }else if(reason==='exit'){
    phase='arrived';statusText('주행 창 닫기 또는 Esc 키로 체험을 종료했습니다. 다시 출발할 수 있어요.');open();
   }else{
    phase='error';
    const detail=status.error||status.summary?.error||reason||'원인을 확인하지 못했습니다.';
    statusText('주행 체험이 종료되었습니다: '+detail);open();
   }
  }
 }catch{connectionLost=true;statusText('주행 서버에 연결되지 않습니다. 36번 앱을 다시 열거나 현재 실행 중인 내비 주소를 확인해 주세요.');updateStart()}
}
load().then(()=>setInterval(poll,1200));
})();

(()=>{
 const $=id=>document.getElementById(id),cards=[...document.querySelectorAll('[data-profile]')];
 const profiles={congestion:{name:'4차로 저속 차량',detail:'약 600m 실제 도로에서 앞차와 오른쪽 대형차는 25~35km/h로 속도를 달리하고, 왼쪽 차량은 90km/h 목표로 주행합니다.'},night:{name:'야간 불안정한 앞차',detail:'밤길에서 앞차의 불안정한 움직임을 체험합니다. 현재는 짧은 촬영 구간입니다.'},fog:{name:'짙은 안개',detail:'기존 고속도로에서 약 5분간 주행합니다. 출발 30초 뒤 안개가 점점 짙어집니다.'}};
 let selected='congestion',busy=false,launch=null;
 try{$('voice').checked=localStorage.getItem('nurec-sohee-enabled')!=='false'}catch{}
 $('voice').onchange=()=>{try{localStorage.setItem('nurec-sohee-enabled',String($('voice').checked))}catch{}};
 function select(profile){if(busy)return;selected=profile;for(const card of cards)card.setAttribute('aria-checked',String(card.dataset.profile===profile));$('selected-name').textContent=profiles[profile].name;$('selected-detail').textContent=profiles[profile].detail;$('duration-field').hidden=true;$('duration-note').textContent=(profile==='fog'?'최대 약 5분 · 일시정지 시간 제외':profile==='night'?'현재는 짧은 촬영 구간으로 진행합니다.':'25~35km/h로 약 1분대 · 촬영 구간 끝까지 진행합니다.')+' 대응 실행 시 결과를 확인한 뒤 종료됩니다.'}
 for(const card of cards)card.onclick=()=>select(card.dataset.profile);
 function lock(value){busy=value;$('open-trial').disabled=value;$('duration').disabled=value;$('performance').disabled=value;for(const card of cards)card.disabled=value;$('open-trial').textContent=value?'주행을 준비하고 있어요…':'내비게이션으로 이동'}
 $('open-trial').onclick=async()=>{
  if(busy)return;lock(true);$('status').textContent='선택한 주행을 준비하고 있어요.';$('open-ready').hidden=true;
  try{
   const response=await fetch('/api/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:selected,performance:$('performance').value,duration_s:selected==='congestion'?Number($('duration').value):300,request_id:crypto.randomUUID()})});
   const result=await response.json();if(!response.ok)throw Error(result.error||'체험을 준비하지 못했습니다.');launch=result.launch_id;poll();
  }catch(error){$('status').textContent=error.message;lock(false)}
 };
 async function poll(){
  if(!busy)return;
  try{
   const response=await fetch('/api/status',{cache:'no-store'});if(!response.ok)throw Error('연결을 확인하고 있어요.');
   const state=await response.json();if(state.launch_id!==launch)throw Error('선택 화면이 변경됐어요. 다시 선택해 주세요.');
   if(state.phase==='failed'){lock(false);$('status').textContent=state.error||'체험을 준비하지 못했어요.';return}
   if(state.phase==='ready'){
    $('status').textContent='준비됐어요. 내비게이션으로 이동합니다.';
    const target='http://127.0.0.1:8774/navigation?voice='+($('voice').checked?'1':'0');
    $('open-ready').href=target;$('open-ready').hidden=false;location.assign(target);return;
   }
   $('status').textContent=state.phase==='warming'?'실사 도로를 불러오고 있어요. 첫 준비에는 몇 분 걸릴 수 있습니다.':'선택한 도로와 주행 화면을 준비하고 있어요.';
  }catch(error){$('status').textContent=error.message||'연결을 확인하고 있어요.'}
  setTimeout(poll,1000);
 }
 select(selected);
})();

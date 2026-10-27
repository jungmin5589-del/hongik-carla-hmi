/* Optional depth of information. Opening details never executes a vehicle action. */
(()=>{
'use strict';
const root=document.createElement('div');root.id='research-ui';root.hidden=true;
root.innerHTML=`<button id="research-launch" type="button" aria-label="주행 상태 확인" aria-expanded="false">
 <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3 5 21M16 3l3 18M12 5v3m0 4v3m0 4v2"/></svg>
 <span><strong>주행 상태</strong><small id="research-badge">정보 확인</small></span><i id="research-unread" hidden></i></button>
 <section id="research-dialog" hidden role="dialog" aria-modal="false" aria-labelledby="research-title">
 <header><span>주행 정보</span><button type="button" id="research-close" aria-label="주행 정보 닫기">×</button></header>
 <div class="research-dialog-content"><p id="research-caption">현재 상황</p><h2 id="research-title"></h2>
 <p id="research-description"></p><div id="research-feedback" role="status" hidden></div>
 <button id="research-options-open" class="research-primary" type="button">대응 방법 보기 <span aria-hidden="true">→</span></button>
 <div id="research-options" hidden></div>
 <div id="research-confirmation" hidden><p id="research-confirm-copy"></p><div class="research-confirm-actions">
 <button id="research-back" type="button">선택 취소</button><button id="research-execute" type="button" class="research-primary">실행</button></div></div>
 </div></section>`;
document.body.appendChild(root);
const $=id=>document.getElementById(id),launch=$('research-launch'),dialog=$('research-dialog');
let current=null,event=null,session=null,seen=null,unread=false,phase='detail',selected=null,busy=false,lastFocus=null;
const previous=window.CockpitUpdate;
async function post(action,details={},wait=false){
 const snapshot=session,nav=current;
 if(!snapshot||!nav)return null;
 const response=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
  session_id:snapshot.session_id,navigation_id:nav.id,action,request_id:crypto.randomUUID(),
  client_event:{phase,client_ms:performance.now(),event_visible:event?.active===true,...details}
 })});
 const queued=await response.json();if(!response.ok)throw Error(queued.error||'요청을 전달하지 못했습니다.');
 if(!wait)return queued;
 for(let i=0;i<40;i++){
  await new Promise(resolve=>setTimeout(resolve,250));
  if(session?.session_id!==snapshot.session_id)throw Error('주행 연결이 변경되었습니다.');
  const result=await(await fetch(`/api/reply?session=${queued.session_id}&id=${queued.command_id}`,{cache:'no-store'})).json();
  if(result.accepted===false)throw Error(result.message||'요청이 실행되지 않았습니다.');
  if(result.accepted===true)return result;
 }
 throw Error('차량 응답을 확인하지 못했습니다. 다시 누르기 전에 현재 상태를 확인해 주세요.');
}
function record(action,details){post(action,details).catch(()=>{/* Network failures must not create an extra vehicle action. */})}
function feedback(text){$('research-feedback').textContent=text;$('research-feedback').hidden=!text}
function render(){
 if(!event)return;
 $('research-title').textContent=event.title;
 $('research-description').textContent=event.description;
 $('research-caption').textContent=event.active?'현재 상황과 차량의 판단':'현재 주행';
 $('research-badge').textContent=unread?'새 주행 정보':'정보 확인';
 $('research-unread').hidden=!unread;
 $('research-options-open').hidden=!event.active||phase!=='detail';
 $('research-options-open').disabled=busy||Boolean(event.pending);
 $('research-options').hidden=phase!=='options';
 $('research-confirmation').hidden=phase!=='confirm';
 $('research-execute').disabled=busy||Boolean(event.pending);
 $('research-back').disabled=busy;
 if(!busy)feedback(event.feedback);
 if(phase==='options'){
  $('research-options').replaceChildren();
  for(const option of event.options||[]){
   const button=document.createElement('button');button.type='button';button.className='research-option';
   const label=document.createElement('strong'),detail=document.createElement('small');
   label.textContent=option.label;detail.textContent=option.detail;button.append(label,detail);
   button.disabled=busy||Boolean(event.pending);
   button.onclick=()=>{selected=option;phase='confirm';$('research-confirm-copy').textContent=option.label+' 요청을 실행할까요? '+option.detail;render();$('research-execute').focus()};
   $('research-options').appendChild(button);
  }
 }
}
function close(){
 if(dialog.hidden)return;
 record('study_close',{choice:selected?.action||'',phase});dialog.hidden=true;phase='detail';selected=null;
 launch.setAttribute('aria-expanded','false');lastFocus?.focus();
}
launch.onclick=()=>{
 if(!dialog.hidden){close();return}
 lastFocus=document.activeElement;phase='detail';selected=null;dialog.hidden=false;unread=false;
 launch.classList.remove('has-update');launch.setAttribute('aria-expanded','true');
 record('study_open');render();$('research-close').focus();
};
$('research-close').onclick=close;
$('research-options-open').onclick=()=>{phase='options';selected=null;record('study_options');render()};
$('research-back').onclick=()=>{phase='options';selected=null;render()};
$('research-execute').onclick=async()=>{
 if(!selected||busy||event?.pending)return;
 const action=selected.action,expectedSession=session?.session_id;
 busy=true;feedback('차량에 요청을 전달하고 있습니다.');render();
 try{
  const result=await post(action,{choice:action},true);
  if(session?.session_id!==expectedSession)return;
  phase='detail';selected=null;
  if(result?.message){event={...event,feedback:result.message};feedback(result.message)}
 }catch(error){if(session?.session_id===expectedSession){phase='detail';selected=null;event={...event,feedback:error.message};feedback(error.message)}}
 finally{busy=false;render()}
};
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!dialog.hidden){e.preventDefault();close()}});
window.CockpitUpdate=data=>{
 previous?.(data);
 const next=data.session?.navigation?.research_event;
 const live=Boolean(next&&data.connected&&['ready','running'].includes(data.session?.stage));
 root.hidden=!live;document.body.classList.toggle('research-driving',live);
 if(!live){dialog.hidden=true;seen=null;session=null;current=null;event=null;busy=false;return}
 if(session?.session_id!==data.session.session_id){
  seen=null;unread=false;phase='detail';selected=null;busy=false;dialog.hidden=true;launch.classList.remove('has-update');launch.setAttribute('aria-expanded','false');
 }
 session=data.session;current=session.navigation;event=next;
 launch.disabled=session.stage!=='running';
 if(event.active&&seen!==current.id){
  seen=current.id;unread=dialog.hidden;
  if(dialog.hidden)launch.classList.add('has-update');
  record('study_presented',{alert_presented:true,phase:dialog.hidden?'button':'detail'});
 }
 render();
};
})();

/* Experiment input only. Recognition proposes a request; execution always needs confirmation. */
(()=>{
'use strict';
let data=null,pending=null,source='text',recording=null,session='',notice=0,ack=0,recognized='',ready=false,busy=false;
const box=document.createElement('section');box.id='experiment-request';box.hidden=true;
box.innerHTML=`<h3 class="experiment-heading">직접 요청하기</h3><p id="experiment-stage"></p>
<div class="experiment-inputs"><button id="experiment-mic" type="button">말로 요청하기</button><button id="experiment-type" type="button" aria-expanded="false">글로 입력하기</button></div><span id="experiment-stt"></span>
<form hidden><label for="experiment-text">원하는 대응을 입력해 주세요</label><input id="experiment-text" maxlength="1000" placeholder="원하는 대응을 입력하세요"><button class="research-primary">요청 확인</button></form>
<div><button id="experiment-confirm" class="research-primary" type="button" hidden>이 요청 실행</button><button id="experiment-cancel" type="button" hidden>선택 취소</button></div>
<p id="experiment-message" role="status" aria-live="polite"></p><p id="experiment-result"></p>
<button id="experiment-stop" type="button" hidden>요청 중단</button><button id="experiment-home" type="button" hidden>회차 종료 · 실험 진행으로</button>`;
const requestHost=document.querySelector('#research-dialog .midterm-choices');
if(!requestHost)return;requestHost.prepend(box);
const style=document.createElement('style');style.textContent=`
#experiment-request{position:static;width:auto;max-width:none;margin:0 0 24px;padding:0 0 22px;border:0;border-bottom:1px solid #e9edf3;background:transparent;box-shadow:none;color:#26354c;font:inherit}
#experiment-request[hidden]{display:none}
#experiment-request .experiment-heading{margin:0 0 8px;font-size:20px;font-weight:750;letter-spacing:-.025em}
#experiment-request label{display:block;margin:0 0 14px;font-size:15px;line-height:1.6;font-weight:550;color:#64738a}
#experiment-request form{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center}
#experiment-request form label{grid-column:1/-1}
#experiment-request input{box-sizing:border-box;min-width:0;width:100%;height:52px;padding:0 16px;background:#f5f7fa;border:1px solid #dce3ee;border-radius:12px;color:#26354c;font:550 16px Pretendard,Arial,sans-serif}
#experiment-request input:focus{outline:3px solid #3e6ae126;border-color:#3e6ae1;background:white}
#experiment-request button{min-height:48px;padding:12px 18px;margin:0;border:1px solid #dce3ee;border-radius:12px;background:white;color:#3e6ae1;font:650 16px Pretendard,Arial,sans-serif;cursor:pointer}
#experiment-request button.research-primary{background:#3e6ae1;border-color:#3e6ae1;color:white}
#experiment-request button:hover{filter:brightness(.97)}#experiment-request button:focus-visible{outline:3px solid #89a5ff;outline-offset:3px}
#experiment-request button:disabled{opacity:.5;cursor:default}
#experiment-request .experiment-inputs{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;margin:0}#experiment-mic{min-height:76px!important;background:#3e6ae1!important;border-color:#3e6ae1!important;color:white!important;font-size:20px!important}#experiment-type{min-height:76px!important}#experiment-stt{display:block;margin-top:8px;color:#7a8696;font-size:12px;line-height:1.5}
#experiment-request>div{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
#experiment-stage{margin:0 0 12px;color:#7a8696;font-size:13px}#experiment-stage:empty,#experiment-message:empty,#experiment-result:empty{display:none}
#experiment-message{padding:16px 18px;margin:16px 0 0;background:#f1f5fc;border-radius:12px;font-size:16px;line-height:1.65;font-weight:600}
#experiment-result{color:#64738a;font-size:14px;line-height:1.65}#experiment-request button[hidden],#experiment-request form[hidden]{display:none}
#research-options .research-option.suggested{border-color:#3e6ae1!important;box-shadow:0 0 0 3px #3e6ae133!important;background:#f3f6ff!important}
#experiment-request form{margin-top:16px}
body.experiment-off #research-launch,body.experiment-off #midterm-passive,body.experiment-off #research-dialog{display:none!important}
body.experiment-practice .midterm-explanation,body.experiment-practice .midterm-choices>*:not(#experiment-request){display:none!important}
body.experiment-practice .research-dialog-content{grid-template-columns:1fr;max-width:680px;margin:auto}
body.experiment-practice #experiment-request{border:0;padding:0;margin:0}
@media(max-width:600px){#experiment-request form{grid-template-columns:minmax(0,1fr)}#experiment-request form label{grid-column:auto}#experiment-request form button{width:100%}}
`;document.head.append(style);
const q=id=>box.querySelector('#experiment-'+id),msg=q('message'),confirm=q('confirm'),cancel=q('cancel'),mic=q('mic');
let typing=false;q('type').onclick=()=>{typing=!typing;q('type').setAttribute('aria-expanded',String(typing));box.querySelector('form').hidden=!typing;if(typing)q('text').focus()};
function suggest(action){for(const b of document.querySelectorAll('#research-options .research-option.suggested'))b.classList.remove('suggested');confirm.textContent='이 요청 실행';if(!action)return;const b=document.querySelector('#research-options [data-action="study_'+action+'"]');if(b){b.classList.add('suggested');confirm.textContent=b.querySelector('strong')?.textContent+' 실행'}}
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok||d.error)throw Error(d.error||'요청을 전달하지 못했어요.');return d}
async function propose(text,via){if(busy)return;busy=true;source=via;pending=null;confirm.hidden=cancel.hidden=true;try{const r=await post('/api/experiment/request',{session_id:data.session.session_id,text,source});msg.textContent=r.message;if(r.supported){pending={text,session:data.session.session_id};confirm.hidden=cancel.hidden=false;suggest(r.action)}}catch(e){msg.textContent=e.message}finally{busy=false}}
box.querySelector('form').onsubmit=e=>{e.preventDefault();propose(q('text').value,'text')};
confirm.onclick=async()=>{if(!pending||busy)return;busy=true;confirm.disabled=true;try{const r=await post('/api/experiment/request',{session_id:pending.session,text:pending.text,source,execute:true});msg.textContent=r.message;pending=null;confirm.hidden=cancel.hidden=true;suggest(null)}catch(e){msg.textContent=e.message}finally{busy=false;confirm.disabled=false}};
cancel.onclick=()=>{pending=null;confirm.hidden=cancel.hidden=true;suggest(null);msg.textContent='실행 전 선택을 취소했어요.'};
q('stop').onclick=async()=>{try{const s=data.session;await post('/api/command',{session_id:s.session_id,navigation_id:s.navigation.id,action:'study_cancel_pending',request_id:crypto.randomUUID(),client_event:{source:'experiment_request_card'}});msg.textContent='요청을 중단하고 현재 상태를 확인하고 있어요.'}catch(e){msg.textContent=e.message}};
q('home').onclick=()=>{if(window.HongikSurvey?.require())return;location.href=window.HONGIK_TABLET?'/navigation':'/experiment'};
async function sttStatus(){try{const s=await(await fetch('/api/stt/status')).json();ready=s.state==='ready';q('stt').textContent=ready?(window.isSecureContext?'말하기를 누른 뒤 요청해 주세요.':'음성 요청은 보안 연결에서 사용할 수 있어요.'):'음성 요청을 준비하고 있어요. 입력으로도 요청할 수 있어요.';mic.disabled=!ready||!window.isSecureContext}catch{ready=false;mic.disabled=true}}
sttStatus();setInterval(()=>{if(!box.hidden&&!recording)sttStatus()},5000);
function wav(chunks,samples,rate){const buffer=new ArrayBuffer(44+samples*2),v=new DataView(buffer);const str=(o,s)=>{for(let i=0;i<s.length;i++)v.setUint8(o+i,s.charCodeAt(i))};str(0,'RIFF');v.setUint32(4,36+samples*2,true);str(8,'WAVEfmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,rate,true);v.setUint32(28,rate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);str(36,'data');v.setUint32(40,samples*2,true);let at=44;for(const a of chunks)for(const x of a){v.setInt16(at,Math.max(-1,Math.min(1,x))*32767,true);at+=2}let b='';for(const x of new Uint8Array(buffer))b+=String.fromCharCode(x);return btoa(b)}
mic.onclick=async()=>{if(recording){recording();return}if(!ready||busy||!data)return;
let stream,ctx;
try{
 if(!navigator.mediaDevices?.getUserMedia)throw Error('Safari의 HTTPS 연결에서 마이크를 사용해 주세요.');
 stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});ctx=new AudioContext();await ctx.resume();
 const sid=data.session.session_id,src=ctx.createMediaStreamSource(stream),node=ctx.createScriptProcessor(4096,1,1),chunks=[];let samples=0,voiced=0,quiet=0,timer;
 src.connect(node);node.connect(ctx.destination);mic.textContent='녹음 끝내기';
 node.onaudioprocess=e=>{const a=new Float32Array(e.inputBuffer.getChannelData(0));chunks.push(a);samples+=a.length;const rms=Math.sqrt(a.reduce((s,x)=>s+x*x,0)/a.length),dt=a.length/ctx.sampleRate;if(rms>.012){voiced+=dt;quiet=0}else quiet+=dt;if(voiced>.35&&quiet>.7)recording?.()};
 recording=async()=>{if(!recording)return;clearTimeout(timer);recording=null;node.onaudioprocess=null;node.disconnect();src.disconnect();stream.getTracks().forEach(t=>t.stop());const rate=ctx.sampleRate;await ctx.close();mic.textContent='말로 요청하기';mic.disabled=true;msg.textContent='음성을 해석하고 있어요…';
 try{if(data.session.session_id!==sid)throw Error('주행이 바뀌었어요. 다시 말해 주세요.');const r=await post('/api/stt/transcribe',{audio:wav(chunks,samples,rate),language:window.HongikLocale?.lang||'ko'});if(!r.job)throw Error('음성 모델의 상태를 확인해 주세요.');const end=Date.now()+90000;while(Date.now()<end){const j=await(await fetch('/api/stt/jobs/'+r.job)).json();if(data.session.session_id!==sid)throw Error('주행이 바뀌었어요. 다시 말해 주세요.');if(j.state==='done'){recognized='음성 처리 '+(j.processing_ms/1000).toFixed(1)+'초';q('text').value=j.text;if(!j.text)throw Error('말소리를 인식하지 못했어요. 다시 말해 주세요.');await propose(j.text,'voice');return}if(j.error)throw Error(j.error);await new Promise(r=>setTimeout(r,300))}throw Error('인식이 지연됐어요. 입력으로 요청해 주세요.')}catch(e){msg.textContent=e.message}finally{mic.disabled=false}}
 timer=setTimeout(()=>recording?.(),10000);
}catch(e){stream?.getTracks().forEach(t=>t.stop());ctx?.close();msg.textContent='마이크 연결을 확인해 주세요. '+e.message}};
const old=window.CockpitUpdate;window.CockpitUpdate=d=>{old?.(d);data=d;const p=d.experiment,sid=d.session?.session_id,event=d.session?.navigation?.research_event,study=event?.study,complete=d.nurec?.scenario?.completed;
 document.body.classList.toggle('experiment-off',Boolean(p&&!p.ai_enabled));document.body.classList.toggle('experiment-practice',Boolean(p?.practice));box.hidden=!p||!p.ai_enabled;
 if(!p)return;
 const depart=document.getElementById('passenger-depart');if(depart&&d.nurec?.scenario?.elapsed_s===0){depart.disabled=d.nurec?.departure_ready===false;depart.textContent=depart.disabled?'주행 준비 중…':'출발'}
 if(session!==sid){session=sid;pending=null;notice=0;ack=0;recognized='';confirm.hidden=cancel.hidden=true;suggest(null);msg.textContent='';recording?.()}
 const phases={idle:'대기',queued:'실행 전 · 취소 가능',applying:'실행 중',observing:'결과 확인 중',stopping:'정차 중',complete:'완료'};
 q('stage').textContent=p.practice?'연습 · 온도를 22도로 설정해 보세요.':('내 요청 · '+(p.watching?(p.notified?'변화 알림 · 반응 확인 중':'상황 변화 확인 중'):phases[study?.phase]||'대기'));
 q('result').textContent=[event?.feedback||p.feedback,event?.outcome?.summary].filter(Boolean).join(' · ');
 q('stop').hidden=!(p.watching||study?.cancellable);q('home').hidden=!complete;mic.hidden=Boolean(complete);box.querySelector('form').hidden=Boolean(complete)||!typing;q('type').hidden=Boolean(complete);
 if(['queued','applying','observing','stopping'].includes(study?.phase)){box.querySelector('form').hidden=true;mic.hidden=true;q('type').hidden=true;confirm.hidden=cancel.hidden=true;pending=null}
 if(p.request_serial>ack){ack=p.request_serial;msg.textContent=p.feedback;if(p.last_request==='explain')window.HongikStudyVoice?.read();else window.HongikFeedback?.say('intent:'+p.last_request)}
 if(p.notified&&p.notice_id>notice){notice=p.notice_id;msg.textContent=p.notice;window.HongikFeedback?.say(p.profile==='congestion'?'watch_gap':'watch_risk')}
 if(p.practice){const temp=document.getElementById('temperature');if(temp)temp.textContent=p.temperature.toFixed(1)+'°'}
};
})();

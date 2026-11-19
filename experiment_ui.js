/* Experiment input only. Recognition proposes a request; execution always needs confirmation. */
(()=>{
'use strict';
let data=null,pending=null,source='text',recording=null,session='',notice=0,ack=0,recognized='',ready=false,busy=false;
const box=document.createElement('section');box.id='experiment-request';box.hidden=true;
box.innerHTML=`<strong>홍익 AI · 내 요청</strong><p id="experiment-stage"></p>
<form><label for="experiment-text">직접 요청하기</label><input id="experiment-text" maxlength="1000" placeholder="원하는 대응을 입력하세요"><button>요청 확인</button></form>
<button id="experiment-mic" type="button">말하기</button><span id="experiment-stt"></span>
<div><button id="experiment-confirm" type="button" hidden>이 요청 실행</button><button id="experiment-cancel" type="button" hidden>선택 취소</button></div>
<p id="experiment-message" role="status" aria-live="polite"></p><p id="experiment-result"></p>
<button id="experiment-stop" type="button" hidden>요청 중단</button><button id="experiment-home" type="button" hidden>회차 종료 · 실험 진행으로</button>`;
document.body.append(box);
const style=document.createElement('style');style.textContent=`#experiment-request{position:fixed;right:22px;bottom:104px;width:320px;max-width:43vw;max-height:65vh;overflow:auto;background:white;border:1px solid #dce3ed;border-radius:16px;padding:18px;z-index:65;font:14px/1.45 system-ui;box-shadow:0 6px 25px #0002}#experiment-request[hidden]{display:none}#experiment-request input{width:94%;padding:9px;border:1px solid #bac7dd;border-radius:8px}#experiment-request label{display:block;margin:8px 0}#experiment-request button{padding:9px;margin:5px 3px;border:0;border-radius:8px;background:#edf2ff;color:#244baf;cursor:pointer}#experiment-request button:disabled{opacity:.5}#experiment-stt{font-size:11px;color:#69778c}#experiment-message{padding:10px;background:#f3f6fd;border-radius:8px}body.experiment-off #research-launch,body.experiment-off #midterm-passive,body.experiment-off #research-dialog{display:none!important}`;document.head.append(style);
const q=id=>box.querySelector('#experiment-'+id),msg=q('message'),confirm=q('confirm'),cancel=q('cancel'),mic=q('mic');
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok||d.error)throw Error(d.error||'요청을 전달하지 못했어요.');return d}
async function propose(text,via){if(busy)return;busy=true;source=via;pending=null;confirm.hidden=cancel.hidden=true;try{const r=await post('/api/experiment/request',{session_id:data.session.session_id,text,source});msg.textContent=r.message;if(r.supported){pending={text,session:data.session.session_id};confirm.hidden=cancel.hidden=false}}catch(e){msg.textContent=e.message}finally{busy=false}}
box.querySelector('form').onsubmit=e=>{e.preventDefault();propose(q('text').value,'text')};
confirm.onclick=async()=>{if(!pending||busy)return;busy=true;confirm.disabled=true;try{const r=await post('/api/experiment/request',{session_id:pending.session,text:pending.text,source,execute:true});msg.textContent=r.message;pending=null;confirm.hidden=cancel.hidden=true}catch(e){msg.textContent=e.message}finally{busy=false;confirm.disabled=false}};
cancel.onclick=()=>{pending=null;confirm.hidden=cancel.hidden=true;msg.textContent='실행 전 선택을 취소했어요.'};
q('stop').onclick=async()=>{try{const s=data.session;await post('/api/command',{session_id:s.session_id,navigation_id:s.navigation.id,action:'study_cancel_pending',request_id:crypto.randomUUID(),client_event:{source:'experiment_request_card'}});msg.textContent='요청을 중단하고 현재 상태를 확인하고 있어요.'}catch(e){msg.textContent=e.message}};
q('home').onclick=()=>{location.href=window.HONGIK_TABLET?'/navigation':'/experiment'};
async function sttStatus(){try{const s=await(await fetch('/api/stt/status')).json();ready=s.state==='ready';q('stt').textContent=ready?'로컬 음성 인식 준비됨':s.state==='loading'?'음성 모델 준비 중':'PC에서 음성 모델을 준비해 주세요.';mic.disabled=!ready||!window.isSecureContext}catch{ready=false;mic.disabled=true}}
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
 recording=async()=>{if(!recording)return;clearTimeout(timer);recording=null;node.onaudioprocess=null;node.disconnect();src.disconnect();stream.getTracks().forEach(t=>t.stop());const rate=ctx.sampleRate;await ctx.close();mic.textContent='말하기';mic.disabled=true;msg.textContent='음성을 해석하고 있어요…';
 try{if(data.session.session_id!==sid)throw Error('주행이 바뀌었어요. 다시 말해 주세요.');const r=await post('/api/stt/transcribe',{audio:wav(chunks,samples,rate),language:window.HongikLocale?.lang||'ko'});if(!r.job)throw Error('음성 모델의 상태를 확인해 주세요.');const end=Date.now()+90000;while(Date.now()<end){const j=await(await fetch('/api/stt/jobs/'+r.job)).json();if(data.session.session_id!==sid)throw Error('주행이 바뀌었어요. 다시 말해 주세요.');if(j.state==='done'){recognized='음성 처리 '+(j.processing_ms/1000).toFixed(1)+'초';q('text').value=j.text;if(!j.text)throw Error('말소리를 인식하지 못했어요. 다시 말해 주세요.');await propose(j.text,'voice');return}if(j.error)throw Error(j.error);await new Promise(r=>setTimeout(r,300))}throw Error('인식이 지연됐어요. 입력으로 요청해 주세요.')}catch(e){msg.textContent=e.message}finally{mic.disabled=false}}
 timer=setTimeout(()=>recording?.(),10000);
}catch(e){stream?.getTracks().forEach(t=>t.stop());ctx?.close();msg.textContent='마이크 연결을 확인해 주세요. '+e.message}};
const old=window.CockpitUpdate;window.CockpitUpdate=d=>{old?.(d);data=d;const p=d.experiment,sid=d.session?.session_id,event=d.session?.navigation?.research_event,study=event?.study,complete=d.nurec?.scenario?.completed;
 document.body.classList.toggle('experiment-off',Boolean(p&&(!p.ai_enabled||p.practice)));box.hidden=!p||!p.ai_enabled;
 if(!p)return;
 if(session!==sid){session=sid;pending=null;notice=0;ack=0;recognized='';confirm.hidden=cancel.hidden=true;msg.textContent='';recording?.()}
 const phases={idle:'대기',queued:'실행 전 · 취소 가능',applying:'실행 중',observing:'결과 확인 중',stopping:'정차 중',complete:'완료'};
 q('stage').textContent=p.practice?'연습 · 온도를 22도로 설정해 보세요.':('내 요청 · '+(p.watching?(p.notified?'변화 알림 · 반응 확인 중':'상황 변화 확인 중'):phases[study?.phase]||'대기'));
 q('result').textContent=[recognized,event?.feedback||p.feedback,event?.outcome?.summary].filter(Boolean).join(' · ');
 q('stop').hidden=!(p.watching||study?.cancellable);q('home').hidden=!complete;mic.hidden=Boolean(complete);box.querySelector('form').hidden=Boolean(complete);
 if(['queued','applying','observing','stopping'].includes(study?.phase)){box.querySelector('form').hidden=true;mic.hidden=true;confirm.hidden=cancel.hidden=true;pending=null}
 if(p.request_serial>ack){ack=p.request_serial;msg.textContent=p.feedback;if(p.last_request==='explain')window.HongikStudyVoice?.read();else window.HongikFeedback?.say('intent:'+p.last_request)}
 if(p.notified&&p.notice_id>notice){notice=p.notice_id;msg.textContent=p.notice;window.HongikFeedback?.say(p.profile==='congestion'?'watch_gap':'watch_risk')}
 if(p.practice){const temp=document.getElementById('temperature');if(temp)temp.textContent=p.temperature.toFixed(1)+'°'}
};
})();

/* Local Qwen Sohee audio; cancel pending requests and never play stale speech. */
(()=>{
class QwenSpeechTransport {
 constructor({provider='qwen'}={}){this.player=null;this.controller=null;this.provider=provider;this.label=provider==='supertonic'?'Supertonic F3':'Sohee';this.client=globalThis.crypto?.randomUUID?.()||Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);this.lease=null;this.heartbeatTimer=null}
 async leasePost(action,body,signal){const response=await fetch('/api/speech/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,voice_ui:globalThis.PASSENGER_VOICE_UI||'split-voice-20261013'}),signal,keepalive:action==='release'});const result=await response.json();if(!response.ok)throw Error(result.error||'음성 재생 권한 요청 실패');return result}
 releaseLease(){clearTimeout(this.heartbeatTimer);this.heartbeatTimer=null;const lease=this.lease;this.lease=null;if(lease)this.leasePost('release',lease).catch(()=>{})}
 cancel(){this.controller?.abort();this.controller=null;if(this.player){this.player.pause();this.player.removeAttribute('src');this.player.load();this.player=null}this.releaseLease()}
 async speak(text,{onstart,onend,onerror,kind='navigation',speechRole='assistant',parts}){
  this.cancel();const controller=new AbortController();this.controller=controller;const signal=controller.signal;
  try{
   const response=await fetch('/api/tts/synthesize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,parts,provider:this.provider,speech_role:kind==='assistant'?(speechRole==='briefing'?'briefing':'assistant'):'navigation',voice_ui:globalThis.PASSENGER_VOICE_UI||'split-voice-20261013'}),signal});
   let result=await response.json();if(!response.ok)throw Error(result.error||this.label+' 음성 요청 실패');const jobId=result.job_id;
   for(let i=0;result.status!=='complete'&&i<1200;i++){
    await new Promise((resolve,reject)=>{const cancelled=()=>{clearTimeout(timer);reject(new DOMException('Cancelled','AbortError'))};const timer=setTimeout(()=>{signal.removeEventListener('abort',cancelled);resolve()},100);signal.addEventListener('abort',cancelled,{once:true})});
    if(signal.aborted)return;
    result=await(await fetch('/api/tts/job?id='+jobId,{cache:'no-store',signal})).json();
    if(result.error)throw Error(result.error);
   }
   if(signal.aborted)return;if(!result.url)throw Error(this.label+' 음성 준비 시간이 초과됐습니다.');
   if(globalThis.document){
    const role=kind==='assistant'?'assistant':'navigation';let granted;
    for(let i=0;i<100;i++){
     if(signal.aborted)return;granted=await this.leasePost('claim',{client:this.client,role},signal);
     if(granted.granted)break;
     if(!granted.waiting){onend();return}
     await new Promise(resolve=>setTimeout(resolve,100));
    }
    if(signal.aborted){if(granted?.granted)this.leasePost('release',{client:this.client,token:granted.token}).catch(()=>{});return}
    if(!granted?.granted)throw Error('다른 화면의 음성을 중단하지 못했습니다.');
    this.lease={client:this.client,token:granted.token};
    const beat=async()=>{if(signal.aborted)return;try{const state=await this.leasePost('heartbeat',this.lease,signal);if(signal.aborted||this.controller!==controller)return;if(!state.active){this.cancel();onend();return}this.heartbeatTimer=setTimeout(beat,250)}catch(error){if(!signal.aborted){this.cancel();onerror(error)}}};
    this.heartbeatTimer=setTimeout(beat,250);
   }
   const player=new Audio(result.url);this.player=player;player.volume=1;
   player.onplaying=()=>{if(!signal.aborted)onstart()};player.onended=()=>{if(!signal.aborted){this.player=null;this.releaseLease();onend()}};
   player.onerror=()=>{if(!signal.aborted){this.releaseLease();onerror(Error(this.label+' 음성을 재생하지 못했습니다.'))}};
   await player.play();
  }catch(error){if(this.controller===controller)this.releaseLease();if(!signal.aborted)onerror(error)}
 }
}
globalThis.QwenSpeechTransport=QwenSpeechTransport;
})();

/* Scene sound belongs to one armed navigation tab, including behind the 3-view window. */
(function(root){
 class AudioLease{
  constructor(id,lost=()=>{},options={}){this.id=id;this.lost=lost;this.now=options.now||Date.now;try{this.store=options.store||root.localStorage}catch{}this.listen=e=>{if(e.key==='city-audio-owner'&&!this.isOwner())this.lost()};root.addEventListener?.('storage',this.listen)}
  read(){try{return JSON.parse(this.store?.getItem('city-audio-owner')||'null')}catch{return null}}
  claim(){try{this.store?.setItem('city-audio-owner',JSON.stringify({id:this.id,until:this.now()+6000}))}catch{}return true}
  isOwner(){const old=this.read();return !old||old.id===this.id||old.until<=this.now()}
  owns(){const old=this.read();if(old&&old.id!==this.id&&old.until>this.now())return false;if(!old||old.id!==this.id||old.until-this.now()<3000)this.claim();return true}
  release(){if(this.read()?.id===this.id)try{this.store?.removeItem('city-audio-owner')}catch{}}
  dispose(){this.release();root.removeEventListener?.('storage',this.listen)}
 }
 class Footsteps{
  constructor(ctx){this.ctx=ctx;this.active=new Set();this.last=null;this.distance=0;this.index=0;this.status='loading';this.count=0;
   this.ready=fetch('/api/footsteps').then(r=>r.json()).then(async meta=>{if(!meta.available)throw Error('Recorded steps unavailable');const r=await fetch(meta.url);if(!r.ok)throw Error('Recorded steps unavailable');this.buffer=await ctx.decodeAudioData(await r.arrayBuffer());this.segments=meta.segments;this.status='ready'}).catch(()=>{this.status='unavailable'});
  }
  update(ex,elapsed,quiet){
   const dt=this.last===null?0:Math.max(0,Math.min(.25,elapsed-this.last));this.last=elapsed;
   const speed=ex?.walk_speed_mps||0;if(speed<.12){this.distance=0;return}
   this.distance+=speed*dt;const stride=[.48,.54,.50,.57][this.index%4];
   if(!this.buffer||this.distance<stride)return;this.distance%=stride;
   const part=this.segments[this.index%this.segments.length];this.index++;this.count++;
   const source=this.ctx.createBufferSource(),filter=this.ctx.createBiquadFilter(),gain=this.ctx.createGain(),pan=this.ctx.createStereoPanner();
   const d=Math.max(1,Math.hypot((ex.local_forward_m||0)-.9,ex.local_right_m||0));
   filter.type='lowpass';filter.frequency.value=1800;pan.pan.value=Math.max(-.65,Math.min(.65,(ex.local_right_m||0)/d));
   gain.gain.value=Math.min(.1,.18/(1+d*.5))*(quiet?.22:1);source.buffer=this.buffer;source.playbackRate.value=[.98,1.02,1.,.97][this.index%4];
   source.connect(filter).connect(pan).connect(gain).connect(this.ctx.destination);this.active.add(source);
   source.onended=()=>{this.active.delete(source);for(const n of [source,filter,pan,gain])n.disconnect()};source.start(this.ctx.currentTime,part.offset,part.duration);
  }
  stop(){for(const s of this.active)try{s.stop()}catch{}this.active.clear();this.last=null;this.distance=0}
 }
 class SceneAudio{
  constructor(){
   this.session=null;this.ctx=null;this.outside=null;this.nodes=[];this.hits=new Set();this.lastNotice=0;this.lastKnock=0;this.lastHorn=0;this.lastEnd=-1000;this.retryAt=0;this.error=null;this.elapsed=0;
   this.gate=new root.CityExteriorSound.SpeechGate();this.lease=new AudioLease(crypto.randomUUID(),()=>this.stop());
   this.arm=()=>{const C=root.AudioContext||root.webkitAudioContext;if(C&&!this.ctx){this.ctx=new C();this.steps=new Footsteps(this.ctx)}this.ctx?.resume().then(()=>{this.error=null;this.lease.claim();this.button.hidden=true}).catch(e=>{this.error=e.name;this.button.hidden=false})};
   document.addEventListener('pointerdown',this.arm);document.addEventListener('keydown',this.arm);
   this.button=document.createElement('button');this.button.id='scene-audio-enable';this.button.hidden=true;this.button.textContent='장면 소리 켜기';this.button.onclick=this.arm;this.button.style.cssText='border:1px solid #dce3ed;border-radius:8px;padding:7px 10px;background:white;color:#3e6ae1';
   (document.querySelector('.top-right')||document.querySelector('#settings-sheet')||document.body).append(this.button);
   this.channel=typeof BroadcastChannel==='function'?new BroadcastChannel('nurec-hongik-sohee'):null;if(this.channel)this.channel.onmessage=()=>this.outside?.pause();
   addEventListener('pagehide',()=>{this.stop();this.lease.dispose();this.ctx?.close();this.channel?.close()});
   root.HongikSceneAudio={enable:this.arm,getState:()=>this.diagnostics()};
  }
  stopVoice(){this.outside?.pause();this.outside?.remove();this.outside=null;for(const n of this.nodes)try{n.disconnect()}catch{}this.nodes=[];this.meter=null}
  stop(){this.stopVoice();this.steps?.stop();this.mechanical?.dispose();this.mechanical=null;for(const h of this.hits)try{h.stop()}catch{}this.hits.clear();this.lease.release()}
  voice(key,cue){
   this.stopVoice();const a=new Audio(root.HongikLocale?.audioURL(key)||'/api/narration/audio/'+key+'.wav');this.outside=a;a.id='city-exterior-audio';a.dataset.voiceKey=key;a.hidden=true;document.body.append(a);
   const ctx=this.ctx,source=ctx.createMediaElementSource(a),filter=ctx.createBiquadFilter(),pan=ctx.createStereoPanner(),gain=ctx.createGain(),meter=ctx.createAnalyser();
   filter.type='lowpass';filter.frequency.value=2600;pan.pan.value=.65;gain.gain.value=.25;meter.fftSize=256;
   this.gain=gain;this.pan=pan;this.filter=filter;this.meter=meter;this.nodes=[source,filter,pan,gain,meter];source.connect(filter).connect(pan).connect(gain).connect(meter).connect(ctx.destination);
   a.onended=()=>{if(a===this.outside)this.lastEnd=performance.now()};
   const fail=e=>{if(a!==this.outside)return;this.error=e?.name||'AudioLoadError';this.retryAt=performance.now()+1500;this.gate.retry(cue,this.elapsed);this.button.hidden=false};
   a.onerror=fail;a.play().then(()=>{if(a===this.outside){this.error=null;this.button.hidden=true}}).catch(fail);
  }
  horn(duration=.4){
   duration=Math.max(.4,Math.min(3,Number(duration)||.4));const start=this.ctx.currentTime;
   const mix=this.ctx.createGain(),filter=this.ctx.createBiquadFilter();filter.type='lowpass';filter.frequency.value=1800;
   mix.gain.setValueAtTime(0,start);mix.gain.linearRampToValueAtTime(.17,start+.035);mix.gain.setValueAtTime(.17,start+duration-.1);mix.gain.linearRampToValueAtTime(0,start+duration);
   mix.connect(filter).connect(this.ctx.destination);let active=2;
   for(const freq of [350,440]){const o=this.ctx.createOscillator();o.type='triangle';o.frequency.value=freq;o.connect(mix);this.hits.add(o);
    o.onended=()=>{this.hits.delete(o);o.disconnect();if(--active===0){mix.disconnect();filter.disconnect()}};o.start(start);o.stop(start+duration+.02)}
   this.hornPlayed=(this.hornPlayed||0)+1;
  }
  update(data){
   const s=data.nurec?.scenario;if(!s){this.stop();return}const c=s.context,ex=c?.exterior;
   if(this.session!==s.session){this.stop();this.gate.reset();this.session=s.session;this.lastNotice=0;this.lastKnock=0;this.lastHorn=s.horn_count||0;this.lastEnd=-1000;this.error=null}
   this.elapsed=s.elapsed_s;const running=data.nurec.mode==='auto'&&!s.completed;
   this.button.hidden=!running||(this.ctx?.state==='running'&&!this.error);
   if(!running||this.ctx?.state!=='running'||!this.lease.owns()){
    if(!running)this.gate.offer(ex?.voice_cue,s.elapsed_s,false);
    this.lastKnock=ex?.knock_count||0;this.lastHorn=s.horn_count||0;this.stop();return;
   }
   const speaking=document.getElementById('research-sohee-audio')?.paused===false;if(speaking)this.lastEnd=performance.now();
   if(s.horn_count>this.lastHorn)this.horn(s.horn_duration_s);this.lastHorn=s.horn_count||0;
   this.gate.offer(ex?.voice_cue,s.elapsed_s,!c?.actor_retreat);
   if(speaking||c?.actor_retreat)this.outside?.pause();
   const next=this.gate.take(s.elapsed_s,speaking||Boolean(this.outside&&!this.outside.paused&&!this.outside.ended)||performance.now()-this.lastEnd<800||performance.now()<this.retryAt);
   if(next)this.voice(next,ex?.voice_cue);
   if(this.outside&&!this.outside.paused&&ex&&this.gain){const d=Math.max(1,Math.hypot((ex.local_forward_m||0)-.9,ex.local_right_m||0));this.gain.gain.setTargetAtTime(Math.max(.16,Math.min(.68,1.6/d)),this.ctx.currentTime,.15);this.pan.pan.setTargetAtTime(Math.max(-.65,Math.min(.65,(ex.local_right_m||0)/d)),this.ctx.currentTime,.15);this.filter.frequency.setTargetAtTime(1200+1400*Math.min(1,4/d),this.ctx.currentTime,.15)}
   const count=ex?.knock_count||0;if(count>this.lastKnock&&ex.at_window){const h=root.CityExteriorSound.knock(this.ctx,speaking);this.hits.add(h);h.onended=()=>this.hits.delete(h)}this.lastKnock=count;
   const notices=s.yielding?.announcement_count||c?.announcement_count||0;if(notices>this.lastNotice){this.lastNotice=notices;this.channel?.postMessage({claim:'external-announcement'});document.getElementById('research-sohee-audio')?.pause();this.voice(s.yielding?'yield_notice':s.id==='city_carpool'?'city_taxi_warning':'city_notice')}
   if(s.id==='city_carpool')this.steps.update(ex,s.elapsed_s,speaking);else this.steps.stop();
   if(s.id==='city_rattle'&&c?.rattle_active){if(!this.mechanical)this.mechanical=new root.UnderbodySound.Player(this.ctx);this.mechanical.update(data.nurec.speed_kph,speaking)}else if(this.mechanical){this.mechanical.dispose();this.mechanical=null}
   root.passengerNarration?.setDuck?.(speaking?.16:this.outside&&!this.outside.paused?.30:c?.rattle_active?.60:1);
  }
  diagnostics(){let rms=0;if(this.meter&&this.outside&&!this.outside.paused){const a=new Float32Array(256);this.meter.getFloatTimeDomainData(a);rms=Math.sqrt(a.reduce((n,v)=>n+v*v,0)/a.length)}return {context:this.ctx?.state||'unarmed',owner:this.lease.isOwner(),voice:this.outside?.dataset.voiceKey||null,url:this.outside?.currentSrc||null,time:this.outside?.currentTime||0,paused:this.outside?.paused??true,rms,error:this.error,footsteps:this.steps?.status||'unarmed',footstepCount:this.steps?.count||0}}
 }
 const api={AudioLease,Footsteps,SceneAudio};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.HongikSceneSound=api;
})(globalThis);

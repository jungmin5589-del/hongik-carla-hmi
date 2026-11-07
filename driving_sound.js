/* Native sound design; NuRec uses a separate real interior field recording. */
(function(root){
 'use strict';
 function cabinNoise(rate=48000,seconds=6,seed=473){
  let random=seed>>>0,low=0,mid=0;const road=new Float32Array(Math.round(rate*seconds)),air=new Float32Array(road.length);
  for(let i=0;i<road.length;i++){
   random=(Math.imul(random,1664525)+1013904223)>>>0;const w=random/2147483648-1;
   low+=.012*(w-low);mid+=.12*(w-mid);road[i]=.32*w+.68*mid;air[i]=2.2*low;
  }
  // Match loop edges without a periodic impact at the buffer boundary.
  const n=Math.min(Math.round(rate*.06),Math.floor(road.length/4));
  for(const a of [road,air])for(let i=0;i<n;i++){const u=i/(n-1);a[a.length-n+i]=a[a.length-n+i]*(1-u)+a[0]*u}
  return {road,air};
 }
 function levels(speed,acceleration=0,traffic=[],speaking=false,volume=.65){
  speed=Math.max(0,Math.min(150,Number(speed)||0));const v=speed/70,duck=speaking?.28:1;
  let near=0,pan=0;
  for(const a of traffic||[]){
   if(a.kind!=='vehicle')continue;
   const d=Math.hypot(a.forward_m||0,a.right_m||0);if(d>45)continue;
   const w=Math.max(0,1-d/45);near+=w;pan+=w*Math.max(-1,Math.min(1,(a.right_m||0)/10));
  }
  const g=Math.max(0,Math.min(1,volume))*duck;
  return {road:(speed<.4?0:.018+.14*Math.pow(v,.8))*g,wind:.07*v*v*g,
   ambient:.045*g,traffic:Math.min(.075,near*.024)*g,pan:near?pan/near:0,
   motor:(speed<.4?0:.003+.008*Math.min(1,v)+.004*Math.min(1,Math.abs(acceleration)/4))*g,
   frequency:55+speed*1.8};
 }
 class Player{
  constructor(ctx){
   this.ctx=ctx;this.sources=[];this.nodes=[];this.lastSpeed=0;this.lastTime=ctx.currentTime;
   const bank=cabinNoise(ctx.sampleRate);
   const loop=(samples,type,hz)=>{
    const b=ctx.createBuffer(1,samples.length,ctx.sampleRate);b.copyToChannel(samples,0);
    const s=ctx.createBufferSource(),f=ctx.createBiquadFilter(),g=ctx.createGain();s.buffer=b;s.loop=true;f.type=type;f.frequency.value=hz;g.gain.value=0;
    s.connect(f).connect(g);s.start();this.sources.push(s);this.nodes.push(s,f,g);return g;
   };
   this.road=loop(bank.road,'lowpass',1800);this.wind=loop(bank.road,'highpass',650);this.ambient=loop(bank.air,'lowpass',750);this.traffic=loop(bank.road,'lowpass',620);
   this.pan=ctx.createStereoPanner();this.traffic.connect(this.pan).connect(ctx.destination);
   for(const n of [this.road,this.wind,this.ambient])n.connect(ctx.destination);
   this.motor=ctx.createOscillator();this.motor.type='triangle';this.motor.frequency.value=55;
   this.motorGain=ctx.createGain();this.motorGain.gain.value=0;this.motorFilter=ctx.createBiquadFilter();this.motorFilter.type='lowpass';this.motorFilter.frequency.value=360;
   this.motor.connect(this.motorFilter).connect(this.motorGain).connect(ctx.destination);this.motor.start();this.sources.push(this.motor);this.nodes.push(this.motor,this.motorGain,this.motorFilter,this.pan);
  }
  update(speed,traffic,speaking,volume){
   const now=this.ctx.currentTime,dt=Math.max(.05,now-this.lastTime),a=(speed-this.lastSpeed)/dt;this.lastSpeed=speed;this.lastTime=now;
   const p=levels(speed,a,traffic,speaking,volume);
   for(const key of ['road','wind','ambient','traffic'])this[key].gain.setTargetAtTime(p[key],now,.25);
   this.motorGain.gain.setTargetAtTime(p.motor,now,.2);this.motor.frequency.setTargetAtTime(p.frequency,now,.3);this.pan.pan.setTargetAtTime(p.pan,now,.35);
   return p;
  }
  dispose(){for(const s of this.sources){try{s.stop()}catch{}}for(const n of this.nodes){try{n.disconnect()}catch{}}this.sources=[];this.nodes=[]}
 }
 const api={cabinNoise,levels,Player};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.DrivingSound=api;
 if(typeof document==='undefined')return;
 addEventListener('DOMContentLoaded',()=>{
  let ctx=null,player=null,latest=null,enabled=true,volume=.65,recording=null,loading=false,failed=false,kind=null;const id=crypto.randomUUID();
  try{enabled=localStorage.getItem('hongik-driving-sound-enabled')!=='false';volume=Number(localStorage.getItem('hongik-driving-sound-volume')??.65)}catch{}
  volume=Number.isFinite(volume)?Math.max(0,Math.min(1,volume)):.65;
  function stop(){player?.dispose();player=null;kind=null}
  function status(text,state){const s=document.getElementById('driving-audio-status');if(s)s.textContent=text;const r=document.getElementById('driving-audio-setting');if(r)r.dataset.soundState=state}
  function owns(){
   const scene=window.HongikSceneAudio?.getState();
   if(scene){if(scene.context!=='running'||!scene.owner)return false}
   else if(document.visibilityState!=='visible')return false;
   try{const now=Date.now(),old=JSON.parse(localStorage.getItem('hongik-driving-sound-owner')||'null');if(old&&old.id!==id&&old.until>now)return false;
    localStorage.setItem('hongik-driving-sound-owner',JSON.stringify({id,until:now+1400}));return true}catch{return true}
  }
  function update(){
   const n=latest?.nurec,s=n?.scenario;
   if(!enabled||ctx?.state!=='running'||!latest?.connected||n.phase!=='live'||n.mode!=='auto'||s?.completed||!owns()){
    stop();status(!enabled?'꺼짐':ctx?.state!=='running'?'출발 버튼을 누르면 켜집니다':'정차·일시정지 중',!enabled?'disabled':ctx?.state!=='running'?'locked':'paused');return;
   }
   const recorded=latest.renderer!=='CARLA RGB'&&n.renderer_backend!=='carla';
   if(player&&kind!==recorded)stop();
   if(recorded&&!recording){
    if(!loading&&!failed){loading=true;fetch('/api/cabin-audio').then(r=>{if(!r.ok)throw new Error('recording unavailable');return r.json()}).then(r=>{if(!r.available)throw new Error('recording missing');recording=r;loading=false;update()}).catch(()=>{loading=false;failed=true;status('실제 주행 녹음 파일을 준비해 주세요','unavailable')})}
    status(failed?'실제 주행 녹음 파일을 준비해 주세요':'주행 녹음을 불러오고 있어요',failed?'unavailable':'loading');return;
   }
   if(!player){
    kind=recorded;
    player=recorded?new root.RecordedCabin.Player(ctx,recording,()=>status('주행 녹음을 재생할 수 없어요','unavailable')):new Player(ctx);
   }
   const talking=['research-sohee-audio','city-exterior-audio'].some(key=>{const a=document.getElementById(key);return a&&!a.paused&&!a.ended});
   player.update(n.speed_kph||0,latest.actors,talking,volume);
   if(player.failed){status('주행 녹음을 재생할 수 없어요','unavailable');return}
   status(talking?'설명 중 · 소리를 낮췄습니다':recorded?((n.speed_kph||0)<.4?'정차 중 · 주행음 줄임':'실제 실내 주행 녹음 재생 중'):'주행 상태에 맞춰 재생 중','playing');
  }
  function unlock(){if(!enabled)return;const C=window.AudioContext||window.webkitAudioContext;if(!ctx&&C)ctx=new C();if(document.visibilityState==='visible')try{localStorage.setItem('hongik-driving-sound-owner',JSON.stringify({id,until:Date.now()+1400}))}catch{}ctx?.resume().then(update).catch(()=>{})}
  document.addEventListener('pointerdown',unlock);document.addEventListener('keydown',unlock);
  const sheet=document.getElementById('settings-sheet');
  if(sheet){
   const row=document.createElement('div');row.className='setting';row.id='driving-audio-setting';row.innerHTML='<span>주행·환경음<small id="driving-audio-status" role="status">출발하면 재생됩니다</small></span><button id="driving-audio-toggle" type="button"></button>';
   const level=document.createElement('div');level.className='setting';level.id='driving-audio-volume-setting';level.innerHTML='<label for="driving-audio-volume">주행·환경음 크기</label><input id="driving-audio-volume" type="range" min="0" max="100" step="1">';
   sheet.append(row,level);const button=row.querySelector('button'),slider=level.querySelector('input');
   function label(){button.textContent=enabled?'켜짐':'꺼짐';button.setAttribute('aria-pressed',String(enabled));slider.value=String(Math.round(volume*100))}label();
   button.onclick=()=>{enabled=!enabled;try{localStorage.setItem('hongik-driving-sound-enabled',String(enabled))}catch{}label();if(enabled)unlock();else stop()};
   slider.oninput=()=>{volume=Number(slider.value)/100;try{localStorage.setItem('hongik-driving-sound-volume',String(volume))}catch{}update()};
  }
  const poll=setInterval(()=>{if(!window.CockpitUpdate)return;clearInterval(poll);const prior=window.CockpitUpdate;window.CockpitUpdate=data=>{prior?.(data);latest=data;update()}},100);
  document.addEventListener('visibilitychange',()=>{if(!window.HongikSceneAudio&&document.visibilityState!=='visible')stop();else update()});
  addEventListener('pagehide',()=>{clearInterval(poll);stop();ctx?.close()});addEventListener('nurec-exit',stop);
 });
})(globalThis);

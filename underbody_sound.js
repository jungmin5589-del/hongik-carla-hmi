/* Loose cover contacts: brief damped impacts, irregular clusters, speed-related. */
(function(root){
 function rng(seed){return ()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296}}
 function contactWave(rate=48000,variant=0){
  const random=rng(3401+variant*7919),a=new Float32Array(Math.round(rate*.24));
  const modes=[165+random()*50,355+random()*70,810+random()*160,1420+random()*210];
  const phases=modes.map(()=>random()*Math.PI*2);
  for(let i=0;i<a.length;i++){
   const t=i/rate,attack=Math.min(1,t/.0014),grain=random()*2-1;
   a[i]=attack*(.30*Math.sin(2*Math.PI*modes[0]*t+phases[0])*Math.exp(-t/.045)
    +.21*Math.sin(2*Math.PI*modes[1]*t+phases[1])*Math.exp(-t/.036)
    +.10*Math.sin(2*Math.PI*modes[2]*t+phases[2])*Math.exp(-t/.020)
    +.045*Math.sin(2*Math.PI*modes[3]*t+phases[3])*Math.exp(-t/.012)
    +grain*.12*Math.exp(-t/.004));
   a[i]*=Math.min(1,(a.length-i)/(rate*.025));
  }
  return a;
 }
 // Retain contactWave for decoding old recordings; live playback uses real audio below.
 const prepared=new WeakMap();
 function prepare(ctx){
  if(!prepared.has(ctx))prepared.set(ctx,fetch('/api/mechanical-audio/scrape.wav').then(r=>{if(!r.ok)throw Error('Mechanical recording unavailable');return r.arrayBuffer()}).then(b=>ctx.decodeAudioData(b)));
  return prepared.get(ctx);
 }
 function nextDelay(speed,random){return 4.5+random()*3+Math.max(0,20-Math.max(2,speed))*.05}
 class Player{
  constructor(ctx,options={}){
   this.ctx=ctx;this.random=rng(9027);this.next=0;this.active=new Set();this.dead=false;this.status='loading';
   this.gain=ctx.createGain();this.gain.gain.value=0;
   this.pan=ctx.createStereoPanner();this.pan.pan.value=.08;this.gain.connect(this.pan).connect(ctx.destination);
   this.ready=(options.buffer?Promise.resolve(options.buffer):prepare(ctx)).then(b=>{if(!this.dead){this.buffer=b;this.status='ready'}}).catch(()=>{this.status='unavailable'});
  }
  hit(at){
   const source=this.ctx.createBufferSource(),level=this.ctx.createGain();source.buffer=this.buffer;
   level.gain.value=.75+this.random()*.15;source.connect(level).connect(this.gain);this.active.add(source);
   source.onended=()=>{this.active.delete(source);if(!this.active.size&&!this.dead)this.status='ready';source.disconnect();level.disconnect()};source.start(at);this.status='playing';
   return this.buffer.duration;
  }
  update(speed,duck=false){
   if(this.dead)return;
   if(speed<2){this.stop();return}
   this.gain.gain.setTargetAtTime(duck?.25:1,this.ctx.currentTime,.2);
   if(!this.buffer)return;
   if(this.next<this.ctx.currentTime)this.next=this.ctx.currentTime+.04;
   if(this.next<this.ctx.currentTime+.14){const at=this.next;const duration=this.hit(at);this.next=at+duration+nextDelay(speed,this.random)}
  }
  stop(){for(const s of this.active){try{s.stop()}catch{}}this.active.clear();this.next=0;if(this.buffer)this.status='ready'}
  dispose(){if(this.dead)return;this.dead=true;this.stop();this.gain.disconnect();this.pan.disconnect()}
 }
 const api={contactWave,nextDelay,prepare,Player};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.UnderbodySound=api;
})(globalThis);

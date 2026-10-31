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
 function nextDelay(speed,random){return (.32+random()*.75)*Math.sqrt(18/Math.max(5,speed))}
 class Player{
  constructor(ctx){
   this.ctx=ctx;this.random=rng(9027);this.next=0;this.active=new Set();
   this.gain=ctx.createGain();this.gain.gain.value=.48;
   const filter=ctx.createBiquadFilter(),pan=ctx.createStereoPanner();filter.type='lowpass';filter.frequency.value=3200;pan.pan.value=.12;
   this.filter=filter;this.pan=pan;
   this.gain.connect(filter).connect(pan).connect(ctx.destination);
   this.buffers=Array.from({length:8},(_,i)=>{const a=contactWave(ctx.sampleRate,i),b=ctx.createBuffer(1,a.length,ctx.sampleRate);b.copyToChannel(a,0);return b});
  }
  hit(at,level){
   const source=this.ctx.createBufferSource(),gain=this.ctx.createGain();source.buffer=this.buffers[Math.floor(this.random()*this.buffers.length)];
   source.playbackRate.value=.87+this.random()*.25;gain.gain.value=level;
   source.connect(gain).connect(this.gain);this.active.add(source);
   source.onended=()=>{this.active.delete(source);source.disconnect();gain.disconnect()};source.start(at);
  }
  update(speed,duck=false){
   if(speed<2){this.stop();return}
   this.gain.gain.setTargetAtTime(duck?.09:.40+Math.min(35,speed)*.004,this.ctx.currentTime,.12);
   if(this.next<this.ctx.currentTime)this.next=this.ctx.currentTime+.025;
   if(this.next<this.ctx.currentTime+.14){
    const at=this.next;this.hit(at,.42+this.random()*.48);
    if(this.random()<.58)this.hit(at+.038+this.random()*.055,.22+this.random()*.25);
    this.next=at+nextDelay(speed,this.random);
   }
  }
  stop(){for(const source of this.active){try{source.stop()}catch{}}this.active.clear();this.next=0}
  dispose(){this.stop();this.gain.disconnect();this.filter.disconnect();this.pan.disconnect()}
 }
 const api={contactWave,nextDelay,Player};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.UnderbodySound=api;
})(globalThis);

/* Recorded interior ambience. No synthesized engine or invented traffic sounds. */
(function(root){
 'use strict';
 function gain(speed,speaking=false,volume=.65){
  const s=Math.max(0,Math.min(150,Number(speed)||0));
  const moving=Math.min(1,s/8),v=Math.max(0,Math.min(1,Number(volume)||0));
  return moving*(.55+.15*Math.min(1,s/60))*v*(speaking?.28:1);
 }
 class Player{
  constructor(ctx,asset,onerror=()=>{}){
   if(!/^\/api\/cabin-audio\/drive\.mp3$/.test(asset.url))throw new Error('Invalid cabin recording URL');
   this.ctx=ctx;this.dead=false;this.active=0;this.crossing=false;this.started=false;this.failed=false;this.onerror=onerror;
   this.master=ctx.createGain();this.master.gain.value=0;this.master.connect(ctx.destination);
   this.rows=[0,1].map(index=>{
    const audio=new Audio(asset.url);audio.preload='auto';
    if(typeof document!=='undefined'){
     audio.hidden=true;audio.id='recorded-cabin-media-'+index;
     audio.setAttribute('aria-label','실제 실내 주행 녹음');document.body.append(audio);
    }
    const source=ctx.createMediaElementSource(audio),node=ctx.createGain();node.gain.value=0;
    source.connect(node).connect(this.master);
    audio.addEventListener('error',()=>{if(!this.dead){this.failed=true;this.master.gain.value=0;onerror()}});
    return {audio,source,node};
   });
   this.timer=setInterval(()=>this.mix(),100);
  }
  play(row){
   if(this.dead)return;
   row.audio.play().catch(()=>{if(!this.dead){this.failed=true;this.master.gain.value=0;this.onerror()}});
  }
  mix(){
   if(this.dead||!this.started||this.failed)return;
   const a=this.rows[this.active],b=this.rows[1-this.active],now=this.ctx.currentTime;
   if(!this.crossing&&Number.isFinite(a.audio.duration)&&a.audio.duration-a.audio.currentTime<3){
    b.audio.currentTime=0;this.crossing=true;this.play(b);
   }
   if(this.crossing){
    const u=Math.max(0,Math.min(1,b.audio.currentTime/3));
    a.node.gain.setTargetAtTime(Math.cos(u*Math.PI/2),now,.08);
    b.node.gain.setTargetAtTime(Math.sin(u*Math.PI/2),now,.08);
    if(u>=1){a.audio.pause();a.audio.currentTime=0;this.active=1-this.active;this.crossing=false}
   }else a.node.gain.setTargetAtTime(Math.min(1,a.audio.currentTime/1.2),now,.12);
  }
  update(speed,traffic,speaking,volume){
   const value=gain(speed,speaking,volume);
   this.master.gain.setTargetAtTime(this.failed?0:value,this.ctx.currentTime,.65);
   // Keep the original recording at natural pitch/rate. Fade out at a standstill.
   if(value>0&&!this.started){this.started=true;this.play(this.rows[this.active])}
   return value;
  }
  dispose(){
   if(this.dead)return;this.dead=true;clearInterval(this.timer);
   for(const r of this.rows){r.audio.pause();r.audio.removeAttribute('src');r.audio.load();r.audio.remove?.();r.source.disconnect();r.node.disconnect()}
   this.master.disconnect();
  }
 }
 const api={gain,Player};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.RecordedCabin=api;
})(globalThis);

/* Conservative wake matching and capture; neither sends vehicle commands. */
(()=>{
function parseHongikWake(text){
 const clean=String(text).trim();
 const match=clean.match(/^(?:(?:저기|헤이|안녕)[\s,.!?]*)?(?:홍익\s*아|홍이까|홍이가|홍이카|봉위가)(?=$|[\s,.!?…]|앞|지금|현재|왜|너|목적지|얼마|천천히|빨리|살펴|설명|분석|브리핑)[\s,.!?…]*/);
 return {called:!!match,question:match?clean.slice(match[0].length).trim():clean};
}
class HongikSpeechCapture{
 constructor(rate){this.rate=rate;this.noise=.002;this.reset()}
 reset(){this.pre=[];this.chunks=[];this.speaking=false;this.quiet=0;this.duration=0;this.loudTime=0}
 push(samples){
  const ms=samples.length/this.rate*1000,rms=Math.sqrt(samples.reduce((sum,x)=>sum+x*x,0)/samples.length);
  const threshold=Math.max(.006,Math.min(.035,this.noise*3.2)),loud=rms>threshold;
  this.pre.push(samples);while(this.pre.length>1&&this.pre.reduce((sum,c)=>sum+c.length,0)>this.rate*.6)this.pre.shift();
  if(!this.speaking){
   if(!loud)this.noise=this.noise*.95+rms*.05;
   this.loudTime=loud?this.loudTime+ms:0;
   if(this.loudTime>=80){this.speaking=true;this.chunks=[...this.pre];return {phase:'listening',rms}}
   return {phase:'waiting',rms};
  }
  this.chunks.push(samples);this.duration+=ms;this.quiet=loud?0:this.quiet+ms;
  if(this.quiet<450&&this.duration<6500)return {phase:'listening',rms};
  const chunks=this.chunks;this.reset();return {phase:'complete',chunks,rms};
 }
}
globalThis.parseHongikWake=parseHongikWake;globalThis.HongikSpeechCapture=HongikSpeechCapture;
})();

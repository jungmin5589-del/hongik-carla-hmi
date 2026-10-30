/* Deterministic palm-on-car-door thud. Shared by runtime and offline QA. */
(function(root){
 function doorWave(rate=24000){
  const a=new Float32Array(Math.round(rate*.38));let seed=619;
  for(let i=0;i<a.length;i++){
   const t=i/rate;seed=(seed*1664525+1013904223)>>>0;
   const attack=Math.min(1,t/.0025),noise=seed/4294967296*2-1;
   a[i]=attack*(.6*Math.sin(2*Math.PI*92*t)*Math.exp(-t/ .085)+.27*Math.sin(2*Math.PI*187*t)*Math.exp(-t/.045)+.18*Math.sin(2*Math.PI*327*t)*Math.exp(-t/.025)+.13*noise*Math.exp(-t/.012));
   a[i]*=Math.min(1,(a.length-i)/(rate*.025));
  }
  return a;
 }
 function knock(ctx,quiet=false){
  const source=ctx.createBufferSource(),buffer=ctx.createBuffer(1,Math.round(ctx.sampleRate*.38),ctx.sampleRate);
  buffer.copyToChannel(doorWave(ctx.sampleRate),0);source.buffer=buffer;
  const panner=ctx.createStereoPanner(),filter=ctx.createBiquadFilter(),gain=ctx.createGain();
  panner.pan.value=.85;filter.type='lowpass';filter.frequency.value=1500;gain.gain.value=quiet?.045:.32;
  source.connect(filter).connect(panner).connect(gain).connect(ctx.destination);source.start();return source;
 }
 const api={doorWave,knock};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.CityExteriorSound=api;
})(globalThis);

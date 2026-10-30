const assert=require('node:assert/strict');
const {doorWave}=require('./exterior_sound.js');
for(const rate of [24000,44100,48000]){
 const a=doorWave(rate);
 assert.equal(a.length,Math.round(rate*.38));
 assert(a.every(Number.isFinite));
 assert(Math.max(...a.map(Math.abs))<1,'Door impact waveform must not clip');
 const rms=s=>Math.sqrt(s.reduce((n,x)=>n+x*x,0)/s.length);
 assert(rms(a.slice(-Math.round(rate*.025)))<.004,'No cut-off tail or sustained noise');
 assert(rms(a.slice(0,Math.round(rate*.05)))>.15,'A discernible short body-panel thud');
}
console.log('PASS finite unclipped short door impact at three audio sample rates');

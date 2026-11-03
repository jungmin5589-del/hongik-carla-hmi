const assert=require('node:assert/strict');
const {gain,Player}=require('./recorded_cabin.js');
assert.equal(gain(0),0);assert.equal(gain(-5),0);assert.equal(gain(NaN),0);
assert(gain(30)>gain(5));assert(gain(30,true)<gain(30)*.3);assert.equal(gain(30,false,0),0);
let timer,cleared=0,oscillators=0;const media=[];
global.setInterval=f=>(timer=f,1);global.clearInterval=()=>cleared++;
global.Audio=class{
 constructor(url){this.url=url;this.duration=240.88;this.currentTime=0;this.playbackRate=1;this.paused=true;this.events={};media.push(this)}
 addEventListener(k,f){this.events[k]=f}play(){this.paused=false;return Promise.resolve()}
 pause(){this.paused=true}removeAttribute(){}load(){}
};
const node=()=>({gain:{value:0,setTargetAtTime(v){this.value=v}},connect(){return this},disconnect(){this.disconnected=true}});
const ctx={currentTime:0,destination:{},createGain:node,createMediaElementSource:node,createOscillator(){oscillators++;throw Error('No synthetic sources')}};
const p=new Player(ctx,{url:'/api/cabin-audio/drive.mp3'});
assert(media.every(a=>a.paused));p.update(0,[],false,.65);assert(media.every(a=>a.paused));
p.update(30,[],false,.65);assert(!media[0].paused);assert(media[1].paused);assert(p.master.gain.value>0);
media[0].currentTime=239;timer();assert(!media[1].paused);assert(p.crossing);
media[1].currentTime=1.5;timer();assert(Math.abs(p.rows[0].node.gain.value-Math.SQRT1_2)<1e-6);
media[1].currentTime=3;timer();assert(media[0].paused);assert.equal(p.active,1);
p.update(0,[],false,.65);assert.equal(p.master.gain.value,0);assert(media.every(a=>a.playbackRate===1));assert.equal(oscillators,0);
p.dispose();p.dispose();assert.equal(cleared,1);assert(media.every(a=>a.paused));
assert.throws(()=>new Player(ctx,{url:'https://example.com/audio.mp3'}));
console.log('PASS recorded cabin: actual media only, natural pitch, stationary mute, voice ducking, equal-power long-loop overlap, cleanup');

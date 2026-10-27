const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const posted=[],players=[];
class Player{constructor(url){this.url=url;players.push(this)}play(){return Promise.resolve()}pause(){this.paused=true}removeAttribute(){}load(){}}
const context=vm.createContext({Audio:Player,AbortController,DOMException,setTimeout,clearTimeout,fetch:async(path,options)=>{const body=JSON.parse(options.body);posted.push(body);return {ok:true,json:async()=>({status:'complete',url:'/api/tts/audio/'+body.provider+'.wav'})}}});
vm.runInContext(fs.readFileSync(__dirname+'/qwen-speech.js','utf8'),context);vm.runInContext(fs.readFileSync(__dirname+'/navigation-voice.js','utf8'),context);
(async()=>{
 const voice=new context.NavigationVoice();voice.arm();voice.setProvider('supertonic');voice.enqueue({kind:'test',text:'밝은 안내',priority:3});
 await new Promise(resolve=>setTimeout(resolve,0));assert.equal(posted[0].provider,'supertonic');assert.match(players[0].url,/supertonic/);players[0].onplaying();
 voice.setProvider('qwen');assert.equal(players[0].paused,true);voice.enqueue({kind:'test',text:'Sohee 비교',priority:3});
 await new Promise(resolve=>setTimeout(resolve,0));assert.equal(posted[1].provider,'qwen');assert.match(players[1].url,/qwen/);
 players[0].onended();assert.equal(voice.current.message.text,'Sohee 비교');voice.cancel();
 voice.setProvider('supertonic');voice.setAssistantActive(true);voice.enqueue({kind:'assistant',text:'네, 말씀하세요.',priority:3});
 await new Promise(resolve=>setTimeout(resolve,0));assert.equal(posted[2].provider,'qwen','AI always uses Qwen even with F3 navigation');assert.equal(posted[2].speech_role,'assistant');assert.match(players[2].url,/qwen/);assert.equal(voice.provider,'supertonic','navigation choice stays F3');voice.cancel();
 const parts=['앞차는 저속으로 주행 중입니다.','현재 주행을 유지합니다.'];
 voice.setProvider('qwen');voice.enqueue({kind:'assistant',speechRole:'briefing',parts,text:parts.join(' '),priority:3});
 await new Promise(resolve=>setTimeout(resolve,0));assert.equal(posted[3].provider,'qwen','cached live briefing uses Qwen');assert.equal(posted[3].speech_role,'briefing');assert.deepEqual(posted[3].parts,parts);assert.equal(voice.provider,'qwen','navigation choice is unchanged');assert.match(players[3].url,/qwen/);
 players[3].onplaying();assert.equal(context.passengerTtsSpeaking,true,'briefing blocks microphone like other assistant speech');
 voice.enqueue({kind:'assistant',text:'네, 말씀하세요.',priority:3});await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(players[3].paused,true,'Qwen acknowledgement cancels briefing before taking same playback turn');assert.equal(posted[4].provider,'qwen');voice.cancel();
 console.log('PASS: actual transport requests correct bright/Sohee provider, provider changes cancel old player, stale end cannot end new speech.');
})().catch(error=>{console.error(error);process.exitCode=1});

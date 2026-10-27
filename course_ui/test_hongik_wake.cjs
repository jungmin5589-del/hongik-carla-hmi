const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context=vm.createContext({});vm.runInContext(fs.readFileSync(__dirname+'/hongik-wake.js','utf8'),context);
for(const text of ['홍익아','홍익 아.','홍이까','홍이가, 앞 차가 너무 느려','홍이카, 지금 상황','헤이 홍익아 앞 상황 알려줘','봉위가...'])assert.equal(context.parseHongikWake(text).called,true,text);
for(const text of ['오늘 홍익아라고 말했어','공익아','홍익대학교까지 안내','홍이가족','홍이가족은 왔어'])assert.equal(context.parseHongikWake(text).called,false,text);
assert.equal(context.parseHongikWake('홍익아, 앞 차가 답답해').question,'앞 차가 답답해');
for(const question of ['지금 상황 살펴봐줘','살펴봐줘','설명해줘','분석해줘','브리핑해줘']){
 assert.equal(context.parseHongikWake('홍익아'+question).question,question);
 assert.equal(context.parseHongikWake('홍익아, '+question).called,true);
}
const capture=new context.HongikSpeechCapture(48000),frame=value=>new Float32Array(2048).fill(value);
for(let i=0;i<10;i++)assert.equal(capture.push(frame(.001)).phase,'waiting');
let result;for(let i=0;i<7;i++)result=capture.push(frame(.01));assert.equal(result.phase,'listening','quiet speech below old .018 threshold is captured');
let silent=0;while(result.phase!=='complete'&&silent<20){result=capture.push(frame(.001));silent++}
assert.equal(result.phase,'complete');assert.ok(silent*2048/48000*1000>=450&&silent*2048/48000*1000<500);
assert.ok(result.chunks.length>=7+silent,'pre-roll preserves opening syllable');
capture.push(frame(.01));capture.push(frame(.01));capture.reset();assert.equal(capture.push(frame(.001)).phase,'waiting','blocked playback discards partial recordings');
console.log('PASS: conservative wake variants, false matches rejected, intact question, quiet short speech, 450ms endpoint, pre-roll and cancelled partial audio.');

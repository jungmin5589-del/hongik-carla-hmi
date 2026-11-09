const assert=require('node:assert/strict'),{AtlasLoader}=require('./map_context.js');
(async()=>{
 let complete=[],applied=[],now=0;
 const loader=new AtlasLoader(()=>new Promise((resolve,reject)=>complete.push({resolve,reject})),v=>applied.push(v),{now:()=>now});
 const old=loader.request('old-ego');await loader.request('new-ego');complete[0].resolve('old atlas');await old;
 assert.deepEqual(applied,[],'Prior scene atlas must not overwrite the new scene');assert.equal(complete.length,2);
 complete[1].reject(Error('temporary network failure'));await new Promise(resolve=>setImmediate(resolve));
 await loader.request('new-ego');assert.equal(complete.length,2,'Failed loads are throttled');
 now=1001;const retry=loader.request('new-ego');complete[2].resolve('current atlas');await retry;
 assert.deepEqual(applied,['current atlas']);await loader.request('new-ego');assert.equal(complete.length,3);
 console.log('PASS latest-scene atlas, retry after failure, and single in-flight request');
})().catch(e=>{console.error(e);process.exitCode=1});

const assert=require('node:assert/strict');
const {actorPose,drawContext,drawActors}=require('./map_context.js');
const p=actorPose({forward_m:10,right_m:2,yaw_deg:5},{x:100,y:200,yaw:90});
assert.ok(Math.abs(p.x-98)<1e-8);assert.ok(Math.abs(p.y-210)<1e-8);assert.equal(p.yaw,95);
const absolute={x:1,y:2,yaw:3};assert.equal(actorPose({world_pose:absolute},{}),absolute);
// Exercise the actual canvas draw path, including offscreen culling.
const calls=[];const ctx=new Proxy({}, {get:(_,key)=>(...args)=>calls.push([key,...args]),set:()=>true});
const at=p=>p;
drawContext(ctx,{buildings:[{points:[[10,10],[30,10],[30,30],[10,10]]}],context_roads:[]},at,1,100,100);
assert.ok(calls.some(c=>c[0]==='fill'));
calls.length=0;
drawActors(ctx,{world_pose:{x:0,y:0,yaw:0},actors:[{kind:'vehicle',world_pose:{x:20,y:30,yaw:0},length_m:12,width_m:2.5},{kind:'vehicle',world_pose:{x:1000,y:1000,yaw:0}}]},at,2,100,100);
assert.equal(calls.filter(c=>c[0]==='translate').length,1);
assert.ok(calls.some(c=>c[0]==='roundRect'&&c[4]===24));
console.log('Map coordinates, footprints, vehicle drawing and culling passed.');

/* Navigation map only. Cached OSM footprints and actual CARLA actor poses. */
(function(root){
 'use strict';
 function actorPose(actor,ego){
  if(actor.world_pose)return actor.world_pose;
  const a=ego.yaw*Math.PI/180,c=Math.cos(a),s=Math.sin(a);
  return {x:ego.x+actor.forward_m*c-actor.right_m*s,
          y:ego.y+actor.forward_m*s+actor.right_m*c,yaw:ego.yaw+actor.yaw_deg};
 }
 function path(ctx,points,at,close){ctx.beginPath();points.forEach((p,i)=>{const q=at(p);i?ctx.lineTo(...q):ctx.moveTo(...q)});if(close)ctx.closePath()}
 function drawContext(ctx,atlas,at,scale,w,h){
  const visible=points=>{const q=points.map(at);return Math.max(...q.map(p=>p[0]))>=-30&&Math.min(...q.map(p=>p[0]))<=w+30&&Math.max(...q.map(p=>p[1]))>=-30&&Math.min(...q.map(p=>p[1]))<=h+30};
  ctx.save();ctx.lineJoin='round';
  for(const road of atlas.context_roads||[]){if(!visible(road.points))continue;path(ctx,road.points,at,false);ctx.strokeStyle='#d5d8d2';ctx.lineWidth=Math.max(1,road.width*scale+1);ctx.stroke();ctx.strokeStyle='#f4f4ef';ctx.lineWidth=Math.max(1,road.width*scale);ctx.stroke()}
  for(const building of atlas.buildings||[]){if(building.points.length<4||!visible(building.points))continue;path(ctx,building.points,at,true);ctx.fillStyle='#d7dbd5';ctx.fill();ctx.strokeStyle='#b9c1b9';ctx.lineWidth=.8;ctx.stroke()}
  ctx.restore();
 }
 function drawActors(ctx,state,at,scale,w,h){
  if(!state?.world_pose)return;ctx.save();
  for(const actor of state.actors||[]){
   if(actor.kind!=='vehicle')continue;
   const pose=actorPose(actor,state.world_pose),[x,y]=at([pose.x,pose.y]);
   if(x < -30||y < -30||x>w+30||y>h+30)continue;
   const width=Math.max(5,Math.min(22,(actor.width_m||1.85)*scale));
   const length=Math.max(9,Math.min(75,(actor.length_m||4.4)*scale));
   ctx.save();ctx.translate(x,y);ctx.rotate((pose.yaw+90)*Math.PI/180);
   ctx.shadowColor='#0002';ctx.shadowBlur=3;ctx.fillStyle=actor.role==='lead'?'#667485':'#89939d';
   ctx.beginPath();ctx.roundRect(-width/2,-length/2,width,length,Math.min(3,width/3));ctx.fill();
   ctx.shadowBlur=0;ctx.fillStyle='#d8e2e8';ctx.fillRect(-width*.31,-length*.32,width*.62,Math.min(4,length*.18));
   ctx.fillStyle='#c84747';ctx.fillRect(-width*.35,length*.35,width*.25,1.5);ctx.fillRect(width*.1,length*.35,width*.25,1.5);
   ctx.restore();
  }
  ctx.restore();
 }
 const api={actorPose,drawContext,drawActors};
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.NurecMapContext=api;
})(globalThis);

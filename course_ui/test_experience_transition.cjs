const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('tesla-drive-ui/experience.js','utf8');
const VERSION='split-voice-20261013';
function harness({running=false,connected=true,startError=false}={}){
 const nodes=new Map(),requests=[],classes=new Set();let timer,offline=false;
 function element(){return {hidden:false,checked:false,disabled:false,value:'',children:[],textContent:'',classList:{toggle(){},add(){},remove(){}},setAttribute(){},replaceChildren(){this.children=[]},append(...items){this.children.push(...items)},appendChild(item){this.children.push(item)},querySelector(selector){this.parts??={};return this.parts[selector]??=element()},querySelectorAll(selector){if(selector==='button')return this.children;if(selector==='input'||selector==='input:checked'){const inputs=this.children.flatMap(x=>x.children).filter(x=>x.type==='checkbox');return selector.endsWith(':checked')?inputs.filter(x=>x.checked):inputs}return []}}}
 function get(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)}
 const radios=[element(),element()];radios[0].value='popup';radios[0].checked=true;radios[1].value='controls';
 let status={running,started:running,config:{destination:'1',situations:['timber'],ui:'popup',input_mode:'touch',yolo:false}};
 const session={session_id:'active-session',stage:'ready',telemetry:{yolo:{enabled:false,status:'idle'}},navigation:{status:'idle'}};
 const window={PASSENGER_VOICE_UI:VERSION};
 const context=vm.createContext({window,document:{getElementById:get,createElement:element,body:{classList:{add:x=>classes.add(x),remove:x=>classes.delete(x)}},addEventListener(){},querySelectorAll:()=>radios,querySelector:selector=>selector.includes(':checked')?radios.find(x=>x.checked):radios.find(x=>selector.includes(x.value))},location:{search:'?setup=1'},URLSearchParams,localStorage:{getItem:()=>null,setItem(){}},crypto:{randomUUID:()=> 'request-id'},setInterval:fn=>{timer=fn},setTimeout:fn=>fn(),fetch:async(path,options)=>{
  requests.push({path,body:options?.body?JSON.parse(options.body):null});if(offline)throw Error('network error');let data,ok=true;
  if(path==='/api/experience')data={catalog:{destinations:[{id:'1',name:'홍익대학교',detail:'캠퍼스',distance_m:350}],situations:[{id:'timber',name:'원목 적재 트럭'}]},status};
  else if(path==='/api/experience/start'){ok=!startError;status={...status,running:ok,started:ok};data=ok?status:{error:'CARLA 시작 오류'}}
  else if(path.startsWith('/api/state')){const version=new URLSearchParams(path.split('?')[1]).get('voice_ui');data=version===VERSION?{connected,session:connected?session:null}:{connected:false,reason:'음성 화면이 업데이트됐습니다. 새로고침해 주세요.'}}
  else if(path==='/api/command')data={session_id:session.session_id,command_id:'command-id'};
  else if(path.startsWith('/api/reply'))data={accepted:true,message:'YOLO 켜짐'};
  else throw Error('Unexpected request: '+path);
  return {ok,json:async()=>data};
 }});
 vm.runInContext(source,context);
 return {get,requests,classes,session,poll:()=>timer(),offline:value=>offline=value,status:()=>status,ready:async()=>{for(let i=0;i<20;i++)await Promise.resolve()},select(){get('experience-destinations').children[0].onclick()}};
}
(async()=>{
 const start=harness();await start.ready();start.select();assert.equal(start.get('experience-setup').hidden,false);
 await start.get('experience-start').onclick();assert.equal(start.get('experience-setup').hidden,false,'wait until session connects');
 await start.poll();assert.equal(start.get('experience-setup').hidden,true,'connected ready session opens driving screen');assert.equal(start.classes.has('experience-open'),false);
 assert.equal(start.requests.filter(x=>x.path==='/api/experience/start').length,1);
 start.get('experience-open').onclick();await start.poll();assert.equal(start.get('experience-setup').hidden,false,'manually opened settings stay open');
 start.get('experience-yolo').checked=true;await start.get('experience-yolo').onchange();assert.equal(start.requests.find(x=>x.path==='/api/command').body.action,'yolo_on');
 assert.equal(start.get('experience-yolo-feedback').textContent,'YOLO 켜짐');
 const waiting=harness({connected:false});await waiting.ready();waiting.select();await waiting.get('experience-start').onclick();await waiting.poll();assert.equal(waiting.get('experience-setup').hidden,false,'disconnected session never opens driving screen');
 const resume=harness({running:true});await resume.ready();await resume.poll();assert.equal(resume.get('experience-setup').hidden,true,'reattach opens existing drive without launching a second one');assert.equal(resume.requests.some(x=>x.path==='/api/experience/start'),false);
 const failure=harness({startError:true});await failure.ready();failure.select();await failure.get('experience-start').onclick();assert.equal(failure.get('experience-setup').hidden,false);assert.equal(failure.get('experience-feedback').textContent,'CARLA 시작 오류');
 const highway=harness();await highway.ready();highway.get('experience-profile').value='four_lane_loop';highway.get('experience-profile').onchange();assert.equal(highway.get('experience-start').disabled,false,'continuous highway needs no destination');assert.equal(highway.get('experience-destinations').hidden,true);await highway.get('experience-start').onclick();await highway.poll();assert.equal(highway.get('experience-setup').hidden,true);assert.equal(highway.requests.find(x=>x.path==='/api/experience/start').body.profile,'four_lane_loop');
 const preparing=harness();await preparing.ready();preparing.select();await preparing.get('experience-start').onclick();preparing.session.stage='preparing';await preparing.poll();assert.equal(preparing.get('experience-setup').hidden,false,'do not transition while roadside assets are still loading');preparing.session.stage='ready';await preparing.poll();assert.equal(preparing.get('experience-setup').hidden,true);
 const loading=harness({running:true,connected:false});await loading.ready();loading.status().stage='preparing';await loading.poll();assert.equal(loading.get('experience-start').textContent,'주행을 준비하고 있어요…');assert.match(loading.get('experience-feedback').textContent,/아직 주행이 시작되지/);
 loading.offline(true);await loading.poll();assert.equal(loading.get('experience-start').textContent,'주행 서버 연결 확인 중');assert.match(loading.get('experience-feedback').textContent,/연결되지/);
 loading.offline(false);loading.status().running=false;loading.status().summary={reason:'path_departure'};await loading.poll();assert.equal(loading.get('experience-start').disabled,false,'finished process must not leave a disabled in-progress button');
 const changed=harness({running:true});await changed.ready();changed.status().session_id='different';await changed.poll();assert.equal(changed.get('experience-setup').hidden,false,'a different session must not satisfy reconnection');
 for(const test of [start,waiting,resume,failure])for(const request of test.requests.filter(x=>x.path.startsWith('/api/state')))assert.equal(new URLSearchParams(request.path.split('?')[1]).get('voice_ui'),VERSION,'all experience state requests must pass browser version gate');
 console.log('PASS: start-to-drive transition, waiting, reconnect, manual settings, startup error and live YOLO toggle with browser state version gate (mock DOM/transport).');
})().catch(error=>{console.error(error);process.exitCode=1});

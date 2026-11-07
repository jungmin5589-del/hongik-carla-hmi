/* Add a language layer to the existing cockpit. No simulation state is changed. */
(()=>{'use strict';
 const query=new URLSearchParams(location.search),originalFetch=window.fetch.bind(window);
 let stored='ko';try{stored=localStorage.getItem('hongik-language')||'ko'}catch{}
 let lang=['ko','en'].includes(query.get('lang'))?query.get('lang'):stored==='en'?'en':'ko';
 try{if(['ko','en'].includes(query.get('lang')))localStorage.setItem('hongik-language',lang)}catch{}
 let pack={strings:{},voices:{}},pieces=[];
 const mobile=location.pathname.startsWith('/m'),hasKorean=s=>/[가-힣]/.test(s);
 function t(input){
  if(lang!=='en'||typeof input!=='string'||!hasKorean(input))return input;
  if(pack.strings[input])return pack.strings[input];
  const trimmed=input.trim();if(pack.strings[trimmed])return input.replace(trimmed,pack.strings[trimmed]);
  let m;
  if((m=input.match(/^현재 속도 ([\d.]+) km\/h(?: · 앞차 간격 약 ([\d.]+) m)?$/)))return `Speed ${m[1]} km/h`+(m[2]?` · Gap approximately ${m[2]} m`:'');
  if((m=input.match(/^감속해 앞차와 약 ([\d.]+)m 간격을 확보했어요\.$/)))return `We slowed down and established a gap of approximately ${m[1]} m.`;
  if((m=input.match(/^(.+) 요청을 실행할까요\? (.*)$/)))return `Confirm “${t(m[1])}”? ${t(m[2])}`;
  if((m=input.match(/^(.+)을 실행할까요\? (.*)$/)))return `Confirm “${t(m[1])}”? ${t(m[2])}`;
  if((m=input.match(/^(.+) 요청을 실행할까요\?$/)))return `Confirm “${t(m[1])}”?`;
  if((m=input.match(/^([\d.]+)초 뒤 실행 · 요청 취소$/)))return `${m[1]} seconds to execution · Cancel`;
  if((m=input.match(/^앞차 간격 약 ([\d.]+) m$/)))return `Gap approximately ${m[1]} m`;
  if((m=input.match(/^\s*\/\s*(\d+) 차로 · 왼쪽부터$/)))return ` / ${m[1]} lanes · from the left`;
  if((m=input.match(/^(\d+)\s*대 \/ 명$/)))return `${m[1]} vehicles / people`;
  if((m=input.match(/^(\d+)\s*분$/)))return `${m[1]} min`;
  if(/\d+곡/.test(input))return t(input.replace(/(\d+)곡/g,'$1 tracks'));
  let out=input;for(const [ko,en] of pieces)if(out.includes(ko))out=out.split(ko).join(en);
  return out;
 }
 function audioURL(key,koreanURL){
  if(lang==='en')return (mobile?'/m/english-audio/':'/api/english-audio/')+encodeURIComponent(key)+'.wav';
  return koreanURL||'/api/narration/audio/'+key+'.wav';
 }
 const ready=lang==='en'?originalFetch(mobile?'/m/language/en':'/api/language/en',{cache:'no-store',signal:AbortSignal.timeout(8000)}).then(r=>{if(!r.ok)throw Error('English pack unavailable');return r.json()}).then(p=>{pack=p;pieces=Object.entries(pack.strings).filter(([ko])=>ko.length>1).sort((a,b)=>b[0].length-a[0].length);return p}):Promise.resolve(pack);
 window.HongikLocale={get lang(){return lang},ready,t,audioURL,setLanguage(value){if(!['ko','en'].includes(value))return;try{localStorage.setItem('hongik-language',value)}catch{}const url=new URL(location.href);url.searchParams.set('lang',value);location.assign(url);}};
 function localize(value){
  if(Array.isArray(value))return value.map(localize);
  if(value&&typeof value==='object'){
   const out={};for(const [key,item] of Object.entries(value))out[key]=localize(item);
   // Only replace a prepared narration. A missing Korean URL never turns a
   // progress/result message into an unrelated arrival or scenario announcement.
   if(value.narration?.url){const key=value.narration.url.split('/').pop().replace(/\.wav$/,'');const voice=pack.voices[key];if(voice)out.narration={...voice,url:voice.cached?audioURL(key):null,language:'en'};}
   return out;
  }
  return typeof value==='string'?t(value):value;
 }
 window.fetch=async(input,init)=>{
  const url=new URL(typeof input==='string'||input instanceof URL?input:input.url,location.href);
  if(mobile&&url.origin===location.origin&&url.pathname==='/m/api/state'){url.searchParams.set('lang',lang);input=url;}
  const response=await originalFetch(input,init);if(lang!=='en')return response;
  if(url.origin!==location.origin||!/^\/(?:m\/api|api|state|control)(?:\/|$)/.test(url.pathname)||url.pathname==='/api/language/en'||!response.headers.get('content-type')?.includes('application/json'))return response;
  await ready;const translated=localize(await response.json()),headers=new Headers(response.headers);headers.delete('content-length');headers.delete('content-encoding');
  return new Response(JSON.stringify(translated),{status:response.status,statusText:response.statusText,headers});
 };
 const attributes=['aria-label','title','alt','placeholder'];
 function textNode(node){if(node.nodeType!==3||!hasKorean(node.data)||node.parentElement?.closest('script,style,code,textarea,#tracks'))return;const next=t(node.data);if(next!==node.data)node.data=next;}
 function element(node){if(node.nodeType===3){textNode(node);return}if(node.nodeType!==1)return;for(const a of attributes){const v=node.getAttribute(a);if(v&&hasKorean(v)){const next=t(v);if(next!==v)node.setAttribute(a,next)}}const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);while(walker.nextNode())textNode(walker.currentNode);for(const e of node.querySelectorAll('[aria-label],[title],[alt],[placeholder]'))for(const a of attributes){const v=e.getAttribute(a);if(v&&hasKorean(v))e.setAttribute(a,t(v));}}
 function init(){
  document.documentElement.lang=lang;
  const compact=matchMedia('(max-width:700px)');
  const target=()=>(compact.matches&&document.querySelector('#settings-sheet'))||document.querySelector('.top-right')||document.querySelector('.shell>header')||document.querySelector('main')||document.body;
  const host=target();
  const label=document.createElement('label');label.className='hongik-language-picker';label.style.cssText='display:inline-flex;align-items:center;gap:7px;font:500 12px inherit;margin:6px 10px;vertical-align:middle';
  const caption=document.createElement('span');caption.textContent='Language';const select=document.createElement('select');select.id='hongik-language';select.setAttribute('aria-label','Language');select.style.cssText='font:inherit;border:1px solid #dce3ed;border-radius:8px;background:white;color:#34435a;padding:6px 8px';select.innerHTML='<option value="ko">한국어</option><option value="en">English</option>';select.value=lang;select.onchange=()=>window.HongikLocale.setLanguage(select.value);label.append(caption,select);if(host.tagName==='MAIN')host.prepend(label);else host.append(label);
  compact.addEventListener('change',()=>{const destination=target();if(destination.tagName==='MAIN')destination.prepend(label);else destination.append(label)});
  if(lang==='en')ready.then(()=>{document.title='Hongik DRIVE · Navigation';element(document.body);new MutationObserver(records=>{for(const r of records){if(r.type==='characterData')textNode(r.target);else if(r.type==='attributes'){const v=r.target.getAttribute(r.attributeName);if(v&&hasKorean(v))r.target.setAttribute(r.attributeName,t(v));}else for(const n of r.addedNodes)element(n)}}).observe(document.body,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:attributes});}).catch(()=>{const note=document.createElement('p');note.textContent='English language pack could not load. Please reconnect or choose Korean.';host.append(note)});
 }
 if(document.readyState==='loading')addEventListener('DOMContentLoaded',init);else init();
})();

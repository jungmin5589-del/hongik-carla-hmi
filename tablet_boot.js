/* Full original cockpit on iPad; no camera/microphone permission is needed. */
(()=>{'use strict';
 window.HONGIK_TABLET=true;
 if(!crypto.randomUUID)crypto.randomUUID=()=>{
  const a=crypto.getRandomValues(new Uint8Array(16));a[6]=(a[6]&15)|64;a[8]=(a[8]&63)|128;
  const h=[...a].map(v=>v.toString(16).padStart(2,'0')).join('');return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;
 };
 const style=document.createElement('style');style.textContent=`
  #nurec-reset,#nurec-quality,#research-admin,.nurec-controls a,.navigation-settings-title,a[href="/drive"],a[href^="http://127.0.0.1:8776"]{display:none!important}
  html,body{overscroll-behavior:none}button,a,input,select{touch-action:manipulation}
  .view-tools{bottom:100px;right:18px;left:auto;z-index:4}
 `;document.head.append(style);
 const original=window.fetch.bind(window);
 window.fetch=async(input,init)=>{
  const response=await original(input,init);
  if(response.status===401&&new URL(typeof input==='string'?input:input.url,location.href).origin===location.origin)
   location.replace('/m/navigation');
  return response;
 };
})();

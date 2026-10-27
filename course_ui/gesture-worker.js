let recognizer=null;
self.onmessage=async({data})=>{
 try{
  if(data.type==='init'){
   const {FilesetResolver,GestureRecognizer}=await import('/vendor/mediapipe/vision_bundle.mjs');
   const vision=await FilesetResolver.forVisionTasks(data.base+'/wasm');
   recognizer=await GestureRecognizer.createFromOptions(vision,{baseOptions:{modelAssetPath:data.base+'/gesture_recognizer.task',delegate:'CPU'},runningMode:'VIDEO',numHands:1,minHandDetectionConfidence:.65,minHandPresenceConfidence:.65,minTrackingConfidence:.65});
   const canvas=new OffscreenCanvas(64,64);canvas.getContext('2d').fillRect(0,0,64,64);
   const blank=canvas.transferToImageBitmap();
   try{recognizer.recognizeForVideo(blank,0)}finally{blank.close()}
   self.postMessage({type:'ready'});
  }else if(data.type==='frame'&&recognizer){
   try{
    const result=recognizer.recognizeForVideo(data.bitmap,data.time);
    const gesture=result.gestures?.[0]?.[0];
    self.postMessage({type:'result',time:data.time,landmarks:result.landmarks?.[0]||[],category:gesture?.categoryName||'',score:gesture?.score||0});
   }finally{data.bitmap.close()}
  }
 }catch(error){self.postMessage({type:'error',message:error.message})}
};


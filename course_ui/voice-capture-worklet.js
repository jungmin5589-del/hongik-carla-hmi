class PassengerRecorder extends AudioWorkletProcessor {
 constructor(){super();this.count=0;this.buffer=new Float32Array(2048)}
 process(inputs){
  const audio=inputs[0]?.[0];if(!audio)return true;
  for(const value of audio){
   this.buffer[this.count++]=value;
   if(this.count===this.buffer.length){this.port.postMessage(this.buffer);this.buffer=new Float32Array(2048);this.count=0}
  }
  return true;
 }
}
registerProcessor('passenger-recorder',PassengerRecorder);


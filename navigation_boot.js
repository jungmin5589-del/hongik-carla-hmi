/* No speech provider is started by this isolated visual research trial. */
window.NavigationVoice=class {
 constructor({audio}){this.audio=audio;this.musicVolume=.45;this.duck=1}
 setProvider(){} arm(){} cancel(){} reset(){} update(){} test(){}
 setEnabled(value){window.dispatchEvent(new CustomEvent('hongik-voice-enabled',{detail:value}))}
 setMusicVolume(value){this.musicVolume=Math.max(0,Math.min(1,value));this.audio.volume=this.musicVolume*this.duck}
 setDuck(value){this.duck=Math.max(0,Math.min(1,value));this.audio.volume=this.musicVolume*this.duck}
};

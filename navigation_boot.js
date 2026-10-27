/* No speech provider is started by this isolated visual research trial. */
window.NavigationVoice=class {
 constructor({audio}){this.audio=audio;this.musicVolume=.45}
 setProvider(){} setEnabled(){} arm(){} cancel(){} reset(){} update(){} test(){}
 setMusicVolume(value){this.musicVolume=value;this.audio.volume=value}
};

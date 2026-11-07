/* Cached scene audio remains active behind the native three-view display. */
addEventListener('DOMContentLoaded',()=>{
 const sound=new HongikSceneSound.SceneAudio(),update=window.CockpitUpdate;
 window.CockpitUpdate=data=>{update?.(data);sound.update(data)};
});

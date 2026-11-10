"""Verified offline Qwen responses; no model inference during driving."""
import hashlib,json,wave
from functools import lru_cache
from pathlib import Path

CACHE=Path(__file__).resolve().parents[1]/'cache/research-voice'
ENGINE='Qwen3-TTS-12Hz-0.6B-CustomVoice'
# Each row is Korean, English, Mandarin. Completion claims are outcome-gated.
LINES={
 'choice':('선택한 대응을 확인했어요. 실행을 누르면 요청할게요.','Choice noted. Tap Execute to send the request.','已确认您的选择。点击执行后，我会发送请求。'),
 'queued':('요청을 받았어요.','Request received.','已收到您的请求。'),
 'applying':('요청한 대응을 진행하고 있어요.','We are carrying out your request.','正在按您的请求进行处理。'),
 'gap':('주변 차량과의 간격을 넓혔어요.','We have increased the space from the surrounding vehicle.','已拉大与周围车辆的距离。'),
 'left':('왼쪽 차로로 이동했어요.','We have moved into the lane on the left.','已驶入左侧车道。'),
 'stop':('차량을 정차했어요.','The vehicle has stopped.','车辆已停车。'),
 'inspect':('현재 상태를 화면에 표시했어요. 함께 확인해 주세요.','The current status is on the screen for you to review.','当前状态已显示在屏幕上，请查看。'),
 'slow':('속도를 낮춰 주행하고 있어요.','We are now driving at a lower speed.','车辆已降低速度，正在缓慢行驶。'),
 'horn':('경적을 한 번 울렸어요. 주변의 반응을 확인할게요.','We sounded the horn once. We will monitor the response.','已鸣笛一次，我们会继续观察周围的反应。'),
 'announce':('보행자에게 먼저 건너라고 알렸어요.','We have asked the pedestrian to cross first.','已示意行人先通过。'),
 'creep':('횡단 구간을 확인한 뒤 천천히 출발했어요.','We checked the crossing and proceeded slowly.','已确认过街区域，并缓慢起步。'),
 'support':('지원을 요청했어요. 실제 상담원 연결은 아직 확인되지 않았어요.','Assistance was requested. A connection to an agent has not been confirmed.','已请求支援，但尚未确认与工作人员接通。'),
 'relocate':('다른 대기 위치로 이동했어요.','We have moved to another waiting position.','已移动到另一处等候位置。'),
 'avoid':('전방 물체를 피해서 지나왔어요.','We have passed the object ahead.','已避开前方物体并通过。'),
 'maintain':('현재 차량의 대응을 유지하고 있어요.','We are maintaining the current response.','正在保持车辆当前的应对方式。'),
 'partial':('요청한 대응을 모두 마치지는 못했어요. 화면에서 현재 상태를 확인해 주세요.','Your request could only be partly fulfilled. Please review the current status.','您的请求未能全部完成，请查看屏幕上的当前状态。'),
 'unfulfilled':('요청한 대응을 완료하지 못했어요. 현재 상태를 확인해 주세요.','We could not complete the request. Please review the current status.','未能完成您的请求，请查看当前状态。'),
 'complete':('주변 확인을 마치고 차량을 정차했어요.','We have finished monitoring the surroundings and stopped.','已完成周围情况确认，车辆已停车。'),
 'cancelled':('요청을 취소했어요.','The request was cancelled.','已取消请求。')}
ACTION_KEY={'lateral':'gap','widen':'gap','merge':'left','pass':'left','end_ride':'stop',
 'safe_stop':'stop','stop':'stop','inspect':'inspect','slow':'slow','horn':'horn',
 'announce':'announce','creep':'creep','support':'support','relocate':'relocate',
 'avoid':'avoid','delegate':'avoid','maintain':'maintain'}
CHINESE={
 'blockade':'前车和右侧的大型车辆正在缓慢行驶，左侧不断有车辆快速通过。我们正在保持车距，并确认左侧是否有合适的空间。您希望如何应对？',
 'congestion':'前车正在反复起步和停车。我们正在保持车距，缓慢跟随。您希望如何应对？',
 'night':'前车在车道线附近左右摇摆。我们正在保持本车道，并观察前方车距。您希望如何应对？',
 'fog':'前方浓雾正在加重，视野受到限制。我们正在减速，并与前车保持距离。您希望如何应对？',
 'normal':'我正在查看当前行驶情况。如有变化，您可以在这里查看说明和应对方式。',
 'complete':'已到达目的地。',
 'city_yield':'人行横道旁的行人正在犹豫，并示意我们先走。车辆已停车，正在确认行人是否准备过街。您希望如何应对？',
 'city_carpool':'有人在车外喊叫，并向车门靠近。我们尚未确认此人是否是预约的同行乘客。车辆正在保持停车，观察周围情况。您希望如何应对？',
 'city_rattle':'行驶中，车外反复传来刮擦或振动的声音。原因尚未确认，我们正在检查当前行驶状态。您希望如何应对？',
 'city_cargo':'前方卡车掉落了物体，车辆正在减速。目前尚未确认物体的种类，也尚未确认能否安全通过。您希望如何应对？',
 'yield_notice':'请您先过马路，我们会等候。',
 'city_notice':'请确认您的预约信息。如需帮助，可以请求支援。',
 'city_taxi_warning':'这辆车不是出租车。',
 'city_taxi_call':'出租车！送我回家！',
 'city_taxi_refusal':'开门！把门打开！',
 'city_taxi_complaint':'怎么？你还拒载啊？',
 'city_taxi_plate':'你车牌多少？等一下，让我看看你的车牌！',
 'city_taxi_door':'喂！我看见里面有人！开门！',
 'city_taxi_answer':'听见没有？你在无视我吗？',
 'city_outside':'喂，是我叫的车吗？等一下，这边！',
 'city_outside_shout':'我看见里面有人！出来！喂！',
 'city_outside_door':'看这边！开门！等一下！'}
ALIASES={'yield':'city_yield','city_fog':'fog'}

def entries():
    result={}
    for lang,index,language,speaker in [('ko',0,'Korean','Sohee'),('en',1,'English','Sohee'),('zh',2,'Chinese','Vivian')]:
        for key,texts in LINES.items():result[lang+'_'+key]=dict(text=texts[index],language=language,speaker=speaker)
    for key,text in CHINESE.items():result['zh_scene_'+key]=dict(text=text,language='Chinese',speaker='Uncle_Fu' if key.startswith(('city_taxi_','city_outside')) and key!='city_taxi_warning' else 'Vivian')
    return result

@lru_cache(maxsize=160)
def audio_path(key):
    expected=entries().get(key)
    if expected is None:raise ValueError('Unknown response voice')
    record=json.loads((CACHE/'manifest.json').read_text('utf-8'))['entries'][key]
    if any(record.get(k)!=v for k,v in expected.items()) or record.get('engine')!=ENGINE:raise ValueError('Voice identity mismatch')
    name=record['filename']
    if Path(name).name!=name or not name.endswith('.wav'):raise ValueError('Unsafe voice filename')
    path=CACHE/name
    if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Voice checksum mismatch')
    with wave.open(str(path)) as w:
        if w.getnchannels()!=1 or w.getframerate()!=24000 or w.getnframes()<2400:raise ValueError('Invalid voice waveform')
    return path

def catalog(lang='ko'):
    result={}
    for key,entry in entries().items():
        if not key.startswith(lang+'_'):continue
        try:audio_path(key);cached=True
        except (OSError,ValueError,KeyError,wave.Error):cached=False
        result[key[len(lang)+1:]]=dict(entry,cached=cached,url='/api/research-audio/'+key+'.wav' if cached else None)
    return dict(language=lang,voices=result,actions=ACTION_KEY)

def chinese_voices():
    voices={key[len('scene_'):]:v for key,v in catalog('zh')['voices'].items() if key.startswith('scene_')}
    for alias,key in ALIASES.items():voices[alias]=voices[key]
    return voices

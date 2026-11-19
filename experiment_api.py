"""Same physical requests for text and transcribed speech; execution is explicit."""
def request(b,body):
 from experiment_protocol import intent
 with b.lock:
  sc=b.scenario;study=getattr(sc,'study',None);p=getattr(study,'protocol',None)
  if not p or not p.setting['ai_enabled']:raise ValueError('AI 요청을 사용할 수 없는 회차예요.')
  if body.get('session_id')!=sc.session:raise ValueError('이전 주행의 요청이에요. 다시 확인해 주세요.')
  if b.state.get('drive_guard') or sc.completed:raise ValueError('주행을 다시 준비해 주세요.')
  text=str(body.get('text','')).strip();source=body.get('source','text')
  if not text or len(text)>1000 or source not in ('text','voice'):raise ValueError('요청 내용을 확인해 주세요.')
  if p.setting['practice']:
   import re
   number=re.search(r'(?<!\d)(1[6-9]|2\d|30)(?!\d)',text)
   temperature=number is not None and any(x in text.lower() for x in ('온도','도','temperature','degrees','温度'))
   if not temperature:return dict(supported=False,message='연습에서는 온도를 16~30도로 조절해 보세요. 예: 온도를 22도로 해 줘.')
   degrees=int(number.group(1))
   if body.get('execute'):
    p.temperature=degrees;p.feedback=f'실내 온도를 {degrees}도로 설정했어요.'
    sc.log('experiment_practice_request',client_event=dict(input_source=source,transcript=text))
   return dict(supported=True,action='temperature',message=p.feedback if body.get('execute') else f'실내 온도를 {degrees}도로 설정할까요?')
  action=intent(text,sc.profile)
  if not body.get('execute'):
   sc.log('experiment_free_request',client_event=dict(transcript=text,input_source=source,choice='study_'+action if action else 'unsupported'))
   if action:sc.log('navigation_study_choice',client_event=dict(input_source=source,transcript=text,choice='study_'+action))
  if not action:return dict(supported=False,message='현재 구현된 대응으로 확실하게 해석하지 못했어요. 요청을 구체적으로 말하거나 문구를 선택해 주세요.')
  if not body.get('execute'):return dict(supported=True,action=action,message={'explain':'지금 상황과 차량의 대응을 설명할게요.','notify':'상황 변화를 확인해 알려드릴게요.','widen':'앞차와 간격을 넓힐게요.','merge':'안전한 틈이 생기면 왼쪽 차로로 이동할게요.','pass':'안전한 공간에서 앞차를 지나갈게요.','horn':'앞차에 경적을 한 번 울릴게요.','maintain':'현재 주행을 유지할게요.'}[action])
  if not sc.onset:raise ValueError('현재는 정상 주행 중이에요. 상황 발생 후 요청해 주세요.')
  result=study.schedule(action,sc.session,direct=True)
  sc.log('navigation_execution_confirmed',action=action,client_event=dict(input_source=source,transcript=text))
  return dict(supported=True,action=action,message=result.get('feedback','요청을 접수했어요.'))

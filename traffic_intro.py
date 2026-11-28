"""Shared ON/OFF stimulus: ordinary traffic first, then a continuous transition."""
ONSET_SECONDS=30.
INTRO_GAP=24.
NOVICE_GAP=4.
def blend(a,b,t,start=30.,end=45.):
 u=min(1.,max(0.,(t-start)/(end-start)));u=u*u*(3.-2.*u)
 return a+(b-a)*u

def lead_targets(profile,elapsed,practice=False,settled=False):
 import math
 if practice:return 30.,0.
 if profile=='congestion':
  t=max(0.,elapsed-30.);ramp=blend(0.,1.,elapsed,30.,45.)
  # A brief, visible hesitation with finite braking, never an instant stop.
  cycle=t%43.
  dip=blend(0.,1.,cycle,14.,18.)-blend(0.,1.,cycle,20.,25.)
  speed=30.+4.*math.sin(t*.28)-15.*dip
  lateral=.54*math.sin(t*.49)+.16*math.sin(t*.91)
  return 35.+ramp*(speed-35.),ramp*lateral
 amplitude=blend(.3,.5,elapsed,45.,50.)+blend(0.,.15,elapsed,60.,65.)
 ramp=blend(0.,1.,elapsed,30.,40.)
 t=max(0.,elapsed-30.);cycle=t%39.
 dip=blend(0.,1.,cycle,12.,17.)-blend(0.,1.,cycle,19.,25.)
 speed=34.+6.*math.sin(t*.23)+3.*math.sin(t*.51)-12.*dip
 return 35.+ramp*(speed-35.),ramp*(1.6+amplitude*(.2 if settled else 1.)*math.sin(t*2*math.pi/10.5))

# Two finite platoons, with irregular headways and one safe overtaking window
# per group. Positions and speeds do not change when a UI option is selected.
FAST_CYCLE=960.
FAST_REAR=220.
def fast_positions():
 return [-FAST_REAR+g*480.+v for g in range(2) for v in (0.,17.,37.,53.,76.,94.,115.,137.,156.,174.,193.,213.)]

def passing_speed(index,elapsed,profile='congestion'):
 import math
 if profile!='congestion':return 51.+(index%3)*4.+2.*math.sin(elapsed*.08+index)
 return blend(55.,88.,elapsed,30.,42.)+(index%3-1)*2.+math.sin(elapsed*.06+index)

def following_gap(profile,elapsed):
 return blend(INTRO_GAP,NOVICE_GAP if profile=='congestion' else 6.5,elapsed)

def truck_formation(relative,elapsed,lane=1):
 return relative+blend(45.,0.,elapsed)+(6. if lane==2 else 0.)

def limited_offset(current,target,dt):
 return current+max(-.5*max(0.,dt),min(.5*max(0.,dt),target-current))

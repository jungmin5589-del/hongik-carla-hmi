"""Shared ON/OFF stimulus: ordinary traffic first, then a continuous transition."""
ONSET_SECONDS=30.
INTRO_GAP=24.
def blend(a,b,t,start=30.,end=45.):
 u=min(1.,max(0.,(t-start)/(end-start)));u=u*u*(3.-2.*u)
 return a+(b-a)*u

def lead_targets(profile,elapsed,practice=False,settled=False):
 import math
 if practice:return 30.,0.
 if profile=='congestion':
  return blend(35.,30.,elapsed)-blend(0.,3.,elapsed,50.,55.)-blend(0.,2.,elapsed,65.,70.),0.
 amplitude=blend(.3,.5,elapsed,45.,50.)+blend(0.,.15,elapsed,60.,65.)
 ramp=blend(0.,1.,elapsed,30.,40.)
 return 35.,ramp*(1.6+amplitude*(.2 if settled else 1.)*math.sin((elapsed-30.)*2*math.pi/10.5))

def following_gap(profile,elapsed):
 return blend(INTRO_GAP,5.5 if profile=='congestion' else 6.5,elapsed)

def truck_formation(relative,elapsed):
 return relative+blend(45.,0.,elapsed)

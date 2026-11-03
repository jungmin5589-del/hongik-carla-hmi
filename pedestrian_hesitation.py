"""Bounded, irregular half-step intentions. Not intent detection or a release signal."""
import math

KEYS=((0.,0.),(.65,0.),(1.45,.46),(2.05,.46),(3.05,.06),(4.45,.06),
      (5.15,.38),(5.65,.18),(7.05,.18),(7.95,.54),(8.65,.54),(9.85,0.),(11.7,0.))

def hesitation_at(seconds):
    phase=max(0.,seconds)%KEYS[-1][0]
    for (a,x),(b,y) in zip(KEYS,KEYS[1:]):
        if a<=phase<=b:
            u=(phase-a)/(b-a);value=x+(y-x)*u*u*(3-2*u)
            return dict(nudge_m=value,phase='step_in' if y>x else 'step_back' if y<x else 'hesitate',
                        glance_deg=7.*math.sin(seconds*.85)*(.4 if x!=y else 1.))
    return dict(nudge_m=0.,phase='hesitate',glance_deg=0.)

def hesitation_target(anchor,curb,seconds):
    info=hesitation_at(seconds)
    # Remain on the starting side; a full crossing is a separate scenario phase.
    info['target_offset_m']=max(.85,anchor-info['nudge_m'])
    info['target_offset_m']=min(curb,info['target_offset_m'])
    return info

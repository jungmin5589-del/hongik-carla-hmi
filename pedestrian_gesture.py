"""Two-bone arm gesture in component space, preserving joint translations."""
import math

import carla
import numpy as np


def swing_between(source,target,weight=1.):
    """Shortest-arc rotation, avoiding arbitrary per-bone Euler additions."""
    a=np.asarray(source,dtype=float);b=np.asarray(target,dtype=float)
    a=a/np.linalg.norm(a);b=b/np.linalg.norm(b)
    axis=np.cross(a,b);sine=float(np.linalg.norm(axis));cosine=float(np.clip(a@b,-1.,1.))
    if sine<1e-8:
        if cosine>0:return np.eye(3)
        axis=np.cross(a,np.eye(3)[int(np.argmin(np.abs(a)))])
        axis/=np.linalg.norm(axis)
    else:axis/=sine
    angle=math.atan2(sine,cosine)*min(1.,max(0.,weight))
    x,y,z=axis;k=np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
    return np.eye(3)+math.sin(angle)*k+(1-math.cos(angle))*(k@k)


def carla_rotation(matrix):
    # CARLA's matrix has +sin(pitch) at [2,0] and -sin(roll) at [2,1].
    pitch=math.asin(float(np.clip(matrix[2,0],-1.,1.)))
    return carla.Rotation(pitch=math.degrees(pitch),
                          yaw=math.degrees(math.atan2(matrix[1,0],matrix[0,0])),
                          roll=math.degrees(math.atan2(-matrix[2,1],matrix[2,2])))


def yielding_arm(rest,elapsed,weight):
    """Gentle forward invitation, with no extra wrist/finger rotation."""
    upper=rest['crl_arm__R'];fore=rest['crl_foreArm__R'];hand=rest['crl_hand__R']
    parent=np.asarray(rest['crl_shoulder__R'].component.get_matrix())[:3,:3]
    um=np.asarray(upper.component.get_matrix());fm=np.asarray(fore.component.get_matrix())
    hm=np.asarray(hand.component.get_matrix())
    upper_vector=fm[:3,3]-um[:3,3];fore_vector=hm[:3,3]-fm[:3,3]
    smooth=weight*weight*(3.-2.*weight)
    lift=swing_between(upper_vector,[.18,.10,-.20],smooth)
    upper_rotation=lift@um[:3,:3]
    # The elbow stays moderately bent. A small forearm sweep signals "go ahead".
    direction=[.26,-.03,.10+.025*math.sin(elapsed*2.*math.pi/2.4)]
    bend=swing_between(lift@fore_vector,direction,smooth)
    fore_rotation=bend@lift@fm[:3,:3]
    return [
        ('crl_arm__R',carla.Transform(upper.relative.location,carla_rotation(parent.T@upper_rotation))),
        ('crl_foreArm__R',carla.Transform(fore.relative.location,carla_rotation(upper_rotation.T@fore_rotation)))]

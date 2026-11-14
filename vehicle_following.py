"""Small scalar controls; distances are bumper gaps and speeds are m/s."""
import math

def following_speed(speed,leader_speed,gap,desired_gap=7.,preferred=25.,reaction=.35):
    if gap<=2.5:return 0.
    gap=max(0.,gap);leader_speed=max(0.,leader_speed);speed=max(0.,speed)
    # A reaction allowance and differential braking bound supplement gap tracking.
    b=4.;room=max(0.,gap-2.5)
    safe=max(0.,-b*reaction+math.sqrt((b*reaction)**2+leader_speed**2+2*b*room))
    nominal=max(0.,leader_speed+.55*(gap-desired_gap))
    return min(max(0.,preferred),nominal,safe)

def imminent_contact(speed,leader_speed,gap):
    closing=max(0.,speed-leader_speed)
    return gap<1.5 or closing>.5 and gap/closing<1.5

def longitudinal(speed,target,previous_target,dt,emergency=False,running=True):
    if not running or emergency:return 0.,1.,0.
    # A stop uses the current measured speed, never a stale positive integral.
    target=max(0.,target)
    goal=min(target,previous_target+1.6*max(0.,dt)) if target>previous_target else target
    error=goal-speed
    if goal<.05:return 0.,min(1.,.4+speed*.25),goal
    if error<-.03:return 0.,min(1.,-error*.55),goal
    if error<=0:return 0.,0.,goal
    return min(.65,max(0.,.10+.38*error)),0.,goal


def driving_step(previous_stamp,stamp,was_running,running):
    """A paused/setup interval is not a stale moving-vehicle control interval."""
    if previous_stamp is None or not was_running or not running:return 0.
    return max(0.,stamp-previous_stamp)

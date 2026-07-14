import math
def retention(t,half_life):
    if half_life<=0: raise ValueError("Half-life must be positive")
    return 2**(-t/half_life)
def scanner_capacity(n,h,cycle,availability):
    return 0.0 if n<=0 else n*h*60/cycle*availability/100
def room_capacity(n,h,service):
    return 0.0 if n<=0 else n*h*60/service
def required_scanners(target,h,cycle,availability):
    one=scanner_capacity(1,h,cycle,availability)
    return math.ceil(target/one) if one>0 else 0
def required_rooms(target,batches,h,service):
    avg=math.ceil(target*service/(h*60))
    interval=h*60/max(1,batches)
    cohort=math.ceil(math.ceil(target/max(1,batches))*service/interval)
    return max(avg,cohort)
def max_batches(window_h,cycle_min):
    return math.floor(window_h*60/cycle_min)

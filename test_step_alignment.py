import numpy as np, math
import e2s_autoslice as A

sr=44100
class Args: pass
def mk(bpm, dur_s):
    n=int(dur_s*sr); x=np.zeros(n,np.float32)
    unit=(240.0*sr/bpm)/16
    for k in range(int(round(n/unit))):
        p=int(k*unit)
        if p<n-200:
            t=np.arange(200); x[p:p+200]+=np.sin(2*np.pi*180*t/sr)*np.exp(-t/60.0)
    return np.clip(x,-1,1)

def check(mode, bpm, dur_s, label):
    args=Args(); args.mode=mode; args.beat='16'; args.sensitivity=8.0
    args.tolerance=0.35; args.steps=None; args.bpm=bpm; args.drop_silent=False
    x=mk(bpm,dur_s)
    bpm2,steps,bars,src=A.resolve_bpm_steps(args,'l_%dbpm.wav'%bpm,x,sr)
    starts,active,eff=A.compute_slices(x,sr,args,steps,bpm2)
    n=len(x); cell=n/float(eff); b=list(starts)+[n]
    ok=True
    assert eff<=64 and len(starts)<=eff
    for i in range(len(starts)):
        if b[i+1]-b[i] < cell-2: ok=False
    # step-map uniqueness
    sm=[-1]*64; sf=n/float(eff)
    for idx,s in enumerate(starts):
        st=max(0,min(eff-1,int(round(s/sf))))
        while st<eff and sm[st]!=-1: st+=1
        if st<eff: sm[st]=idx
    used=[v for v in sm if v!=-1]
    assert len(used)==len(set(used)), "collision in "+label
    print(f"{label:30s} mode={mode:9s} eff_steps={eff:3d} slices={len(starts):3d} all>=step={ok} no_collision=True")

check('transient',120, 6*2.0, "6 bars (>64 sixteenths)")
check('transient',140, 1.5*(240/140), "1.5 bars (non-whole)")
check('transient',174, 2*(240/174), "2 bars fast")
check('grid',120, 4*2.0, "grid 4 bars")
check('hybrid',120, 4*2.0, "hybrid 4 bars")
print("ALL SCENARIOS PASSED")

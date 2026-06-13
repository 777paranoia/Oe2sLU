import numpy as np
import e2s_autoslice as A

def make_loop(bpm, bars, hits_steps):
    sr=44100; dur=bars*240.0/bpm; n=int(round(dur*sr))
    x=np.zeros(n,np.float32); unit=n/(bars*16)
    for s in hits_steps:
        p=int(s*unit); t=np.arange(300)
        if p<n-300: x[p:p+300]+=np.sin(2*np.pi*180*t/sr)*np.exp(-t/70.0)
    return np.clip(x,-1,1), sr

class Args: pass
def run(bpm,bars,hits,label):
    x,sr=make_loop(bpm,bars,hits)
    a=Args(); a.mode='transient'; a.beat='16'; a.sensitivity=8.0; a.tolerance=0.35
    a.steps=None; a.bpm=None; a.drop_silent=False  # BPM auto = length-first
    b2,steps,bars_d,src=A.resolve_bpm_steps(a,'loop.wav',x,sr)
    starts,active,eff=A.compute_slices(x,sr,a,steps,b2)
    cell=len(x)/float(eff)
    on_grid=all(abs(s/cell-round(s/cell))<0.02 for s in starts)
    bnd=list(starts)+[len(x)]
    lens=[round((bnd[i+1]-bnd[i])/cell) for i in range(len(starts))]  # slice len in steps
    print(f"{label}: detect bpm={b2:.1f}(true {bpm}) bars={bars_d}(true {bars}) src={src} steps={eff}")
    print(f"   slices={len(starts)} on_grid={on_grid} slice_lengths_in_steps={lens}")
    ratio=b2/bpm; assert any(abs(ratio-2**k)<0.02 for k in (-1,0,1)), f"BPM not octave of true: {b2} vs {bpm}"
    assert src=='length', "should detect from length"
    assert on_grid, "slice off grid"
    pass

run(120,1,[0,4,8,12],"1bar 4-on-floor")          # quarter-note hits -> 4 slices of 4 steps
run(140,2,[0,3,6,8,11,14,16,20,24,28],"2bar synco")
run(174,4,[0,8,16,24,32,40,48,56],"4bar fast halfbeats")
run(90,1,[0,2,4,6,8,10,12,14],"1bar 8th hits")
print("\nALL PIPELINE TESTS PASSED")

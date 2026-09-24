"""Cross-check parent POSIX process clock against child time.process_time."""
import ctypes,json,os,subprocess,sys,time
from pathlib import Path
def main():
    lib=ctypes.CDLL(None);lib.clock_getcpuclockid.argtypes=[ctypes.c_int,ctypes.POINTER(ctypes.c_int)];lib.clock_getcpuclockid.restype=ctypes.c_int
    code='import time\nfor i in range(1,10):\n while time.process_time()<i*.2: pass\n print(time.process_time(),flush=True)\nwhile time.process_time()<2: pass\n'
    p=subprocess.Popen([sys.executable,'-u','-c',code],stdout=subprocess.PIPE,text=True);clk=ctypes.c_int();assert lib.clock_getcpuclockid(p.pid,ctypes.byref(clk))==0;samples=[]
    for line in p.stdout:
        child=float(line);parent=time.clock_gettime(clk.value);samples.append(dict(child_reported_cpu_s=child,parent_observed_cpu_s=parent,read_lag_cpu_s=parent-child))
    assert p.wait()==0
    maximum=max(abs(r['read_lag_cpu_s']) for r in samples);assert maximum<.05
    result=dict(status='PARENT_CHILD_PROCESS_CPU_CLOCK_MATCH',samples=samples,max_abs_read_lag_cpu_s=maximum,tolerance_s=.05,comparison='parent POSIX process clock versus child process_time; sample read lag includes child CPU consumed before parent observation')
    Path('results/ablation180_v2/cpu_clock_calibration.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],maximum)
if __name__=='__main__':main()

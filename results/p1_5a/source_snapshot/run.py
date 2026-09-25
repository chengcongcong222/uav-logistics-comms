"""Sequential stage gates; never proceed after failed F13 admission."""
import os,subprocess,sys
from src.p1_5a.common import ROOT,OUT,write
def main():
    OUT.mkdir(exist_ok=True)
    stages=[
      ('readmission','P1_5A_F13_READMISSION_BLOCKED'),
      ('q4','P1_5A_Q4_BLOCKED'),('q4_check','P1_5A_Q4_BLOCKED'),
      ('submission','P1_5A_SUBMISSION_INCONSISTENT'),
      ('tests','P1_5A_SOURCE_FIREWALL_BLOCKED'),
      ('firewall freeze','P1_5A_SOURCE_FIREWALL_BLOCKED'),
      ('build_paper','P1_5A_SOURCE_FIREWALL_BLOCKED'),
      ('firewall audit','P1_5A_SOURCE_FIREWALL_BLOCKED'),
      ('seal','P1_5A_SOURCE_FIREWALL_BLOCKED')]
    for stage,failure in stages:
        cmd=[sys.executable,'-u','-m','src.p1_5a.'+stage.split()[0]]+stage.split()[1:]
        name=stage.replace(' ','_')+'.log'
        if stage=='tests':
            cmd=[sys.executable,'-m','unittest','src.p1_5a.test_source_guard','-v']
            name='source_guard_tests.log'
        if stage=='seal':
            # Seal must not hash a log file still being written.
            result=subprocess.run(cmd,cwd=ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        else:
            with (OUT/name).open('w') as f:
                result=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,
                    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        if result.returncode:
            write(OUT/'gate.json',dict(status=failure,failed_stage=stage,log=name))
            raise SystemExit(result.returncode)
        print('PASSED',stage,flush=True)
if __name__=='__main__':main()

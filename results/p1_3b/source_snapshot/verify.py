"""Independent rational replay and byte-level checks of every accepted package."""
import math,json
from fractions import Fraction
import numpy as np
from scipy.sparse import csr_matrix
from src.bench_p1_3b.common import *

def replay(matrix,cert):
    # Deliberately does not call the optimization module's certificate builder.
    z=np.load(matrix);F=lambda v:Fraction.from_float(float(v))
    a=csr_matrix((z['data'],z['indices'],z['indptr']),shape=tuple(z['shape']))
    coeff=[Fraction(0) for _ in z['lower']];value=Fraction(0);u=e=0
    for i,(lo,hi) in enumerate(zip(z['lower'],z['upper'])):
        if lo==hi:
            y=F(cert['equality_multipliers'][e]);e+=1;coeff[i]+=y;value+=y*F(lo)
        else:
            if math.isfinite(hi):
                y=F(cert['upper_multipliers'][u]);u+=1;assert y<=0;coeff[i]+=y;value+=y*F(hi)
            if math.isfinite(lo):
                y=F(cert['upper_multipliers'][u]);u+=1;assert y<=0;coeff[i]-=y;value-=y*F(lo)
    assert u==len(cert['upper_multipliers']) and e==len(cert['equality_multipliers'])
    residual=[F(v) for v in z['objective']]
    for i,y in enumerate(coeff):
        if not y:continue
        for k in range(a.indptr[i],a.indptr[i+1]):residual[a.indices[k]]-=y*F(a.data[k])
    for r,lo,hi in zip(residual,z['lb'],z['ub']):value+=r*F(lo if r>=0 else hi)
    assert value==Fraction(int(cert['numerator']),int(cert['denominator']))
    assert F(cert['lower_bound'])<=value
    return value

def main():
    certs=[]
    for p in sorted(OUT.rglob('certificate.json')):
        cert=read(p);matrix=p.parent/'model.npz';assert cert['matrix_sha256']==digest(matrix)
        value=replay(matrix,cert)
        certs.append(dict(path=str(p.relative_to(ROOT)),matrix_sha256=digest(matrix),status='INDEPENDENT_RATIONAL_REPLAY_PASSED',
            lower_bound=cert['lower_bound'],integer_ceiling=math.ceil(value)))
    packages=[]
    for p in sorted((OUT/'representatives').glob('*.json')):
        r=read(p);package=ROOT/r['package'];v=read(package/'validation.json');assert digest(package/'validation.json')==r['validation_sha256']
        for name,h in v['artifact_sha256'].items():assert digest(package/name)==h,(package,name)
        assert r['metrics']['J_late']<=1e-4
        packages.append(dict(id=r['id'],scope='Q2',status='INDEPENDENT_VALIDATION_AND_ARTIFACT_HASHES_PASSED',validation=str((package/'validation.json').relative_to(ROOT))))
    for p in sorted((OUT/'screening').rglob('validation_0.5.json')):
        v=read(p);assert v['status']=='P1_Q3_INDEPENDENTLY_VALIDATED';assert v['hard_violations']==0 and v['uncovered_sample_count']==0 and v['J_late']<=1e-4
        for name,h in v['artifact_sha256'].items():assert digest(ROOT/name)==h,(p,name)
        packages.append(dict(id=p.parent.name,scope='Q3',status='INDEPENDENT_VALIDATION_AND_ARTIFACT_HASHES_PASSED',validation=str(p.relative_to(ROOT))))
    write(OUT/'verification.json',dict(certificates=certs,packages=packages,status='PASSED'))
    print('VERIFIED',len(certs),'certificates',len(packages),'packages')

if __name__=='__main__':main()

"""Replay exact rational lower-bound certificates from exported matrices."""
import json, math
from fractions import Fraction
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from src.bench_p1.common import ROOT,write,digest
from src.bench_p1_3a.model import lp_form,rational_lagrangian_bound

OUT=ROOT/'results/p1_3a'
def main():
    records=[]
    for p in sorted((OUT/'runs').glob('*/**/lp_lower_bound_certificate.json')):
        z=np.load(p.parent/'model.npz');a=csr_matrix((z['data'],z['indices'],z['indptr']),shape=tuple(z['shape']))
        cert=json.loads(p.read_text());assert cert['matrix_sha256']==digest(p.parent/'model.npz')
        *_,u_map,e_map=lp_form(a,z['lower'],z['upper'])
        replay=rational_lagrangian_bound(z['objective'],a,z['lower'],z['upper'],z['lb'],z['ub'],u_map,e_map,cert['upper_multipliers'],cert['equality_multipliers'])
        assert replay['numerator']==cert['numerator'] and replay['denominator']==cert['denominator']
        exact=Fraction(int(cert['numerator']),int(cert['denominator']))
        assert Fraction.from_float(cert['lower_bound'])<=exact
        row=dict(certificate=str(p.relative_to(ROOT)),status='EXACT_RATIONAL_REPLAY_PASSED',lower_bound=cert['lower_bound'])
        if p.parent.name=='relay_sorties':row['integer_objective_lower_bound']=math.ceil(exact)
        records.append(row)
    write(OUT/'certificate_verification.json',dict(records=records,all_passed=bool(records)))
    print('RATIONAL_CERTIFICATES_VERIFIED',len(records))

if __name__=='__main__':main()

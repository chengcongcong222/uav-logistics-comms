import unittest, warnings
from fractions import Fraction
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import csr_matrix
from src.bench_p1_3a.model import LinearModel,AuditModel,charging_graph,union_affine,rational_lagrangian_bound
from src.common.charging import charge_time_s

def solve(m,c):
    a,lo,hi=m.arrays()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return milp(np.array(c),integrality=m.integer,bounds=Bounds(m.lb,m.ub),constraints=LinearConstraint(a,lo,hi),options=dict(threads=1,time_limit=5,mip_rel_gap=1e-9))

class ExactDomainTests(unittest.TestCase):
    def test_original_charge_graph_both_pieces(self):
        for fraction in [0.,.03,.099999,.1,.100001,.3,.8]:
            m=LinearModel();z=m.var('z',1,1);energy=m.var('E',3.2*fraction,3.2*fraction);charge=m.var('charge',0,2000)
            charging_graph(m,energy,charge,z,3.2,2000,'test')
            for direction in [-1,1]:
                c=np.zeros(len(m.names));c[charge]=direction;r=solve(m,c)
                self.assertTrue(r.success,r.message)
                self.assertAlmostEqual(r.x[charge],charge_time_s(1-fraction,2000),places=5)
    def test_inactive_charge_is_zero(self):
        m=LinearModel();z=m.var('z',0,0);energy=m.var('E',0,0);charge=m.var('charge',0,2000)
        charging_graph(m,energy,charge,z,3.2,2000,'test')
        r=solve(m,[0,0,-1,0]);self.assertTrue(r.success);self.assertEqual(r.x[charge],0)
    def test_overlap_union_is_not_all_active_span(self):
        # [x0,x0+2], [x1+5,x1+7] are disjoint in this cell.
        row,const=union_affine([(0,0,0),(0,2,1),(1,5,0),(1,7,1)])
        self.assertEqual(row,{});self.assertEqual(const,4)
        row,const=union_affine([(0,0,0),(1,1,0),(0,4,1),(1,6,1)])
        self.assertEqual(row,{1:1.,0:-1.});self.assertEqual(const,6)
    def test_conditional_m_all_trigger_patterns(self):
        for a in [0,1]:
            for b in [0,1]:
                m=LinearModel();x=m.var('x',-7,11);aa=m.var('a',a,a);bb=m.var('b',b,b)
                m.conditional({x:1},2,[(aa,1),(bb,0)])
                r=solve(m,[-1,0,0]);self.assertTrue(r.success)
                self.assertAlmostEqual(r.x[x],2 if a==1 and b==0 else 11,places=6)
    def test_free_resource_order_can_reverse_reference(self):
        m=AuditModel.__new__(AuditModel);LinearModel.__init__(m)
        m.one=m.var('one',1,1);m.T=m.var('T',0,10);m.families=[]
        a=m.var('A_start',4,7);b=m.var('B_start',0,1)
        jobs=[dict(name='A',active=m.one,start=({a:1},0),end=({a:1},3),tasks=set()),
              dict(name='B',active=m.one,start=({b:1},0),end=({b:1},3),tasks=set())]
        m.resources('ONE_MACHINE',jobs,['U1'],0)
        r=solve(m,np.zeros(len(m.names)));self.assertTrue(r.success)
        self.assertLessEqual(r.x[b]+3,r.x[a]+1e-7)
        self.assertEqual(round(r.x[m.families[0]['orders'][0][2]]),0)
    def test_exact_rational_dual_stationarity_correction(self):
        a=csr_matrix([[1.,1.]])
        for y in [-1.,-1.1,-.9,100.]:
            cert=rational_lagrangian_bound(np.array([1.,2.]),a,np.array([3.]),np.array([np.inf]),[0.,0.],[4.,4.],[(0,-1)],[],[y],[])
            exact=Fraction(int(cert['numerator']),int(cert['denominator']))
            self.assertLessEqual(exact,3)
            self.assertLessEqual(Fraction.from_float(cert['lower_bound']),exact)
        self.assertAlmostEqual(cert['lower_bound'],0.,places=8)
    def test_equality_dual_free_sign(self):
        a=csr_matrix([[1.,1.]])
        cert=rational_lagrangian_bound([1.,2.],a,[3.],[3.],[0.,0.],[4.,4.],[],[0],[],[1.])
        self.assertAlmostEqual(cert['lower_bound'],3.,places=8)

if __name__=='__main__':unittest.main()

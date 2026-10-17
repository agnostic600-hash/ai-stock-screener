import unittest
from resilience import evaluate_resilience, stress_24m

class ResilienceTests(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(evaluate_resilience({})[1:],(None,0))
        self.assertEqual(evaluate_resilience({'fcf_margin':0})[1:],(50,25))
        self.assertEqual(evaluate_resilience({'fcf_margin':float('nan')})[1:],(None,0))
    def test_weights(self):
        m=dict(fcf_margin=.2,net_debt_ebitda=0,revenue_growth=.2,operating_margin=.2,forward_pe=5,share_dilution=0,ai_capex_exposure=0)
        self.assertEqual(evaluate_resilience(m)[1:],(100,100))
        m['ai_capex_exposure']=1
        self.assertEqual(evaluate_resilience(m)[1],90)
    def test_stress(self):
        m=dict(annual_revenue=1000,annual_fcf=50,annual_gross_margin=.5,cash=120,debt_due_24m=50)
        self.assertEqual(stress_24m(m)['funding_gap'],30)
        m.pop('debt_due_24m')
        self.assertEqual(stress_24m(m)['status'],'N/A')

from django.test import TestCase
from tom_targets.tests.factories import SiderealTargetFactory
from mop.toolbox import TAP_priority
from mop.toolbox import TAP

class TestTAPPlanetPriority(TestCase):
    """
    Class describing unittests for the target planet priority functions
    """
    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.target.name = 'OGLE-2023-BLG-1060'
        self.target.ra = 270.66679
        self.target.dec = -35.70483

        self.model_params = {'t': 2460201.74,
                             't0': 2462010.0,
                             'u0': 0.007,
                             'te': 76.1,
                             'Source_magnitude' : 19.49,
                             'Blend_magnitude' : 19.09,
                             'Baseline_magnitude' : 18.52,
                             'Fit_covariance': np.array([[ 2.88968069e-02,  1.12954139e-04, -7.42284485e-01,  2.02936871e+01, -1.88429832e+01],
                                  [ 1.12954139e-04,  1.43258210e-06, -2.59171683e-03 , 7.22109915e-02, -6.72582244e-02],
                                  [-7.42284485e-01, -2.59171683e-03,  2.00291596e+01, -5.44231081e+02, 5.04835762e+02],
                                  [2.02936871e+01, 7.22109915e-02, -5.44231081e+02,  4.61093205e+04, -5.10975638e+04],
                                  [-1.88429832e+01, -6.72582244e-02,  5.04835762e+02, -5.10975638e+04, 6.61363273e+04]
                                  ]),
                             'chi2' : 276521.69,
                             'red_chi2': 787.811,
                             }
        self.params = {'Latest_data_HJD' : 2460239.91}

    def test_psi_derivatives_squared(self):

        result = TAP_priority.psi_derivatives_squared(self.model_params['t'],
                                                     self.model_params['te'],
                                                     self.model_params['u0'],
                                                     self.model_params['t0'])

        assert(type(result) == type([]))
        assert(len(result) == 3)
        for entry in result:
            assert(type(entry) == type(1.0))

    def test_TAP_planet_priority(self):
        result = TAP_priority.TAP_planet_priority(self.model_params['t'],
                                     self.model_params['t0'],
                                     self.model_params['u0'],
                                     self.model_params['te'])

        assert(type(result) == type(1.0))
        self.assertAlmostEqual(result, 64.92, places=1)
    def test_TAP_planet_priority_error(self):

        result = TAP_priority.TAP_planet_priority_error(self.model_params['t'],
                                           self.model_params['t0'],
                                           self.model_params['u0'],
                                           self.model_params['te'],
                                           self.model_params['Fit_covariance'])
        assert(type(result) == type(1.0))
        self.assertAlmostEqual(result, 8.66, places=1)

    def test_check_planet_priority(self):
        mag_now = 16.39

        planet_priority = TAP_priority.TAP_planet_priority(self.model_params['t'],
                                                           self.model_params['t0'],
                                                           self.model_params['u0'],
                                                           self.model_params['te'])
        planet_priority_error = TAP_priority.TAP_planet_priority_error(self.model_params['t'],
                                                                       self.model_params['t0'],
                                                                       self.model_params['u0'],
                                                                       self.model_params['te'],
                                                                       self.model_params['Fit_covariance'])

        result = TAP_priority.check_planet_priority(planet_priority,
                                                    planet_priority_error,
                                                    self.model_params['Baseline_magnitude'],
                                                    mag_now)

        assert (type(result) == type(True))
        self.assertEqual(result, True)

class TestTAPLongEventPriority(TestCase):
    """
    Class describing unittests for the target long event priority functions
    """

    def setUp(self):
        self.target = SiderealTargetFactory.create()
        self.target.name = 'Gaia23cnu'
        self.target.ra = 284.1060
        self.target.dec = -18.0808

        self.model_params = {'t': 2460237.0,
                             't0': 2460217.09,
                             'u0': 0.34,
                             'te': 126.4,
                             'Source_magnitude': 16.92,
                             'Blend_magnitude': 16.50,
                             'Baseline_magnitude': 15.94,
                             'Fit_covariance': np.array([[2.15139430e+02, -6.99073781e-01, 1.58171420e+02, 9.10223660e+03, -9.17011400e+03],
                                                         [-6.99073781e-01, 2.77657360e-03, -4.40726722e-01, -4.40097857e+01, 4.42423141e+01],
                                                         [1.58171420e+02, -4.40726722e-01, 1.32540884e+02, 4.79312741e+03, -4.85656397e+03],
                                                         [9.10223660e+03, -4.40097857e+01, 4.79312741e+03, 8.78518102e+05, -8.82383618e+05],
                                                         [-9.17011400e+03, 4.42423141e+01, -4.85656397e+03, -8.82383618e+05, 8.87477082e+05]]
                                                        ),
                             'chi2': 6.35,
                             'red_chi2': 6135.256,
                             }
        self.params = {'Latest_data_HJD': 2460207.09}

    def test_TAP_long_event_priority(self):
        result = TAP_priority.TAP_long_event_priority(self.model_params['t'],
                                                      self.params['Latest_data_HJD'],
                                                      self.model_params['te'])

        assert (type(result) == type(1.0))
        self.assertAlmostEqual(result, 16.84, places=1)

    def test_TAP_long_event_priority_erro(self):
        result = TAP_priority.TAP_long_event_priority_error(self.model_params['te'],
                                                           self.model_params['Fit_covariance'])
        assert (type(result) == type(1.0))
        self.assertAlmostEqual(result, 1.53, places=1)

    def test_check_long_priority(self):
        long_priority = TAP_priority.TAP_planet_priority(self.model_params['t'],
                                                         self.model_params['t0'],
                                                         self.model_params['u0'],
                                                         self.model_params['te'])
        
        t_E_error = self.model_params['Fit_covariance'][2,2]
        
        long_priority_error = TAP_priority.TAP_planet_priority_error(self.model_params['t'],
                                                                     self.model_params['t0'],
                                                                     self.model_params['u0'],
                                                                     self.model_params['te'],
                                                                     self.model_params['Fit_covariance'])

        result = TAP_priority.check_long_priority(long_priority,
                                                  long_priority_error,
                                                  self.model_params['te'],
                                                  t_E_error,
                                                  self.model_params['Baseline_magnitude'],
                                                  self.model_params['red_chi2'])

        assert (type(result) == type(True))
        self.assertEqual(result, True)
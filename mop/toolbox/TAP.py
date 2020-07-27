from django.core.management.base import BaseCommand
from tom_observations.models import ObservationRecord
from tom_targets.models import Target
from astropy import units as u
from astropy.coordinates import Angle
from astropy.time import Time
import datetime
import numpy as np
from pyLIMA import event
from pyLIMA import telescopes
from pyLIMA import microlmodels



ZP = 27.4 #pyLIMA convention

def TAP_anomaly():

    pass

def TAP_observing_mode(priority,priority_error,mag_now,mag_baseline):

   if (priority-priority_error>10) & (mag_baseline-mag_now<0.2) & (mag_now<19): #mag cut for high blended events

       return 'Priority'

   else:

       return None


def calculate_exptime_floyds(magin):
    """
    This function calculates the required exposure time
    for a given iband magnitude for the floyds spectra
    """
    exposure_time = 3600 #s

    if magin<11:
       exposure_time = 1800 #s 

    return exposure_time 


def calculate_exptime_omega_sdss_i(magin):
    """
    This function calculates the required exposure time
    for a given iband magnitude (e.g. OGLE I which also
    roughly matches SDSS i) based on a fit to the empiric
    RMS diagram of DANDIA light curves from 2016. The
    output is in seconds.
    """
    if magin < 14.7:
        mag = 14.7
    else:
        mag = magin
    lrms = 0.14075464 * mag * mag - 4.00137342 * mag + 24.17513298
    snr = 1.0 / np.exp(lrms)
    # target 4% -> snr 25

    return float(np.max((5,np.min((np.round((25. / snr)**2 * 300., 1),300))))) #no need to more 5 min exposure time, since we have different apertures, but more than 5 s at least



def event_in_the_Bulge(ra,dec):

    Bulge_limits = [[255,275],[-36,-22]]

    if (ra>Bulge_limits[0][0]) & (ra<Bulge_limits[0][1]) & (dec>Bulge_limits[1][0]) & (dec<Bulge_limits[1][1]):
        in_the_Bulge = True
    else:
        
        in_the_Bulge = False

    return in_the_Bulge

def psi_derivatives_squared(t,te,u0,t0):
    """if you prefer to have the derivatives for a simple 
       error propagation without correlation
    """
    x0 = u0**2
    x1 = te**(-2)
    x2 = (t - t0)**2
    x3 = x1*x2
    x4 = x0 + x3
    x5 = x2/te**3
    x6 = x4*x5
    x7 = x4 + 4.0
    x8 = x5*x7
    x9 = (x4*x7)**0.5
    x10 = 1/(x4*x7)
    x11 = x10/x9
    x12 = x10*x9
    x13 = 0.125/(0.5*x0 + 0.5*x3 + 0.5*x9 + 1)**2
    x14 = u0*x4
    x15 = u0*x7
    x16 = x1*(-2*t + 2*t0)
    x17 = (1/2)*x16
    x18 = x17*x4
    x19 = x17*x7

    c0 = 16.0*(x11*(x6 + x8) - x13*(-x12*(-x6 - x8) + 2*x5))**2
    c1 = 16.0*(x11*(-x14 - x15) - x13*(-2*u0 - x12*(x14 + x15)))**2
    c2 = 16.0*(x11*(-x18 - x19) - x13*(-x12*(x18 + x19) - x16))**2
    #i.e. for te, u0, to
    return [c0, c1, c2 ] 

def TAP_planet_priority_error(time_now,t0_pspl,u0_pspl,tE_pspl,covariance):
    """
    This function calculates the priority for ranking
    microlensing events based on the planet probability psi
    as defined by Dominik 2009 and estimates the cost of
    observations based on an empiric RMS estimate
    obtained from a DANDIA reduction of K2C9 Sinistro
    observations from 2016. It expects the overhead to be
    60 seconds and also return the current Paczynski
    light curve magnification.
    """

    usqr = u0_pspl**2 + ((time_now - t0_pspl) / tE_pspl)**2
    
    dpsipdu = -8*(usqr+2)/(usqr*(usqr+4)**1.5)
    dpsipdu += 4*(usqr**0.5*(usqr+4)**0.5+usqr+2)/(usqr+2+(usqr+4)**0.5)**2*1/(usqr+4)**0.5
   
  
  
     
    dUdto = -(time_now - t0_pspl) / (tE_pspl ** 2 *usqr**0.5)
    dUduo = u0_pspl/ usqr**0.5
    dUdtE = -(time_now - t0_pspl) ** 2 / (tE_pspl ** 3 * usqr**0.5)
    
    Jacob = np.zeros(len(covariance))
    Jacob[0] = dpsipdu*dUdto
    Jacob[1] = dpsipdu*dUduo
    Jacob[2] = dpsipdu*dUdtE


    error_psip = np.dot(Jacob.T,np.dot(covariance,Jacob))**0.5
 
    return error_psip #/ (calculate_exptime_omega_sdss_i(mag) + 60.)

def TAP_planet_priority(time_now,t0_pspl,u0_pspl,tE_pspl):
    """
    This function calculates the priority for ranking
    microlensing events based on the planet probability psi
    as defined by Dominik 2009 and estimates the cost of
    observations based on an empiric RMS estimate
    obtained from a DANDIA reduction of K2C9 Sinistro
    observations from 2016. It expects the overhead to be
    60 seconds and also return the current Paczynski
    light curve magnification.
    """
    usqr = u0_pspl**2 + ((time_now - t0_pspl) / tE_pspl)**2
    pspl_deno = (usqr * (usqr + 4.))**0.5
    if pspl_deno < 1e-10:
        pspl_deno = 10000.
    psip = 4.0 / (pspl_deno) - 2.0 / (usqr + 2.0 + pspl_deno)
 
    return psip




def TAP_regular_mode(in_the_Bulge,survey_cadence,sdssi_baseline,tE_fit):

    cadence =   20/tE_fit  #visits per day
    cadence = np.max(0.5,np.min(4,cadence)) # 0.5<cadence<4

    #Inside the Bulge?
    if not in_the_Bulge:
        return cadence 
    
    if survey_cadence<1:
          
       if sdssi_baseline<16.5:
       
          return cadence 

    return None


def TAP_priority_mode():

    cadence = 24 #pts/day
    duration = 3 
    return duration,cadence



def TAP_telescope_class(sdss_i_mag):

   telescope_class = '2m'

   #change telescope class limit to 18.5 to save 2 m time
   if sdss_i_mag<18.5:
      
      telescope_class = '1m'

   if sdss_i_mag<14:
      
      telescope_class = '0.4m'


   return telescope_class

def TAP_mag_now(target):

   fs = 10**((ZP-target.extra_fields['Source_magnitude'])/2.5)
   fb = 10**((ZP-target.extra_fields['Blend_magnitude'])/2.5)

   if np.isnan(fb):
      fb = 0 
   fit_parameters = [target.extra_fields['t0'],target.extra_fields['u0'],target.extra_fields['tE'],
                     target.extra_fields['piEN'],target.extra_fields['piEE'],
                     fs,
                     fb]
 
   current_event = event.Event()
   current_event.name = 'MOP_to_fit'

   current_event.ra = target.ra
   current_event.dec = target.dec

   time_now = Time(datetime.datetime.now()).jd
   fake_lightcurve = np.c_[time_now,14,0.01]
   telescope = telescopes.Telescope(name='Fake', camera_filter='I',
                                            light_curve_magnitude= fake_lightcurve,
                                            clean_the_lightcurve='No')
   current_event.telescopes.append(telescope)
   t0_par = fit_parameters[0]

   Model_parallax = microlmodels.create_model('PSPL', current_event, parallax=['Full', t0_par],blend_flux_ratio=False)
   Model_parallax.define_model_parameters()
   pyLIMA_parameters = Model_parallax.compute_pyLIMA_parameters(fit_parameters)
   ml_model, f_source, f_blending = Model_parallax.compute_the_microlensing_model(telescope, pyLIMA_parameters)
   
   mag_now = ZP-2.5*np.log10(ml_model)
   return mag_now

from django.core.management.base import BaseCommand
from tom_dataproducts.models import ReducedDatum
from tom_targets.models import Target,TargetExtra,TargetList
from astropy.time import Time, TimeDelta
from mop.toolbox import TAP
from mop.toolbox import TAP_priority
from mop.toolbox import obs_control
from mop.toolbox import omegaII_strategy
from mop.toolbox import interferometry_prediction
import datetime
import json
import numpy as np
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):

    help = 'Sort events that need extra observations'

    def add_arguments(self, parser):

        parser.add_argument('target_name', help='name of the event to fit')
        parser.add_argument('observe', help='whether or not to observe (live_obs or none)')

    def handle(self, *args, **options):
        verbose = False

        logger.info("runTAP: Started with options "+repr(options))

        ### Create or load TAP list
        try:

            tap_list = TargetList.objects.filter(name='OMEGAII')[0]

        except:

            tap_list = TargetList(name='OMEGAII')
            tap_list.save()

        if options['target_name'] == 'all':
            list_of_events_alive = Target.objects.filter(targetextra__in=TargetExtra.objects.filter(key='Alive', value=True))
            logger.info('runTAP: Loaded all '+str(len(list_of_events_alive))+' events')

        else:
            target, created = Target.objects.get_or_create(name= options['target_name'])
            list_of_events_alive = [target]
            logger.info('runTAP: Loaded event ' + target.name)
        
        KMTNet_fields = TAP.load_KMTNet_fields()

        for event in list_of_events_alive[:]:
            logger.info('runTAP: analyzing event '+event.name)

            if 'Microlensing' not in event.extra_fields['Classification']:
               pass

            else:
                #try:

                # Gather the necessary information from the model fit to this event.  Sanity check: if this information
                # isn't available, skip the event
                try:
                    time_now = Time(datetime.datetime.now()).jd
                    t0_pspl = event.extra_fields['t0']
                    u0_pspl = event.extra_fields['u0']
                    tE_pspl = event.extra_fields['tE']
                    t0_pspl_error = event.extra_fields['t0_error']
                    tE_pspl_error = event.extra_fields['tE_error']

                    covariance = load_covar_matrix(event.extra_fields['Fit_covariance'])

                    sane = TAP.sanity_check_model_parameters(t0_pspl, t0_pspl_error, u0_pspl,
                                                             tE_pspl, tE_pspl_error, covariance)

                except KeyError:
                    logger.warning('runTAP: Insufficent model parameters available for ' + event.name + ', skipping')
                    sane = False

                if sane:
                    # Categorize the event based on event timescale
                    category = TAP.categorize_event_timescale(event)

                    # Calculate the priority of this event for different science goals
                    planet_priority = TAP_priority.TAP_planet_priority(time_now,t0_pspl,u0_pspl,tE_pspl)
                    planet_priority_error = TAP_priority.TAP_planet_priority_error(time_now,t0_pspl,u0_pspl,tE_pspl,covariance)
                    logger.info('runTAP: Planet priority: ' + str(planet_priority) + ', ' + str(planet_priority_error))

                    # ACTION RAS: Need to calculate this if not already available.
                    # If not available, assume a default 30d period to encourage observations
                    if 'Latest_data_HJD' in event.extra_fields.keys():
                        t_last = event.extra_fields['Latest_data_HJD']
                    else:
                        t_last = Time.now(jd) - TimeDelta(days=30.0)
                    logger.info('runTAP: Last datapoint: ' + str(t_last))

                    long_priority = TAP_priority.TAP_long_event_priority(time_now, t_last, tE_pspl)
                    long_priority_error = TAP_priority.TAP_long_event_priority_error(tE_pspl, covariance)
                    logger.info('runTAP: Long tE priority: ' + str(long_priority) + ' ' + str(long_priority_error))

                    # Storing both types of priority as extra_params and also as ReducedDatums so
                    # that we can track the evolution of the priority as a function of time
                    extras = {'TAP_priority':np.around(planet_priority,5),
                              'TAP_priority_longtE': np.around(long_priority, 5)}
                    event.save(extras = extras)

                    data = {'tap_planet': planet_priority,
                            'tap_planet_error': planet_priority_error,
                            'tap_long': long_priority,
                            'tap_long_error': long_priority_error
                            }

                    rd, created = ReducedDatum.objects.get_or_create(
                              timestamp=datetime.datetime.utcnow(),
                              value=data,
                              source_name='MOP',
                              source_location=event.name,
                              data_type='TAP_priority',
                              target=event)
                    if created:
                        rd.save()

                    rd, created = ReducedDatum.objects.get_or_create(
                        timestamp=datetime.datetime.utcnow(),
                        value=data,
                        source_name='MOP',
                        source_location=event.name,
                        data_type='TAP_priority_longtE',
                        target=event)
                    if created:
                        rd.save()

                    # Gather the information required to make a strategy decision
                    # for this target:

                    # Exclude events that are within the High Cadence Zone
                    # event_in_the_Bulge = TAP.event_in_the_Bulge(event.ra, event.dec)
                    event_not_in_OMEGA_II = TAP.event_not_in_OMEGA_II(event.ra, event.dec, KMTNet_fields)
                    if event_not_in_OMEGA_II:
                        sky_location = 'In HCZ'
                    else:
                        sky_location = 'Outside HCZ'
                    logger.info('runTAP: Event NOT in OMEGA: ' + str(event_not_in_OMEGA_II))
                    logger.info('runTAP: Event alive? ' + repr(event.extra_fields['Alive']))

                    # If the event is in the HCZ, set the MOP flag to not observe it
                    if (event_not_in_OMEGA_II):# (event_in_the_Bulge or)  & (event.extra_fields['Baseline_magnitude']>17):

                        extras = {'Observing_mode':'No', 'Sky_location': sky_location}
                        event.save(extras = extras)
                        logger.info('runTAP: Event not in OMEGA-II')

                    # If the event is flagged as not alive, then it is over, and should also not be observed
                    elif not event.extra_fields['Alive']:
                        extras = {'Observing_mode': 'No', 'Sky_location': sky_location}
                        event.save(extras=extras)
                        logger.info('runTAP: Event not Alive')

                    # For Alive events outside the HCZ, the strategy depends on whether it is classified as a
                    # stellar/planetary event, or a long-timescale black hole candidate
                    else:
                        logger.info('runTAP: Event should be observed')
                        # Check target for visibility
                        visible = obs_control.check_visibility(event, Time.now().decimalyear, verbose=False)
                        logger.info('runTAP: Event visible?  ' + repr(visible))

                        if visible:
                            mag_now = TAP.TAP_mag_now(event)
                            logger.info('runTAP: Mag now = ' + str(mag_now))
                            if mag_now:
                                mag_baseline = event.extra_fields['Baseline_magnitude']
                                logger.info('runTAP: mag_baseline: ' + str(mag_baseline))
                                observing_mode = TAP.TAP_observing_mode(planet_priority, planet_priority_error,
                                                                    long_priority, long_priority_error,
                                                                    tE_pspl, tE_pspl_error, mag_now, mag_baseline)

                            else:
                                observing_mode = None
                            logger.info('runTAP: Observing mode: ' + event.name + ' ' + str(observing_mode))
                            extras = {'Observing_mode': observing_mode, 'Sky_location': sky_location}
                            event.save(extras=extras)

                            if observing_mode in ['priority_stellar_event', 'priority_long_event', 'regular_long_event']:
                                tap_list.targets.add(event)

                                # Get the observational configurations for the event, based on the OMEGA-II strategy:
                                obs_configs = omegaII_strategy.determine_obs_config(event, observing_mode,
                                                                                    mag_now, time_now, t0_pspl, tE_pspl)
                                logger.info('runTAP: Determined observation configurations: ' + repr(obs_configs))

                                # Filter this list of hypothetical observations, removing any for which a similar
                                # request has already been submitted and has status 'PENDING'
                                obs_configs = obs_control.filter_duplicated_observations(obs_configs)
                                logger.info('runTAP: Filtered out duplicates: ' + repr(obs_configs))

                                # Build the corresponding observation requests in LCO format:
                                obs_requests = obs_control.build_lco_imaging_request(obs_configs)
                                logger.info('runTAP: Build observation requests: ' + repr(obs_requests))

                                # Submit the set of observation requests:
                                if 'live_obs' in options['observe']:
                                    obs_control.submit_lco_obs_request(obs_requests, event)
                                    logger.info('runTAP: SUBMITTING OBSERVATIONS')
                                else:
                                    logger.warning('runTAP: WARNING: OBSERVATIONS SWITCHED OFF')

                        else:
                            logger.info('runTAP: Target ' + event.name + ' not currently visible')
                            observing_mode = None
                            extras = {'Observing_mode': observing_mode, 'Sky_location': sky_location}
                            event.save(extras=extras)

                    ### Spectroscopy
                    observe_spectro = False
                    if observe_spectro:
                        if (event.extra_fields['Spectras']<1) & (event.extra_fields['Observing_mode'] != 'No'):
                            obs_control.build_and_submit_regular_spectro(event)
                            logger.info('runTAP: Submitted spectroscopic observations for ' + event.name)

                    ### Inteferometry
                    interferometry_prediction.evaluate_target_for_interferometry(event)
                    logger.info('runTAP: Evaluated ' + event.name + ' for interferometry')

                #except:
                #    logger.warning('runTAP: Cannot perform TAP for target ' + event.name)


def load_covar_matrix(raw_covar_data):

    payload = str(raw_covar_data).replace('[[','').replace(']]','').replace('\n','').lstrip()
    array_list = payload.split('] [')

    data = []
    for entry in array_list:
        data.append([float(x) for x in entry.split()])

    return np.array(data)


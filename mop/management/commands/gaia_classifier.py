from django.core.management.base import BaseCommand
from django.db import transaction
from tom_dataproducts.models import ReducedDatum
from astropy.time import Time
from mop.toolbox import querytools, fittools
import numpy as np
from mop.toolbox import classifier_tools

import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):

    help = 'Identify microlensing events from Gaia alerts'

    def handle(self, *args, **options):
        with transaction.atomic():
            classifier = 1

            logger.info('Gaia classifier started run - version check')

            # Retrieve a set of MicrolensingEvent objects of active Gaia Targets:
            target_data = querytools.get_gaia_alive_events()
            nalive = str(len(target_data))
            logger.info('Found '+ nalive + ' alive Gaia targets')

            if classifier == 1:
                # Evaluate each selected Target:
                for k, (event, mulens) in enumerate(target_data.items()):
                    logger.info('Classifier evaluating ' + mulens.name + ', ' + str(k) + ' out of ' + nalive)

                    # The expectation is that the lightcurve data for them will have a model
                    # fit by a separate process, which will have stored the resulting model
                    # parameters in the EXTRA_PARAMs for each Target.  Targets with no
                    # fit parameters are ignored until they are model fitted.
                    # Fitted targets will have their class set to microlensing by default

                    if mulens.extras['u0'].value != 0.0 \
                        and mulens.extras['t0'].value != 0.0 \
                        and mulens.extras['tE'].value != 0.0 \
                        and event.ra != None and event.dec != None:

                        # Test for an invalid blend magnitude:
                        valid_blend_mag = classifier_tools.check_valid_blend(float(mulens.extras['Blend_magnitude'].value))

                        # Test for a suspiciously large u0:
                        valid_u0 = classifier_tools.check_valid_u0(float(mulens.extras['u0'].value))

                        # Test for low-amplitude change in photometry:
                        valid_dmag = classifier_tools.check_valid_dmag(mulens)

                        # Test for suspicious reduced chi squared value
                        valid_chisq = classifier_tools.check_valid_chi2sq(mulens)

                        # If a target fails all three criteria, set its classification
                        # to 'Unclassified variable'.  Note that TAP will consider scheduling
                        # observations for any object with 'microlensing' in the
                        # classification
                        if not valid_blend_mag or not valid_u0 or not valid_dmag:
                            update_extras={
                                'Classification': 'Unclassified variable',
                                'Category': 'Unclassified'
                            }
                            mulens.store_parameter_set(update_extras)
                            logger.info(mulens.name+': Reset as unclassified variable')

                        if 'red_chi2' in event.extra_fields.keys():
                            if not valid_chisq:
                                update_extras={
                                    'Classification': 'Unclassified poor fit',
                                    'Category': 'Unclassified'
                                }
                                mulens.store_parameter_set(update_extras)
                                logger.info(event.name+': Reset as unclassified poor fit')

            elif classifier == 2:
                for event, mulens in target_data.items():
                    update_extras = {
                        'Classification': 'Unclassified Gaia target',
                        'Category': 'Unclassified'
                    }
                    mulens.store_parameter_set(update_extras)
                    logger.info(mulens.name+': Reset as unclassified Gaia target')


def retrieve_target_photometry(target):
    """Function to retrieve all available photometry for a target, combining
    all datasets.  Based on code by E. Bachelet."""

    datasets = ReducedDatum.objects.filter(target=target)

    phot = []
    time = []
    for data in datasets:
        if data.data_type == 'photometry':
            if 'magnitude' in data.value.keys():
                try:
                    phot.append([float(data.value['magnitude']),
                    float(data.value['error'])])
                    time.append(Time(data.timestamp).jd)
                except:
                    # Weights == 1
                    phot.append([float(data.value['magnitude']),
                    1])
                    time.append(Time(data.timestamp).jd)

    photometry = np.c_[time,phot]

    return photometry

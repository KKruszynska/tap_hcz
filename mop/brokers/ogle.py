from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import MultipleObjectsReturned
from tom_alerts.alerts import GenericBroker, GenericQueryForm
from django import forms
from django.db.utils import IntegrityError
from tom_targets.models import Target
from tom_observations import facility
from tom_dataproducts.models import ReducedDatum

from astropy.coordinates import SkyCoord
import astropy.units as unit
import os
import numpy as np
import requests
from astropy.time import Time, TimezoneInfo
import logging

logger = logging.getLogger(__name__)

BROKER_URL = 'https://www.astrouw.edu.pl/ogle/ogle4/ews'

class OGLEQueryForm(GenericQueryForm):
    target_name = forms.CharField(required=False)
    cone = forms.CharField(
        required=False,
        label='Cone Search',
        help_text='RA,Dec,radius in degrees'
    )

    def clean(self):
        if len(self.cleaned_data['target_name']) == 0 and \
                        len(self.cleaned_data['cone']) == 0:
            raise forms.ValidationError(
                "Please enter either a target name or cone search parameters"
                )

class OGLEBroker(GenericBroker):
    name = 'OGLE'
    form = OGLEQueryForm

    def fetch_alerts(self, years = [], events='all'):
        """Fetch data on microlensing events discovered by OGLE"""

        # Read the lists of events for the given years
        ogle_events = self.fetch_lens_model_parameters(years)

        # Apply selection of events, if any
        if str(events).lower() != 'all':
            event_selection = {}
            event_selection[events] = ogle_events[events]
        else:
            event_selection = ogle_events

        #ingest the TOM db
        list_of_targets = self.ingest_events(event_selection)

        return list_of_targets

    def fetch_lens_model_parameters(self, years):
        """Method to retrieve the text file of the model parameters for fits by the OGLE survey"""
        logger.info('OGLE harvester: Fetching event model parameters for years '+repr(years))

        events = {}
        for year in years:
            par_file_url = os.path.join(BROKER_URL,year,'lenses.par')
            response = requests.request('GET', par_file_url)
            logger.info('OGLE harvester: retrieving parameters for events from '
                            +str(year)+' with status '+str(response.status_code))
            if response.status_code == 200:
                for line in response.iter_lines():
                    line = str(line)
                    if 'StarNo' not in line and len(line) > 5:      # Skip the file header
                        entries = line.split()
                        name = 'OGLE-'+entries[0].replace("b'","")
                        ra = entries[3]
                        dec = entries[4]
                        events[name] = (ra,dec)

        logger.info('OGLE harvester: found ' + str(len(events)) + ' event(s)')

        return events

    def ingest_events(self, ogle_events):
        """Function to ingest the targets into the TOM database"""
        logger.info('OGLE harvester: ingesting events')

        list_of_targets = []

        for event_name, event_params in ogle_events.items():

            qs = Target.object.filter(name=event_name)

            if len(qs) == 0:
                s = SkyCoord(event_params[0], event_params[1], unit=(unit.hourangle, unit.deg), frame='icrs')
                target, created = Target.objects.get_or_create(name=event_name, ra=s.ra.deg, dec=s.dec.deg,
                                                           type='SIDEREAL', epoch=2000)
                if created:
                    target.save()
                    logger.info('OGLE harvester: added event '+event_name+' to MOP')
            else:
                logger.info('OGLE harvester: found ' + str(qs.count()) + ' targets with name ' + event_name)
                target = qs[0]
                
            #except IntegrityError:
            #    logger.warning('OGLE harvester IntegrityError: event ' + event_name + ' already known to MOP')

            list_of_targets.append(target)

        logger.info('OGLE harvester: completed ingest of events')

        return list_of_targets

    def find_and_ingest_photometry(self, targets):
        current_year = str(int(Time.now().byear))
        logger.info('OGLE harvester: ingesting photometry')

        for target in targets:
            year = target.name.split('-')[1]
            event = target.name.split('-')[2]+'-'+target.name.split('-')[3]

            latest_data = ReducedDatum.objects.filter(target=target, source_name='OGLE').order_by('-timestamp')
            if len(latest_data) > 0:
                time_latest_data = Time(latest_data[0].timestamp, format='datetime')
            else:
                time_latest_data = Time('2023-01-01T00:00:00.0', format='isot')

            # Only harvest the photometry for the current year's events, since
            # it will not otherwise be updating.  Also check to see if the latest
            # datapoint is more recent than those data already ingested, to minimize
            # runtime.
            if year == current_year:
                photometry = self.read_ogle_lightcurve(target)
                if photometry[-1][0] > time_latest_data.jd:
                    status = self.ingest_ogle_photometry(target, photometry)
                    logger.info('OGLE harvester: read and ingested photometry for event '+target.name)
                else:
                    logger.info('OGLE harvester: most recent photometry for event '
                                +target.name+' ('+str(photometry[-1][0])+') already ingested')

        logger.info('OGLE harvester: Completed ingest of photometry')

    def read_ogle_lightcurve(self, target):
        """Method to read the OGLE lightcurve via HTTP"""

        year = target.name.split('-')[1]
        event = target.name.split('-')[2] + '-' + target.name.split('-')[3]

        lc_file_url = os.path.join(BROKER_URL, year, event.lower(), 'phot.dat')

        photometry = []

        response = requests.request('GET', lc_file_url)
        if response.status_code == 200:
            for line in response.iter_lines():
                entries = str(line).replace('\n','').replace("b'",'').replace("'",'').split()
                photometry.append( [float(x) for x in entries] )

        return np.array(photometry)

    def ingest_ogle_photometry(self, target, photometry):
        """Method to store the photometry datapoints in the TOM as ReducedDatums"""

        for i in range(0,len(photometry),1):
            jd = Time(photometry[i][0], format='jd', scale='utc')
            jd.to_datetime(timezone=TimezoneInfo())
            datum = {'magnitude': photometry[i][1],
                    'filter': 'OGLE_I',
                    'error': photometry[i][2]
                    }
            try:
                rd, created = ReducedDatum.objects.get_or_create(
                    timestamp=jd.to_datetime(timezone=TimezoneInfo()),
                    value=datum,
                    source_name='OGLE',
                    source_location=target.name,
                    data_type='photometry',
                    target=target)

                if created:
                    rd.save()
            except MultipleObjectsReturned:
                logger.error('OGLE HARVESTER: Found duplicated data for event '+target.name)

        return 'OK'

    def sort_target_list(self, list_of_targets):
        name_list = np.array([x.name for x in list_of_targets])
        order = np.argsort(name_list)
        order = order[::-1]
        return (np.array(list_of_targets)[order]).tolist()

    def select_random_targets(self, list_of_targets, ntargets=100):

        target_index = np.random.randint(0,len(list_of_targets)-1, size=ntargets)

        # Numpy's random routines don't provide a sample with no unique entries,
        # so filter for that and fill in the gaps.
        target_index = np.unique(target_index)

        max_iter = 10
        i = 0
        while(len(target_index) < ntargets) and (i <= max_iter):
            i += 1
            idx = np.random.randint(0,len(list_of_targets), size=1)[0]
            if idx not in target_index:
                target_index = np.append(target_index, idx)

        return np.array(list_of_targets)[target_index]

    def to_generic_alert(self, alert):
        pass
  

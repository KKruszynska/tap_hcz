from django.core.management.base import BaseCommand
from tom_observations.models import ObservationRecord
from datetime import datetime
import pytz

class Command(BaseCommand):

    help = "Command to back-fill the scheduled start and end times of observation groups"

    def handle(self, *args, **options):

        tz = pytz.timezone('utc')

        obs_list = ObservationRecord.objects.all()

        for obs_record in obs_list:
            if not obs_record.scheduled_start or not obs_record.scheduled_end:
                tstart = None
                tend = None
                if 'requests' in obs_record.parameters:
                    # Handle current (2023) format of JSON parameter field
                    if 'windows' in obs_record.parameters['requests'][0].keys():
                        tstart = obs_record.parameters['requests'][0]['windows'][0]['start']
                        tend = obs_record.parameters['requests'][0]['windows'][0]['start']
                        for req in obs_record.parameters['requests']:
                            for window in req['windows']:
                                if window['start'] < tstart:
                                    tstart = window['start']
                                if window['end'] > tend:
                                    tend = window['end']

                # Handle older format of parameter dictionary
                else:
                    if 'start' in obs_record.parameters and 'end' in obs_record.parameters:
                        tstart = self.convert_to_datetime(obs_record.parameters['start'])
                        tend = self.convert_to_datetime(obs_record.parameters['end'])

                if tstart and tend:
                    tstart = tstart.replace(tzinfo=tz)
                    tend = tend.replace(tzinfo=tz)
                    obs_record.scheduled_start = tstart
                    obs_record.scheduled_end = tend
                    obs_record.save()

            else:
                print(obs_record.target, obs_record.scheduled_start, obs_record.scheduled_end)

    def convert_to_datetime(self, date_string):
        """Convert dates and times from strings to datetime objects, when they may be in different string formats"""

        try:
            t = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S.%f')
        except ValueError:
            t = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S')
        except:
            raise IOError('Unsupported format of date string: ' + date_string)

        return t
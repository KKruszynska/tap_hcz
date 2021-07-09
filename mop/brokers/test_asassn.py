from mytom.samplecode import ASASSNBroker
import unittest
import requests
from unittest import mock
from unittest.mock import Mock
from django.test import TestCase, override_settings, tag
from unittest.mock import patch
import lxml.html as lh
from tom_targets.models import Target
from tom_alerts.alerts import GenericBroker, GenericQueryForm
from tom_dataproducts.models import ReducedDatum

BROKER_URL = 'http://www.astronomy.ohio-state.edu/asassn/transients.html'
broker = ASASSNBroker('ASAS-SN broker')
fakedata = [['id',['','']],['other',['AT2021kdo (= Gaia21bxn)',
'AT20210du(=Gaia21cqi)']],['ATEL',['','']],['RA',['1:6:42.74','8:8:36.48']],
['Dec',['61:59:40.9','-40:53:23.5']],['Discovery',['2021-06-9.44','2021-06-12.74']],
['V/g',['13.98','15.46']],['SDSS',['','']],['DSS',['','']],['Vizier',['','']],
['Spectroscopic Class',['','']],
['comments',['known microlensing event or Be-type outburst, discovered 2021/04/16.801','known candidate Be-star or microlensing event, discovered 2021/06/01.188']]]


class TestActivity(unittest.TestCase):
    def SetUp(self,broker):
        self.broker = ASASSNBroker('ASAS-SN Broker')
        broker = ASASSNBroker('ASAS-SN broker')
        
        #harvestasassn = HarvestAsassn()
        
    #tests that the link to the transient table functions
    def test_open_webpage(self):
        page_response = broker.open_webpage()
        self.assertEqual(200, page_response)

    #tests that harvest_asassn can read rows and there is at least 1 row in the table
    def test_retrieve_transient_table(self):
        col = broker.retrieve_transient_table()
        self.assertFalse(len(col[0][1])==0)
        self.assertFalse(len(col[1][1])==0)
        self.assertFalse(len(col[2][1])==0)
        self.assertFalse(len(col[3][1])==0)
        self.assertFalse(len(col[4][1])==0)
        self.assertFalse(len(col[5][1])==0)
        self.assertFalse(len(col[6][1])==0)
        self.assertFalse(len(col[7][1])==0)
        self.assertFalse(len(col[8][1])==0)
        self.assertFalse(len(col[9][1])==0)
        self.assertFalse(len(col[10][1])==0)
        self.assertFalse(len(col[11][1])==0)
    
 
    #need to mock and use fake data to test that it finds the microlensing candidates
    
    def test_retrieve_microlensing_coordinates(self):
        with mock.patch('mytom.samplecode.ASASSNBroker.retrieve_transient_table',return_value=fakedata):
            #should equal 1
            actual_result = broker.retrieve_microlensing_coordinates()
            assert (len(actual_result) == 2)

    def test_fetch_alerts(self):
        targetlist=broker.fetch_alerts()
        targettype = type(targetlistå[0])
        self.assertTrue(targettype == Target)
    
    def test_find_and_ingest_photometry(self):
        targets = broker.fetch_alerts()
        #for target in targets:
        lightcurvelinks=broker.find_and_ingest_photometry()
        self.assertEqual(lightcurvelinks[0],'https://asas-sn.osu.edu/photometry/d2295747-d586-5d1b-8e86-b6d7addf94cc')

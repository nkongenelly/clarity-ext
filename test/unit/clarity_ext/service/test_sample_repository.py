import unittest
from clarity_ext.inversion_of_control.ioc import ioc
from clarity_ext.repository.sample_repository import SampleRepository
from clarity_ext.service.application import ApplicationService
from genologics.entities import Container, Artifact, Sample
from genologics.lims import Lims


class TestSampleRepository(unittest.TestCase):
    def test_fetch_sample_not_initialized__assert_exception_thrown(self):
        lims = Lims('', '', '')
        session = FakeSession(lims)
        sample_repo = SampleRepository(session)
        sample_resource = Sample(lims, uri='someting')
        self.assertRaises(
            AssertionError, lambda: sample_repo.get_samples([sample_resource])
        )


class FakeSession(object):
    def __init__(self, lims):
        self.api = lims
        ioc.set_application(ApplicationService(self))

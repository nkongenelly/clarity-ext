import unittest
from clarity_ext.context import ExtensionContext
from clarity_ext.domain import Container, Sample
import uuid


class TestBatchCreate(unittest.TestCase):
    def test_can_create_container_with_samples(self):
        context = ExtensionContext.create(None)
        svc = context.clarity_service
        project = svc.get_project_by_name("Test-0001")
        print((project.name))
        container = Container(name=str(uuid.uuid4()),
                              container_type=Container.CONTAINER_TYPE_96_WELLS_PLATE)

        for ix in range(50):
            sample = Sample(sample_id=None, name=str(uuid.uuid4()), project=project)
            container.append(sample)

        svc.create_container(container, with_samples=True)

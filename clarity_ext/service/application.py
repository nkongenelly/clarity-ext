from clarity_ext.repository.sample_repository import SampleRepository
from clarity_ext.repository.container_repository import ContainerRepository


class ApplicationService(object):
    """
    Sets up instances of all required repositories in the system.
    """

    def __init__(self, session):
        self.sample_repository = SampleRepository(session)
        self.container_repository = ContainerRepository()

from mock import MagicMock
from StringIO import StringIO
from io import BytesIO
from mock import create_autospec
from clarity_ext.service.file_service import Csv
from clarity_ext.service.file_service import FileService
from clarity_ext.service.file_service import OSService
from clarity_ext.service.process_service import ProcessService
from clarity_ext.context import ExtensionContext
from clarity_ext.service.artifact_service import ArtifactService
from clarity_ext.domain.process import Process
from clarity_ext.domain.user import User
from clarity_ext.domain.udf import UdfMapping
from clarity_ext.utility.testing_parse_scripts.fake_artifact_factory import FakeArtifactFactory


class ContextBuilder:
    """
    Add entities to repositories held by context
    E.g. shared files, artifacts, analytes.
    """
    def __init__(self):
        self.step_repo = FakeStepRepo()
        self.logger = FakeLogger()
        self.context = None
        self._create()

    def with_analyte_pair(self, input, output):
        self.step_repo.add_analyte_pair(input, output)

    def with_mocked_local_shared_file(self, filename, contents):
        monkey = LocalSharedFilePatcher()
        monkey.cache[filename] = contents
        self.context.local_shared_file = monkey.local_shared_file

    def _create(self):
        session = None
        clarity_service = None
        file_repository = None
        current_user = None
        validation_service = None
        dilution_service = None
        os_service = OSService()
        process_service = ProcessService()
        artifact_service = ArtifactService(self.step_repo)
        file_service = FileService(
            artifact_service, file_repository, False,
            os_service, uploaded_to_stdout=False, disable_commits=True)
        self.context = ExtensionContext(session, artifact_service, file_service, current_user,
                                self.logger, self.step_repo, clarity_service,
                                dilution_service, process_service, validation_service,
                                test_mode=False, disable_commits=True)


class PairBuilder(object):
    def __init__(self):
        self.artifact_repo = FakeArtifactFactory()
        self.output_udf_dict = dict()
        self.target_id = None
        self.target_type = None
        self.pair = None

    def create(self):
        pair = self.artifact_repo.create_pair(
            pos_from=None, pos_to=None, source_id=None, target_id=self.target_id,
            target_type=self.target_type)
        pair.output_artifact.udf_map = UdfMapping(self.output_udf_dict)
        self.pair = pair

    def with_target_id(self, target_id):
        self.target_id = target_id

    def with_output_udf(self, lims_udf_name, value):
        self.output_udf_dict[lims_udf_name] = value

    def with_target_type(self, type):
        self.target_type = type


class FakeStepRepo:
    def __init__(self):
        self._shared_files = list()
        self._analytes = list()
        self.user = User("Integration", "Tester", "no-reply@medsci.uu.se", "IT")

    def all_artifacts(self):
        return self._shared_files + self._analytes

    def add_analyte_pair(self, input, output):
        self._analytes.append((input, output))

    def get_process(self):
        return Process(None, "24-1234", self.user, dict(), "http://not-avail")


class LocalSharedFilePatcher:
    """
    Replace methods in Context
    """
    def __init__(self):
        self.cache = dict()
        os_service = MagicMock()
        self.file_service = FileService(None, None, False, os_service)

    def local_shared_file(self, name, mode="r", is_xml=False, is_csv=False, file_name_contains=None):
        if is_csv:
            content = self.cache[name]
            stream = StringIO(content)
            return Csv(stream)
        else:
            content = self.cache[name]
            bs = BytesIO(b'{}'.format(content.encode('utf-8')))
            return self.file_service.parse_xml(bs)


class FakeLogger:
    def __init__(self):
        self.warnings = list()

    def warning(self, text):
        self.warnings.append(text)

    def log(self, text):
        pass

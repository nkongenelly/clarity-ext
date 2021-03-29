from mock import MagicMock
from io import StringIO
from io import BytesIO
from mock import create_autospec
from clarity_ext.service.file_service import Csv
from clarity_ext.service.file_service import FileService
from clarity_ext.service.file_service import OSService
from clarity_ext.service.process_service import ProcessService
from clarity_ext.service.validation_service import ValidationService
from clarity_ext.service.step_logger_service import StepLoggerService
from clarity_ext.context import ExtensionContext
from clarity_ext.service.artifact_service import ArtifactService
from clarity_ext.domain.process import Process
from clarity_ext.domain.user import User
from clarity_ext.domain.udf import UdfMapping
from clarity_ext.domain.shared_result_file import SharedResultFile
from clarity_ext.utility.testing_parse_scripts.fake_artifact_factory import FakeArtifactFactory


class ContextBuilder:
    """
    Handle repositories held by context
    E.g. shared files, artifacts, analytes.
    """
    def __init__(self, fake_step_repo_builder=None):
        # Insert fake_step_repo_builder if there are step udfs
        self.fake_step_repo_builder = fake_step_repo_builder or FakeStepRepoBuilder()
        self.fake_step_repo_builder.create()
        self.step_repo = self.fake_step_repo_builder.fake_step_repo
        self.logger = FakeLogger()
        self.file_repository = FakeFileRepository()
        self.os_service = FakeOsService()
        self.artifact_service = FakeArtifactService()
        self.file_service = FakeFileService()
        step_logger_service = StepLoggerService('Step log', self.file_service)
        self.validation_service = ValidationService(step_logger_service)
        self.context = None
        self.id_counter = 1
        self._create()

    def with_analyte_pair(self, input, output):
        self.step_repo.add_analyte_pair(input, output)

    def with_shared_result_file(self, file_handle, file_name):
        artifact = SharedResultFile(name=file_handle)
        self.step_repo.add_shared_result_file(artifact)
        self.file_repository.add_file(self.id_counter, file_name)
        existing_file = self.file_repository.file_by_id[self.id_counter]
        artifact.files.append(existing_file)
        self.id_counter += 1
        return artifact

    def with_mocked_local_shared_file(self, filename, contents):
        monkey = LocalSharedFilePatcher()
        monkey.cache[filename] = contents
        self.context.local_shared_file = monkey.local_shared_file

    def _create(self):
        session = None
        clarity_service = None
        current_user = None
        dilution_service = None
        process_service = ProcessService()
        artifact_service = ArtifactService(self.step_repo)
        self.context = ExtensionContext(session, artifact_service, self.file_service, current_user,
                                self.logger, self.step_repo, clarity_service,
                                dilution_service, process_service, self.validation_service,
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
        self.process = Process(None, "24-1234", self.user, dict(), "http://not-avail")

    def all_artifacts(self):
        return self._shared_files + self._analytes

    def add_analyte_pair(self, input, output):
        self._analytes.append((input, output))

    def get_process(self):
        return self.process

    def add_shared_result_file(self, f):
        self._shared_files.append((None, f))


class FakeStepRepoBuilder:
    def __init__(self):
        self.fake_step_repo = None
        self.process_udf_dict = dict()

    def with_process_udf(self, lims_udf_name, udf_value):
        self.process_udf_dict[lims_udf_name] = udf_value
        if self.fake_step_repo is not None and self.fake_step_repo.process is not None:
            udf_map = UdfMapping(self.process_udf_dict)
            self.fake_step_repo.process.udf_map = udf_map

    def create(self):
        self.fake_step_repo = FakeStepRepo()
        udf_map = UdfMapping(self.process_udf_dict)
        self.fake_step_repo.process = Process(None, "24-1234",
                                              self.fake_step_repo.user,
                                              udf_map,
                                              "http://not-avail")


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
        self.errors = list()

    def warning(self, text):
        self.warnings.append(text)

    def error(self, text):
        self.errors.append(text)

    def log(self, text):
        pass


class FakeFileRepository:
    def __init__(self):
        self.file_by_id = dict()

    def add_file(self, id, filename):
        file = FakeFile(id=id, filename=filename)
        self.file_by_id[id] = file


class FakeFile:
    """
    Represent a genologics File object
    """
    def __init__(self, id, filename=None):
        self.id = id
        self.original_location = filename
        self.api_resource = None
        self.uri = r'www.something/{}'.format(filename)


class FakeOsService(object):
    def exists(self, path):
        return True

    def rmtree(self, path):
        pass

    def makedirs(self, path):
        pass


class FakeArtifactService(object):
    def shared_files(self):
        return list()


class FakeFileService(object):
    def local_shared_file_search_or_create(self, file_name, extension, mode, modify_attached, filename):
        pass

from types import SimpleNamespace

from clarity_ext.domain import Sample
from mock import MagicMock
from io import StringIO
from io import BytesIO
from clarity_ext.service.file_service import Csv
from clarity_ext.service.file_service import FileService
from clarity_ext.service.process_service import ProcessService
from clarity_ext.service.validation_service import ValidationService
from clarity_ext.service.step_logger_service import StepLoggerService
from clarity_ext.context import ExtensionContext
from clarity_ext.service.artifact_service import ArtifactService
from clarity_ext.domain.process import Process
from clarity_ext.domain.user import User
from clarity_ext.domain.udf import UdfMapping
from clarity_ext.domain.aliquot import Aliquot
from clarity_ext.domain.container import Container
from clarity_ext.domain.shared_result_file import SharedResultFile
from clarity_ext.utility.build_fake_environment.fake_artifact_factory import FakeArtifactFactory


class ContextBuilder:
    """
    Handle repositories held by context
    E.g. shared files, artifacts, analytes.
    """
    def __init__(self, fake_step_repo_builder=None, current_user=None):
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
        self.current_user = current_user
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
        dilution_service = None
        process_service = ProcessService()
        artifact_service = ArtifactService(self.step_repo)
        self.context = ExtensionContext(
            session, artifact_service, self.file_service, self.current_user,
            self.logger, self.step_repo, clarity_service,
            dilution_service, process_service, self.validation_service,
            test_mode=False, disable_commits=True)


class PairBuilder(object):
    def __init__(self, base_builder=None):
        self.artifact_repo = \
            base_builder.artifact_repo if base_builder else FakeArtifactFactory()
        self.output_udf_dict = base_builder.output_udf_dict.copy() if base_builder else dict()
        self.input_udf_dict = base_builder.input_udf_dict.copy() if base_builder else dict()
        self.target_id = base_builder.target_id if base_builder else None
        self.target_type = base_builder.target_type if base_builder else None
        self.qc_flag = base_builder.qc_flag if base_builder else Aliquot.QC_FLAG_UNKNOWN
        self.name = base_builder.name if base_builder else None
        self.samples = base_builder.samples.copy() if base_builder else list()
        self.input_container = base_builder.input_container if base_builder else None
        self.output_container = base_builder.output_container if base_builder else None
        self.pair = None

    def create(self):
        pair = self.artifact_repo.create_pair(
            pos_from=None, pos_to=None, source_id=None, target_id=self.target_id,
            target_type=self.target_type)
        pair.output_artifact.udf_map = UdfMapping(self.output_udf_dict)
        pair.output_artifact.qc_flag = self.qc_flag
        pair.output_artifact.name = self.name
        pair.input_artifact.name = self.name
        pair.input_artifact.udf_map = UdfMapping(self.input_udf_dict)
        if self.input_container is not None:
            # get well position from original initiation in fake artifact repo
            well_pos = pair.input_artifact.well.position
            self.input_container.set_well_update_artifact(artifact=pair.input_artifact, well_pos=well_pos)
        if self.output_container is not None:
            well_pos = pair.output_artifact.well.position
            self.output_container.set_well_update_artifact(artifact=pair.output_artifact, well_pos=well_pos)
        if len(self.samples) > 0:
            pair.input_artifact._samples = self.samples
            pair.output_artifact._samples = self.samples
        self.pair = pair

    def with_target_id(self, target_id):
        self.target_id = target_id

    def with_name(self, name):
        self.name = name

    def with_output_udf(self, lims_udf_name, value):
        self.output_udf_dict[lims_udf_name] = value

    def with_input_udf(self, lims_udf_name, value):
        self.input_udf_dict[lims_udf_name] = value

    def with_target_type(self, type):
        self.target_type = type

    def with_input_container(self, container):
        self.input_container = container

    def with_output_container(self, container):
        self.output_container = container

    def add_sample(self, sample):
        self.samples.append(sample)


class SampleBuilder:
    def __init__(self):
        self.udf_dict = dict()
        self.name = None
        self.sample_id = None
        self.project = None

    def with_udf(self, udf_name, value):
        self.udf_dict[udf_name] = value

    def with_id(self, id):
        self.sample_id = id

    def with_name(self, name):
        self.name = name

    def with_project(self, project):
        self.project = project

    def create(self):
        mapping = UdfMapping(self.udf_dict)
        s = Sample(self.sample_id, self.name, udf_map=mapping, project=self.project)
        return s

class ContainerBuilder:
    def __init__(self):
        self.udf_dict = dict()
        self.name = None
        self.id = None

    def with_udf(self, udf_name, value):
        self.udf_dict[udf_name] = value

    def with_id(self, id):
        self.id = id

    def with_name(self, name):
        self.name = name

    def create(self):
        mapping = UdfMapping(self.udf_dict)
        c = Container(container_type=Container.CONTAINER_TYPE_96_WELLS_PLATE, container_id=self.id, name=self.name, udf_map=mapping)
        return c



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

    def get_process_type(self):
        return SimpleNamespace(name="a-step-name")


class FakeStepRepoBuilder:
    def __init__(self):
        self.fake_step_repo = None
        self.process_udf_dict = dict()
        self.active_udfs = list()

    def with_process_udf(self, lims_udf_name, udf_value):
        self.active_udfs.append({'name': lims_udf_name})
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
        self.fake_step_repo.process.active_udfs = self.active_udfs


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
            bs = BytesIO(content.encode('utf-8'))
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

    def upload_files(self, *args, **kwargs):
        pass

from clarity_ext.utility.testing_parse_scripts.builders import FakeStepRepoBuilder
from clarity_ext.utility.testing_parse_scripts.builders import PairBuilder
from clarity_ext.utility.testing_parse_scripts.builders import ContextBuilder


class ReadResultFileBuilder:
    """
    1. call with_analyte_udf, with_output_type, with_mocked_local_shared_file
       (udfs that are to be set from result file)
    2. call with_step_udf (with specific values from user)
    3. call create_pair, N number times
    4. call create
    """
    def __init__(self):
        self.shared_file_handle = None
        self.context_builder = None
        self.step_repo_builder = FakeStepRepoBuilder()
        self.pair_builder = PairBuilder()
        self.extension_type = None

    def create_pair(self, target_artifact_id, name=None):
        artifact_pair_builder = self.pair_builder
        artifact_pair_builder.with_target_id(target_artifact_id)
        artifact_pair_builder.with_name(name)
        artifact_pair_builder.create()
        return artifact_pair_builder.pair

    @property
    def extension(self):
        return self.extension_type(self.context_builder.context)

    def create(self, extension_type, contents, pairs):
        self.extension_type = extension_type
        self.context_builder = ContextBuilder(self.step_repo_builder)
        self.context_builder.with_mocked_local_shared_file(
            self.shared_file_handle, contents)
        for pair in pairs:
            self.context_builder.with_analyte_pair(pair.input_artifact, pair.output_artifact)

    def with_analyte_udf(self, lims_udf_name, udf_value):
        self.pair_builder.with_output_udf(lims_udf_name, udf_value)

    def with_output_type(self, output_type):
        self.pair_builder.target_type = output_type

    def with_step_udf(self, lims_udf_name, udf_value):
        self.step_repo_builder.with_process_udf(lims_udf_name, udf_value)

    def with_mocked_local_shared_file(self, filehandle):
        self.shared_file_handle = filehandle

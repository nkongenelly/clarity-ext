from collections import namedtuple
import xml.etree.ElementTree as ET
from clarity_ext.domain.artifact import Artifact
from clarity_ext.domain.shared_result_file import SharedResultFile
from clarity_ext.repository.container_repository import ContainerRepository
from clarity_ext.domain.user import User
from clarity_ext.domain import ProcessType


class StepRepository(object):
    """
    Provides access to data that's available through a current step.

    All methods return the domain objects, wrapping the REST resources.

    Since the underlying library does caching, this repository does not need
    to do that.
    """

    def __init__(self, session, clarity_mapper):
        """
        Creates a new StepRepository

        :param session: A session object for connecting to Clarity
        """
        self.session = session
        self.clarity_mapper = clarity_mapper
        self.xml_discordance_errors = None

    def all_artifacts(self):
        """
        Fetches all artifacts from the input output map, wraps them in to a domain object.
        From then on, the domain object knows the following:
            * From what resource was it built (for debug reasons, e.g. for getting the URL)
            * Is it an input or output artifact
            * What's the corresponding input or output object (input objects have a reference
              to the output object and vice-versa

        After this, all querying should be done on these domain objects.

        The list is not unique, i.e. artifacts will be fetched more than once.

        Performance note: This method may fetch much more data than necessary as it's designed
        for simplified use of the API. If optimal performance is required, use the underlying REST API
        instead.
        """
        input_output_maps = self.session.current_step.api_resource.input_output_maps
        wrappable_pairs = WrappablePairs(self.session, input_output_maps, WrappablePairs.MODE_STATELESS)
        # We have to defer raising error until all artifacts are fetched.
        # Step log is in the artifacts. The errors are to be written into the step log...
        self.xml_discordance_errors = wrappable_pairs.validate()

        # Artifacts do not contain UDFs that have not been given a value. Since the domain objects returned
        # must know all UDFs available, we fetch them here:
        # TODO: Move this to the service
        process_type = self.get_process_type()

        ret = []
        # TODO: Ensure that the container repo fetches all containers in one batch call:

        # In the case of pools, we might have the same output artifact repeated more than once, ensure
        # that we create only one artifact domain object in this case:
        outputs_by_id = dict()
        container_repo = ContainerRepository()
        for genologics_input, genologics_output, output_generation_type in wrappable_pairs:
            input, output = self._wrap_input_output(
                genologics_input,
                genologics_output,
                container_repo,
                process_type,
                output_generation_type
            )

            if output.id in outputs_by_id:
                output = outputs_by_id[output.id]
            ret.append((input, output))
            outputs_by_id[output.id] = output
        return ret

    def xml_discordance_string(self):
        lst = list()
        for e in self.xml_discordance_errors:
            lst.append(str(e))
        return '\n'.join(lst)

    def _wrap_input_output(self, input_resource, output_resource, container_repo,
                           process_type, output_generation_type):

        # Create a map of all containers, so we can fill in it while building
        # domain objects.

        # Create a fresh container repository. Then we know that only one container
        # will be created for each object in a call to this method
        input = self._wrap_artifact(
            input_resource,
            container_repo,
            gen_type="Input",
            is_input=True,
            process_type=process_type)

        output = self._wrap_artifact(
            output_resource,
            container_repo,
            gen_type=output_generation_type,
            is_input=False,
            process_type=process_type)

        if output_generation_type == "PerInput":
            output.generation_type = Artifact.PER_INPUT
        elif output_generation_type == "PerAllInputs":
            output.generation_type = Artifact.PER_ALL_INPUTS
        else:
            raise NotImplementedError(
                "Generation type {} is not implemented".format(output_generation_type))

        # Add a reference to the other object for convenience:
        # TODO: There are generally several input pairs containing the same input
        # artifact within the same step, where output is either shared result file, or
        # analyte/resultfile. As a consequence, there are several instances of the same
        # input artifact, with different values of .output. When populating containers, there
        # is no check as of which one of these input artifacts are used!
        input.output = output
        output.input = input

        return input, output

    def _wrap_artifact(self, artifact, container_repo, gen_type, is_input, process_type):
        """
        Wraps an artifact in a domain object, if one exists. The domain objects provide logic
        convenient methods for working with the domain object in extensions.
        """

        if artifact.type == "Analyte":
            wrapped = self.clarity_mapper.analyte_create_object(
                artifact, is_input, container_repo, process_type)
        elif artifact.type == "ResultFile" and gen_type == "PerInput":
            wrapped = self.clarity_mapper.result_file_create_object(
                artifact, is_input, container_repo, process_type)
        elif artifact.type == "ResultFile" and gen_type == "PerAllInputs":
            wrapped = SharedResultFile.create_from_rest_resource(
                artifact, process_type)
        else:
            raise Exception("Unknown type and gen_type combination {}, {}".format(
                artifact.type, gen_type))

        # TODO: This is kind of a hack for adding the parent process. Make more use of OOP.
        try:
            wrapped.parent_process = artifact.parent_process
        except AttributeError:
            wrapped.parent_process = None

        return wrapped

    def _wrap_artifacts(self, artifacts):
        for artifact in artifacts:
            yield self._wrap_artifact(artifact)

    def update_artifacts(self, artifacts):
        """Updates all the artifact resources"""
        self.session.api.put_batch(artifacts)

    def current_user(self):
        if not self.session.current_step:
            return None
        current_user_resource = self.session.current_step.technician
        return User.create_from_rest_resource(current_user_resource)

    def get_process_type(self):
        """Returns the process type of the current process"""
        self.session.current_step.api_resource.type.get()
        return ProcessType.create_from_resource(self.session.current_step.api_resource.type)

    def get_process(self):
        """Returns the currently running process (step)"""
        return self.session.current_step


class WrappablePairs(object):
    """
    Contains all artifact pairs within a step, containing genologics Artifact instances
    These are in turn ready to be wrapped into clarity-ext domain instances
    Usage:
    wrappable_pairs = WrappablePairs(session, input_output_maps, mode=<stateful | stateless>)
    wrappable_pairs.validate()  # compares xml for stateful and stateless
    for input, output, output_generation_type in wrappable_pairs:
        input  # genologics Artifact, either stateful or stateless
        output  # genologics Artifact

    The validation compares the stateless and statefull xml representation,
    and discards any discrepancies in the qc-flag
    """

    MODE_STATELESS = "stateless"
    MODE_STATEFUL = "stateful"

    def __init__(self, session, input_output_maps, state_mode):
        # Note, the force flag should be set to False as soon as the test period is over!
        # Develop-1177
        self.force = True
        self.session = session
        self.input_output_maps = input_output_maps
        self.state_mode = state_mode
        self.pairs = list()
        stateful_artifacts = self._fetch_stateful()
        stateless_artifacts = self._fetch_stateless()

        self.pairs = self._assemble_pairs(stateful_artifacts, stateless_artifacts)

    def validate(self):
        errors = list()
        for pair in self.pairs:
            errors.extend(pair.validate(self.session.api))
        return errors

    def __iter__(self):
        self.counter = 0
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        if self.counter == len(self.pairs):
            raise StopIteration
        pair = self.pairs[self.counter]
        self.counter += 1
        return iter((pair.input_artifact, pair.output_artifact, pair.output_generation_type))

    def _assemble_pairs(self, stateful_artifacts, stateless_artifacts):
        pairs = list()
        stateful_by_uri = {artifact.uri: artifact for artifact in stateful_artifacts}
        stateless_by_lims_id = {artifact.id: artifact for artifact in stateless_artifacts}
        for input, output in self.input_output_maps:
            stateful_input = stateful_by_uri[input["uri"].uri]
            fetched_input = ArtifactRepresentation(
                stateful_representation=stateful_input,
                stateless_representation=stateless_by_lims_id[stateful_input.id]
            )
            stateful_output = stateful_by_uri[output["uri"].uri]
            fetched_output = ArtifactRepresentation(
                stateful_representation=stateful_output,
                stateless_representation=stateless_by_lims_id[stateful_output.id]
            )
            pair = Pair(
                input=fetched_input,
                output=fetched_output,
                output_generation_type=output["output-generation-type"],
                state_mode=self.state_mode
            )
            pairs.append(pair)

        return pairs

    def _fetch_stateful(self):
        artifact_keys = set()
        for input, output in self.input_output_maps:
            artifact_keys.add(input["uri"])
            artifact_keys.add(output["uri"])

        return self.session.api.get_batch(artifact_keys, force=self.force)

    def _fetch_stateless(self):
        artifact_keys = set()
        for input, output in self.input_output_maps:
            stateless_input = input["uri"].get_stateless_clone()
            stateless_output = output["uri"].get_stateless_clone()
            artifact_keys.add(stateless_input)
            artifact_keys.add(stateless_output)

        return self.session.api.get_batch(artifact_keys, force=self.force)


class Pair(namedtuple('Pair', ['input', 'output', 'output_generation_type', 'state_mode'])):
    @property
    def input_artifact(self):
        return self._get_artifact(self.input)

    @property
    def output_artifact(self):
        return self._get_artifact(self.output)

    def _get_artifact(self, artifact_repr):
        if self.state_mode == WrappablePairs.MODE_STATEFUL:
            return artifact_repr.stateful_representation
        elif self.state_mode == WrappablePairs.MODE_STATELESS:
            return artifact_repr.stateless_representation
        else:
            raise Exception("Unknown state: {}".format(self.state_mode))

    def validate(self, api):
        errors = list()
        if not api.is_equal(
                self.input.stateless_representation,
                self.input.stateful_representation,
                exclude_tag='qc-flag'
        ):
            errors.append(XmlDiscordanceError(
                self.input.stateless_representation,
                self.input.stateful_representation
            ))

        if not api.is_equal(
            self.output.stateless_representation,
            self.output.stateful_representation,
            exclude_tag='qc-flag'
        ):
            errors.append(XmlDiscordanceError(
                self.output.stateless_representation,
                self.output.stateful_representation
            ))
        return errors


class XmlDiscordanceError(Exception):
    def __init__(self, stateless_representation, stateful_representation):
        self.stateless_representation = stateless_representation
        self.stateful_representation = stateful_representation

    def __repr__(self):
        return "{}\n{}\n{}\n{}\n\n".format(
            'stateless xml:',
            ET.tostring(self.stateless_representation.root),
            '(should match) stateful xml:',
            ET.tostring(self.stateful_representation.root),
        )

    def __str__(self):
        return self.__repr__()


class ArtifactRepresentation(object):
    """
    ArtifactRepresentation contains both the stateless and the statefull
    representation of the same Artifact.

    A validation makes sure there is no discrepancies apart from the qc-flag
    """
    def __init__(self, stateless_representation=None, stateful_representation=None):
        self.stateless_representation = stateless_representation
        self.stateful_representation = stateful_representation

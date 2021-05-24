from genologics.entities import Artifact as ApiArtifact
from clarity_ext.domain.artifact import Artifact
from clarity_ext.domain.shared_result_file import SharedResultFile
from clarity_ext.repository.container_repository import ContainerRepository
from clarity_ext.domain.user import User
from clarity_ext.domain import ProcessType
from urllib.parse import urlparse


class StepRepository(object):
    """
    Provides access to data that's available through a current step.

    All methods return the domain objects, wrapping the REST resources.

    Since the underlying library does caching, this repository does not need
    to do that.
    """

    ARTIFACT_FETCH_STRATEGY_USE_URI = 1
    ARTIFACT_FETCH_STRATEGY_USE_CURRENT_STATE = 2
    ARTIFACT_FETCH_STRATEGY_USE_POST_PROCESS_URI = 3


    def __init__(self, session, clarity_mapper):
        """
        Creates a new StepRepository

        :param session: A session object for connecting to Clarity
        """
        self.session = session
        self.clarity_mapper = clarity_mapper

        self._input_strategy = self.ARTIFACT_FETCH_STRATEGY_USE_CURRENT_STATE
        self._output_strategy = self.ARTIFACT_FETCH_STRATEGY_USE_CURRENT_STATE

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

        def fetch_entry(strategy, info_object):
            # NOTE: When fetching step info, artifacts come in a certain state, but this state
            # is *not* the latest state. In particular, if QC flags have been set by another script
            # or the user in the UI, we don't see the latest changes. Because of this
            # we want to fetch using the current state, which you can do by not sending in the
            # state flag.
            # Temporarily, we provide two other strategies for this. These are only provided for
            # debug reasons and should not be altered.
            if strategy == self.ARTIFACT_FETCH_STRATEGY_USE_URI:
                return info_object["uri"]
            elif strategy == self.ARTIFACT_FETCH_STRATEGY_USE_CURRENT_STATE:
                # The other two strategies fetch using the state flag:
                # https://lims-dev.snpseq.medsci.uu.se/api/v2/artifacts/2-192121?state=108523
                # as that's in the input/output map we get from the backend.
                # Here we remove this state flag
                overview_entry = info_object["uri"]

                parsed = urlparse(overview_entry.uri)
                current_state_uri = "{}://{}{}".format(parsed.scheme, parsed.netloc, parsed.path)
                return ApiArtifact(overview_entry.lims, uri=current_state_uri)
            elif strategy == self.ARTIFACT_FETCH_STRATEGY_USE_POST_PROCESS_URI:
                return info_object["post-process-uri"]

        def fetch_input(info_object):
            return fetch_entry(self._input_strategy, info_object)

        def fetch_output(info_object):
            return fetch_entry(self._output_strategy, info_object)

        input_output_maps = self.session.current_step.api_resource.input_output_maps

        artifact_keys = set()

        for input_info, output_info in input_output_maps:
            artifact_keys.add(fetch_input(input_info))
            artifact_keys.add(fetch_output(output_info))

        artifacts = self.session.api.get_batch(artifact_keys)

        artifacts_by_uri = {artifact.uri: artifact for artifact in artifacts}


        # Artifacts do not contain UDFs that have not been given a value. Since the domain
        # objects returned must know all UDFs available, we fetch them here:
        # TODO: Move this to the service
        process_type = self.get_process_type()

        ret = []
        # TODO: Ensure that the container repo fetches all containers in one batch call:

        # In the case of pools, we might have the same output artifact repeated more than once, ensure
        # that we create only one artifact domain object in this case:
        outputs_by_id = dict()
        container_repo = ContainerRepository()

        for input_info, output_info in input_output_maps:
            input_resource = artifacts_by_uri[fetch_input(input_info).uri]
            output_resource = artifacts_by_uri[fetch_output(output_info).uri]
            output_gen_type = output_info["output-generation-type"]

            input_domain_obj, output_domain_obj = self._wrap_input_output(
                    input_resource,
                    output_resource,
                    output_gen_type,
                    container_repo,
                    process_type)
            if output_domain_obj.id in outputs_by_id:
                output_domain_obj = outputs_by_id[output_domain_obj.id]
            ret.append((input_domain_obj, output_domain_obj))
            outputs_by_id[output_domain_obj.id] = output_domain_obj
        return ret

    def _wrap_input_output(self,
            input_resource,
            output_resource,
            output_generation_type,
            process_type):
        # Create a map of all containers, so we can fill in it while building
        # domain objects.

        # Create a fresh container repository. Then we know that only one container
        # will be created for each object in a call to this method

        input = self._wrap_artifact(
            input_resource,
            gen_type="Input",
            is_input=True,
            process_type=process_type)

        output = self._wrap_artifact(
            output_resource,
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

    def _wrap_artifact(self, artifact, gen_type, is_input, process_type):
        """
        Wraps an artifact in a domain object, if one exists. The domain objects provide logic
        convenient methods for working with the domain object in extensions.
        """

        if artifact.type == "Analyte":
            wrapped = self.clarity_mapper.analyte_create_object(
                artifact, is_input, process_type)
        elif artifact.type == "ResultFile" and gen_type == "PerInput":
            wrapped = self.clarity_mapper.result_file_create_object(
                artifact, is_input, process_type)
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

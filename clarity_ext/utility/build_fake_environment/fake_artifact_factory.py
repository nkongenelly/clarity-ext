from clarity_ext.domain import *
from clarity_ext.service.dilution.service import *


class FakeArtifactFactory:
    """
    Create artifact pairs and place them in containers
    Containers are stored and re-used between calls to create_pair()
    """
    def __init__(self, create_well_order=Container.DOWN_FIRST,
                 source_container_type=Container.CONTAINER_TYPE_96_WELLS_PLATE,
                 target_container_type=Container.CONTAINER_TYPE_96_WELLS_PLATE):

        self.default_source_container = self._create_container('source', True, source_container_type)
        self.default_target_container = self._create_container('target', False, target_container_type)
        self.well_enumerator = self.default_source_container.enumerate_wells(create_well_order)

    def _create_container(self, container_id, is_source, container_type):
        return Container(
            container_type=container_type, container_id=container_id,
            name=container_id, is_source=is_source)

    def _create_artifact(self, is_input, name, artifact_type=None, id=None):
        return artifact_type(
            is_input=is_input, id=id, name=name,samples=None, api_resource=None)

    def create_pair(self, pos_from=None, pos_to=None, source_type=Analyte,
                    target_type=Analyte, source_id=None, target_id=None):

        if pos_from is None:
            well = next(self.well_enumerator)
            pos_from = well.position
        if pos_to is None:
            pos_to = pos_from

        source_name = 'in-FROM:{}-{}'.format('source', pos_from)
        target_name = "out-FROM:{}-{}".format('target', pos_from)

        pair = ArtifactPair(self._create_artifact(True, source_name, source_type, id=source_id),
                            self._create_artifact(False, target_name, target_type, id=target_id))
        self.default_source_container.set_well_update_artifact(pos_from, artifact=pair.input_artifact)
        self.default_target_container.set_well_update_artifact(pos_to, artifact=pair.output_artifact)
        return pair

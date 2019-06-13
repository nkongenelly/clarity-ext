import re
from clarity_ext.utils import single
from clarity_ext.domain.container import PlateSize
from clarity_ext.domain.container import ContainerPosition
from clarity_ext.domain.validation import ValidationException


class ConfigValidator:
    def __init__(self, validation_service, robot_settings_list, category):
        self.validation_service = validation_service
        self.robot_settings_list = robot_settings_list
        self.category = category

    def validate(self, expected_sample_name, samples, input_analytes):
        if len(samples) == 0:
            msg = 'The selected reagent category cannot be handled by the lims. '\
                  'No matching sample could be found that is holding index tag configuration. ' \
                  'See Canea for adding samples that hold '\
                  'index tag configurations. Tag group: {}. Expected sample name: {}'\
                .format(self.category, expected_sample_name)
            exc = ValidationException(msg)
            self.validation_service.handle_validation([exc])

        sample = single(samples)
        errors = list()
        if ' ' in sample.udf_indexconfig_short_name.strip():
            exc = ValidationException('The udf indexconfig_short_name contains spaces, '
                                      '{}, sample: {}'.format(sample.udf_indexconfig_short_name, sample.name))
            errors.append(exc)

        config_parser = ConfigParser(sample)
        for robot in self.robot_settings_list:
            index_mapping_as_text = config_parser.index_mapping_as_text(robot)
            format_errors = self._check_format(index_mapping_as_text)
            contents_errors = list()
            if len(format_errors) == 0:
                source_dimensions = config_parser.source_dimensions(robot)
                index_mapping_dict = config_parser.index_mapping_dict(robot)
                contents_errors = self._check_contents(index_mapping_dict,
                                                       source_dimensions,
                                                       input_analytes)
            if len(format_errors) > 0 or len(contents_errors) > 0:
                msg = 'The sample udf indexconfig_index_position_map_{} could not be parsed. ' \
                      'Sample holding the configuration: {}'.format(robot.name.lower(), sample.name)
                exc = ValidationException(msg)
                errors.append(exc)
                errors.extend(format_errors)
                errors.extend(contents_errors)

        if len(errors) > 0:
            self.validation_service.handle_validation(errors)

    def _check_format(self, index_mapping):
        rows = index_mapping.split('\n')
        errors = list()
        for row in rows:
            splitted_row = row.strip().split('\t')
            if len(splitted_row) != 2:
                msg = 'This row has not exactly two columns separated by tab delimiter: {}.' \
                      ''.format(row)
                errors.append(ValidationException(msg))
            else:
                pos = splitted_row[1]
                res = re.match('[A-Z]:[0-9]+', pos)
                if res is None:
                    msg = 'This position reference doesn\'t fit into the Clarity standard of e.g. ' \
                          'A:1, C:8, etc, row: {}'.format(row)
                    errors.append(ValidationException(msg))
        return errors

    def _check_contents(self, index_mapping_dict, source_dimensions, input_analytes):
        errors = list()
        for label in index_mapping_dict:
            pos = index_mapping_dict[label]
            container_position = ContainerPosition.create(pos)
            if self._is_outside_dimensions(container_position, source_dimensions):
                msg = 'This position goes outside the dimension of the plate/tuberack.' \
                      'Index: {}, position: {}, container rows: {}, container columns: {}' \
                    .format(label, pos, source_dimensions.height, source_dimensions.width)
                errors.append(ValidationException(msg))
        for analyte in input_analytes:
            label = analyte.get_reagent_label()
            if label not in index_mapping_dict:
                msg = 'Configuration error. The index for this sample is not present ' \
                      'in the index mapping from ' \
                      'the taggroup configuration. Sample: {}, sample index: {}, tag group: {}'\
                    .format(analyte.name, label, self.category)
                errors.append(ValidationException(msg))
        return errors

    def _is_outside_dimensions(self, position, platesize):
        return position.row > platesize.height or position.col > platesize.width


class ConfigParser:
    def __init__(self, sample):
        self.map_index_positions_hamilton = sample.udf_indexconfig_index_position_map_hamilton
        self.source_dimensions_columns_hamilton = sample.udf_indexconfig_source_dimensions_columns_hamilton
        self.source_dimensions_rows_hamilton = sample.udf_indexconfig_source_dimensions_rows_hamilton
        self.map_index_positions_biomek = sample.udf_indexconfig_index_position_map_biomek
        self.source_dimensions_columns_biomek = sample.udf_indexconfig_source_dimensions_columns_biomek
        self.source_dimensions_rows_biomek = sample.udf_indexconfig_source_dimensions_rows_biomek
        self.short_name = sample.udf_indexconfig_short_name

    def source_dimensions(self, robot_settings):
        if robot_settings.name == 'hamilton':
            return PlateSize(height=self.source_dimensions_rows_hamilton,
                             width=self.source_dimensions_columns_hamilton)
        elif robot_settings.name == 'biomek':
            return PlateSize(height=self.source_dimensions_rows_biomek,
                             width=self.source_dimensions_columns_biomek)

    def index_mapping_as_text(self, robot_settings):
        if robot_settings.name == 'hamilton':
            return self.map_index_positions_hamilton
        elif robot_settings.name == 'biomek':
            return self.map_index_positions_biomek

    def index_mapping_dict(self, robot_settings):
        index_position_map = self.index_mapping_as_text(robot_settings)
        rows = index_position_map.split('\n')
        index_pos_dict = dict()
        for row in rows:
            label, pos = row.strip().split('\t')
            index_pos_dict[label] = pos

        return index_pos_dict
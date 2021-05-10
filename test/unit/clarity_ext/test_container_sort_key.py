import unittest
from clarity_ext.service.dilution.service import SortStrategy


class TestPlateSortOrder(unittest.TestCase):
    def create_container(self, name, is_temporary):
        c = Dummy()
        c.name = name
        c.is_temporary = is_temporary
        c.sort_weight = 0
        return c

    def test_sort_key_for_plate(self):
        platename = "code-123_Plate432_org_171010"
        c = self.create_container(platename, False)
        sortlist = SortStrategy.container_sort_key(c)
        self.assertEqual((0, True, 'code', 0, '', 123, 'plate', 432, 'org', 0, '', 171010), sortlist)

    def test_validation_error__with_one_lims_id_and_one_ordinary_name(self):
        name1 = "27-8473"
        name2 = "Test-RNA1_PL1_org_210428"
        plate1 = self.create_container(name1, False)
        plate2 = self.create_container(name2, False)
        platelist = sorted([plate2, plate1], key=SortStrategy.container_sort_key)
        self.assertEqual("27-8473", platelist[0].name)
        self.assertEqual("Test-RNA1_PL1_org_210428", platelist[1].name)

    def test_create_sort_key_from_with_id(self):
        assert SortStrategy.create_sort_key_from("24-1234") == ('', 24, '', 1234)

    def test_create_sort_key_from_with_original_expected(self):
        # Original naming convention when this was implemented
        assert (SortStrategy.create_sort_key_from("Test-RNA1_PL1_org_210428") ==
                ('test', 0, 'rna', 1, 'pl', 1, 'org', 0, '', 210428))

    def test_create_sort_key_from_with_original_unexpected_but_documented(self):
        assert (SortStrategy.create_sort_key_from("2ab1_plate3-210505") ==
                ('ab', 2, '', 1, 'plate', 3, '', 210505))

class Dummy:
    pass

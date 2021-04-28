import unittest
from clarity_ext.utility.xml_comparison import ComparableXml
from resources.resource_bag import get_same_without_qc_flags
from resources.resource_bag import get_same_but_in_different_order
from resources.resource_bag import get_same_pools_with_different_order
from resources.resource_bag import get_differeing_qc_flags
from resources.resource_bag import get_different_outside_qc_flag


class TestXmlComparison(unittest.TestCase):
    def test_identical_xmls(self):
        xml1, xml2 = get_same_without_qc_flags()
        str1 = self._parse(xml1)
        str2 = self._parse(xml2)
        self.assertEqual(str1, str2)

    def test_same_but_different_order(self):
        xml1, xml2 = get_same_but_in_different_order()
        str1 = self._parse(xml1)
        str2 = self._parse(xml2)
        self.assertEqual(str1, str2)

    def test_pools_in_different_order(self):
        xml1, xml2 = get_same_pools_with_different_order()
        str1 = self._parse(xml1)
        str2 = self._parse(xml2)
        self.assertEqual(str1, str2)

    def test_exclude_qc_flag(self):
        xml1, xml2 = get_differeing_qc_flags()
        str1 = self._parse(xml1)
        str2 = self._parse(xml2)
        self.assertEqual(str1, str2)

    def test_different_xml__is_discovered(self):
        xml1, xml2 = get_different_outside_qc_flag()
        str1 = self._parse(xml1)
        str2 = self._parse(xml2)
        self.assertNotEqual(str1, str2)

    def _parse(self, resource):
        comparable = ComparableXml(resource, exclude_tag='qc-flag')
        return comparable.tostring()

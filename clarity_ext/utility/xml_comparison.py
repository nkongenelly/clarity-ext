import re
import xml.etree.ElementTree as ET


class ComparableXml(object):
    def __init__(self, xml_string, exclude_tag=None):
        root = ET.fromstring(xml_string)
        self._set_sorted_rec(root)
        if exclude_tag:
            self._exclude_tag(root, exclude_tag)
        self.root = root

    def _exclude_tag(self, root, exclude):
        for el in root.findall(exclude):
            root.remove(el)

    def _set_sorted_rec(self, element):
        for sub_element in element:
            self._set_sorted_rec(sub_element)
        element[:] = sorted(element, key=self._element_sort_key)

    def _element_sort_key(self, el):
        attrib = sorted(el.attrib.items())
        key = el.tag
        for attr, value in attrib:
            key += value
        return key

    def tostring(self):
        # Remove all whitespaces in string. Indentation in output cause problems.
        return re.sub(r'\s+', '', ET.tostring(self.root))

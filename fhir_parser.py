# -*- coding: utf-8 -*-
import re
import os
import json
from fhir_spec import SPECS

# TODO: support parsing path wild card path
# e.g. Extension.value[x]

DATE_RE = re.compile(r'-?([1-9][0-9]{3}|0[0-9]{3})(-(0[1-9]|1[0-2])(-(0[1-9]|[12][0-9]|3[01]))?)?')
DATETIME_RE = re.compile(r'-?([1-9][0-9]{3}|0[0-9]{3})(-(0[1-9]|1[0-2])(-(0[1-9]|[12][0-9]|3[01])(T(([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]+)?|(24:00:00(\.0+)?))(Z|(\+|-)((0[0-9]|1[0-3]):[0-5][0-9]|14:00))?)?)?)?')
ID_RE = re.compile(r'[a-z0-9\-\.]{1,36}')
INSTANT_RE = re.compile(r'[1-9][0-9]{3}-.+T[^.]+(Z|[+-].+)')
OID_RE = re.compile(r'urn:oid:\d+\.\d+\.\d+\.\d+')
UUID_RE = re.compile(r'urn:uuid:[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}')
URI_RE = re.compile(r'''(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))''')

def validate_by_regex(regex):
    return lambda data: regex.match(str(data)) is not None


def validate_by_instance(datatype):
    return lambda data: isinstance(data, datatype)

FHIR_PRIMITIVE_VALIDATORS = {
    'base64Binary': validate_by_instance(basestring),
    'boolean': validate_by_instance(bool),
    'date': validate_by_regex(DATE_RE),
    'dateTime': validate_by_regex(DATETIME_RE),
    'decimal': validate_by_instance(float),
    'id': validate_by_regex(ID_RE),
    'instant': validate_by_regex(INSTANT_RE),
    'integer': validate_by_instance(int),
    'oid': validate_by_regex(OID_RE),
    'string': validate_by_instance(basestring),
    'uri': validate_by_regex(URI_RE),
    'uuid': validate_by_regex(UUID_RE),
}

FHIR_PRIMITIVE_INIT = {
    'boolean': lambda bl: bl == 'true',
    'decimal': float,
    'integer': int
}


def parse(datatype, data, correctible):
    '''
    walk through a complex datatype or a resource and collect elements bound to search params
    '''
    search_elements = []
    if datatype in SPECS:
        elements = [FHIRElement(element_spec, correctible)
                    for element_spec in SPECS[datatype]['elements']]
        search_elements = [element.get_search_elements()
                           for element in elements if element.validate(data)]
        if len(elements) != len(search_elements):
            return False, None
        search_elements = filter(
            lambda x: x.get('spec') is not None, search_elements)
    return True, search_elements


def parse_resource(resource_type, resource, correctible=False):
    '''
    parse a resource

    with `correctible` being `True` the validate function will try to make an invalid resource valid if possible.
    i.e. making changes such as "1" -> 1, {'a': 1} -> [{'a', 1}] to fit the profile description
    '''
    if resource.get('resourceType') == resource_type:
        return parse(resource_type, resource, correctible)
    return False, None


def correct_element(element, element_types):
    for et in element_types:
        if et in FHIR_PRIMITIVE_INIT:
            try:
                return FHIR_PRIMITIVE_INIT[et](element)
            except:
                pass

class FHIRElement(object):

    def __init__(self, spec, correctible):
        self.correctible = correctible
        self.path = spec['path']
        self.elem_types = []
        if 'type' in spec['definition']:
            self.elem_types = [_type['code']
                               for _type in spec['definition']['type']]
        self.min_occurs = spec['definition']['min']
        self.max_occurs = spec['definition']['max']
        self.search_spec = spec.get('searchParam')
        self.search_elements = []

    def _push_ancestors(self, jsondict, path_elems, elem_ancestors):
        cur_key = path_elems[0]
        if cur_key not in jsondict:
            return
        val = jsondict[cur_key]
        if isinstance(val, dict):
            elem_ancestors.append((val, path_elems[1:]))
        else:
            elem_ancestors.extend(
                [(ancestor, path_elems[1:]) for ancestor in val])

    def get_search_elements(self):
        return {'spec': self.search_spec, 'elements': self.search_elements}

    def validate(self, data):
        path_elems = self.path.split('.')
        if len(path_elems) == 1:
            return True
        elem_name = path_elems[-1]
        path_elems = path_elems[1:-1]
        elem_parents = []
        elem_ancestors = []

        if len(path_elems) == 0:
            elem_parents = [data]
        else:
            self._push_ancestors(data, path_elems, elem_ancestors)

        while len(elem_ancestors) > 0:
            ancestor, ancestor_path = elem_ancestors.pop()
            if len(ancestor_path) == 0:
                elem_parents.append(ancestor)
            else:
                self._push_ancestors(ancestor, path_elems, elem_ancestors)

        for parent in elem_parents:
            elem = parent.get(elem_name)

            if elem is None:
                if self.min_occurs > 0:
                    return False
                continue

            if isinstance(elem, list):
                if self.max_occurs != "*":
                    return False

                elems = elem
                for i, elem in enumerate(elems):
                    if not self.validate_elem(elem):
                        if not self.correctible:
                            return False

                        corrected = correct_element(elem, self.elem_types)
                        if corrected is not None:
                            elems[i] = corrected
                        return False

            elif self.max_occurs == '*' and not self.correctible:
                return False

            elif not self.validate_elem(elem):
                if not self.correctible:
                    return False

                corrected = correct_element(elem, self.elem_types)
                if corrected is not None:
                    if self.max_occurs == '*':
                        parent[elem_name] = [corrected]
                    else:
                        parent[elem_name] = corrected
                else:
                    return False
            elif self.max_occurs == '*':
                # in this case, the elem itself is correct, with a cardinality
                # or '*' but stored as a single item
                parent[elem_name] = [elem]

        return True

    def validate_elem(self, elem):
        for elem_type in self.elem_types:
            if elem_type in FHIR_PRIMITIVE_VALIDATORS:
                validate_func = FHIR_PRIMITIVE_VALIDATORS[elem_type]
                if not validate_func(elem):
                    return False
                else:
                    continue

            elif elem_type == 'Resource' and 'resourceType' in elem:
                elem_type = elem.resourceType

            # type of the element is a complex type
            valid, _ = parse(elem_type, elem, self.correctible)
            if not valid:
                return False

        if self.search_spec is not None:
            self.search_elements.append(elem)

        return True

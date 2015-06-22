from flask import Response
from lxml import etree
from functools import partial
import json
import uuid
import hashlib
from werkzeug.datastructures import MultiDict

FHIR_JSON_MIMETYPE = 'application/json'
FHIR_XML_MIMETYPE = 'application/xml'
FHIR_BUNDLE_MIMETYPE = 'application/xml'

FHIR_XMLNS = 'http://hl7.org/fhir'
XHTML_XMLNS = 'http://www.w3.org/1999/xhtml'

json_response = partial(Response, mimetype=FHIR_JSON_MIMETYPE)
xml_response = partial(Response, mimetype=FHIR_XML_MIMETYPE)
xml_bundle_response = partial(Response, mimetype=FHIR_BUNDLE_MIMETYPE)


def _xml_to_json(root):
    '''
    helper function for converting an xml-formated FHIR resource into an json object

    NOTE this can obviously be implemented way more efficient without recursion
    '''
    if root.tag.split('}')[-1] == 'div':
        return etree.tostring(root)
    elif 'value' in root.attrib:
        return root.attrib['value']

    jsondict = {}

    for element in root:
        json_element = _xml_to_json(element)
        tag_name = element.tag.split('}')[-1]
        tag_val = jsondict.get(tag_name)
        if tag_val is None:
            jsondict[tag_name] = json_element
        elif isinstance(tag_val, list):
            tag_val.append(json_element)
        else:
            jsondict[tag_name] = [tag_val, json_element]

    jsondict.update(root.attrib)
    return jsondict


def xml_to_json(root, resource_type):
    '''
    Convert an xml-formated FHIR resource into an json object
    '''
    if 'xmlns' in root.attrib:
        del root.attrib['xmlns']
    jsondict = _xml_to_json(root)
    jsondict['resourceType'] = resource_type
    return jsondict


def _to_xml(data, root):
    '''
    convert a single json element (int, boolean, or object) into corresponding FHIR-XML-encoding
    '''
    if isinstance(data, dict):
        _json_to_xml(data, root)
    else:
        data_str = str(data)
        if isinstance(data, bool):
            data_str = data_str.lower()
        root.set('value', data_str)


def _json_to_xml(jsondict, root):
    '''
    helper function for converting a json-formated FHIR resource into xml
    '''
    for k, v in jsondict.iteritems():
        if isinstance(v, list):
            for el in v:
                new_node = etree.SubElement(root, k)
                _to_xml(el, new_node)
        else:
            if k == 'div' and isinstance(v, basestring):
                try:
                    root.append(etree.fromstring(v))
                    continue
                except:
                    pass
            new_node = etree.SubElement(root, k)
            _to_xml(v, new_node)


def json_to_xml(jsondict):
    '''
    Convert a json-formated FHIR resource into xml
    '''
    resource_type = jsondict['resourceType']
    del jsondict['resourceType']
    root = etree.Element(resource_type)
    root.set('xmlns', FHIR_XMLNS)
    _json_to_xml(jsondict, root)
    return etree.tostring(root)


def iterdict(d):
    '''
    Similar to dict.iteritems
    for something like {1 : [1,2,3,4]},
    it yields streams below:
        1, 1
        1, 2
        1, 3
        1, 4
    '''
    if isinstance(d, MultiDict):
        for k in d:
            for v in d.getlist(k):
                yield k, v
    else:
        for k, v in d.iteritems():
            yield k, v


def hash_password(password, salt=None):
    '''
    hash a password based on a salt
    if salt not given, randomly generate one
    '''
    if salt is None:
        salt = uuid.uuid4().hex
    hashed = hashlib.sha512(password + salt).hexdigest()
    return hashed, salt

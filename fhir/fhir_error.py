from flask import request, Response
import json
from util import json_to_xml, xml_response, json_response 

CODES = {
    '404': ('Resource not found', 'error'),
    '410': ('Resource deleted', 'error'),
    '405': ('Method not allowed', 'fatal'),
    '403': ('Request not authorized.', 'fatal'),
    '400': ('Bad request (possibly mal-formatted request)', 'fatal'),
    '204': ('Resource successfully deleted', 'information')
}

def new_error(status_code):
    '''
    Create a new OperationOutcome resource from HTTP status_code
    '''
    msg, severity = CODES[status_code]
    outcome_content = {
        'resourceType': 'OperationOutcome',
        'issue': {
            'severity': severity,
            'details': msg
        }
    }
    is_xml = (request.args.get('_format', 'xml') == 'xml')
    response= (json_response(json.dumps(outcome_content))
            if not is_xml
            else xml_response(json_to_xml(outcome_content)))
    response.status = status_code
    return response


inform_not_found = lambda: new_error('404')
inform_gone = lambda: new_error('410')
inform_not_allowed = lambda: new_error('405')
inform_bad_request = lambda: new_error('400')
inform_no_content = lambda: new_error('204')
inform_forbidden = lambda: new_error('403')

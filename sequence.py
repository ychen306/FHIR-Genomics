'''
Add support for Sequence resource
'''
sequence_resource = {
    'elements': [
        {
            'path': 'Sequence',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'Resource'}]
            }
        }, {
            'path': 'Sequence.patient',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'Resource'}]
            },
            'searchParam': {
                'name': 'patient',
                'type': 'reference'
             }
        }, {
            'path': 'Sequence.type',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'code'}]
            },
            'searchParam': {
                'name': 'type',
                'type': 'token'
            }
        }, {
            'path': 'Sequence.quantity',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'Quantity'}]
            },
            'searchParam': {
                'name': 'quantity',
                'type': 'quantity'
            }
        }, {
            'path': 'Sequence.quality',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'decimal'}]
            },
            'searchParam': {
                'name': 'quality',
                'type': 'quantity'
            }
        }, {
            'path': 'Sequence.source',
            'definition': {
                'min': 0,
                'max': '1',
            }
        }, {
            'path': 'Sequence.source.sample',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'code'}]
            },
            'searchParam': {
                'name': 'sample',
                'type': 'token'
            }
        }, {
            'path': 'Sequence.source.lab',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'Resource'}]
            },
            'searchParam': {
                'name': 'lab',
                'type': 'reference'
            }
        }, {
            'path': 'Sequence.cigar',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'string'}]
            }
        }, {
            'path': 'Sequence.reference',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'string'}]
            }
        }, {
            'path': 'Sequence.chromosome',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'string'}]
            },
            'searchParam': {
                'name': 'chromosome',
                'type': 'string'
            }
        }, {
            'path': 'Sequence.startPosition',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'integer'}]
            },
            'searchParam': {
                'name': 'start-position',
                'type': 'quantity'
            }
        }, {
            'path': 'Sequence.endPosition',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'integer'}]
            },
            'searchParam': {
                'name': 'end-position',
                'type': 'quantity'
            }
        }, {
            'path': 'Sequence.assembly',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'string'}]
            },
            'searchParam': {
                'name': 'assembly',
                'type': 'string'
            }
        }, {
            'path': 'Sequence.read',
            'definition': {
                'min': 1,
                'max': '*',
                'type': [{'code': 'string'}]
            }
        }
    ],
    'searchParams': {}
}

for element in sequence_resource['elements']:
    if 'searchParam' not in element:
        continue
    param_name = element['searchParam']['name']
    param_type = element['searchParam']['type']
    sequence_resource['searchParams'][param_name] = param_type 

sequence_reference_types = {
    'patient': ['Patient'],
    'lab': ['Procedure']
}

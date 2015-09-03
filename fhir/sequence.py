'''
Specification for Sequence resource
'''
# "schema" for Sequence resource
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
            'path': 'Sequence.timeDetermined',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'dateTime'}]
            },
            'searchParam': {
                'name': 'time-determined',
                'type': 'date'
             }
        }, {
            'path': 'Sequence.variation',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'CodeableConcpet'}]
            },
            'searchParam': {
                'name': 'variation',
                'type': 'token'
             }
        }, {
            'path': 'Sequence.variationType',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'CodeableConcpet'}]
            },
            'searchParam': {
                'name': 'variation-type',
                'type': 'token'
             }
        }, {
            'path': 'Sequence.region',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'CodeableConcpet'}]
            }
        }, {
            'path': 'Sequence.gene',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'CodeableConcpet'}]
            },
        }, {
            'path': 'Sequence.species',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'CodeableConcpet'}]
            }
        }, {
            'path': 'Sequence.chromosome',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'CodeableConcpet'}]
            },
            'searchParam': {
                'name': 'chromosome',
                'type': 'token'
             }
        }, {
            'path': 'Sequence.genomeBuild',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'CodeableConcpet'}]
            }
        }, {
            'path': 'Sequence.start',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'integer'}]
            },
            'searchParam': {
                'name': 'start',
                'type': 'number'
             }
        }, {
            'path': 'Sequence.end',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'integer'}]
            },
            'searchParam': {
                'name': 'end',
                'type': 'number'
             }
        }, {
            'path': 'Sequence.source',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'CodeableConcpet'}]
            },
            'searchParam': {
                'name': 'source',
                'type': 'token'
             }
        }, {
            'path': 'Sequence.request',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'Resource'}]
            },
            'searchParam': {
                'name': 'request',
                'type': 'reference'
             }
        }, {
            'path': 'Sequence.analysis',
            'definition': {
                'min': 0,
                'max': '*',
            }
        }, {
            'path': 'Sequence.analysis.target',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'CodeableConcpet'}]
            },
            'searchParam': {
                'name': 'analysis-target',
                'type': 'token'
             }
        }, {
            'path': 'Sequence.analysis.type',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'CodeableConcpet'}]
            }
        }, {
            'path': 'Sequence.analysis.interpretation',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'CodeableConcpet'}]
            }
        }, {
            'path': 'Sequence.analysis.confidence',
            'definition': {
                'min': 1,
                'max': '1',
                'type': [{'code': 'code'}]
            }
        }, {
            'path': 'Sequence.gaRepository',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'uri'}]
            }
        }, {
            'path': 'Sequence.gaVariantSet',
            'definition': {
                'min': 0,
                'max': '*',
                'type': [{'code': 'string'}]
            }
        }, {
            'path': 'Sequence.gaCallSet',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'string'}]
            }
        }, {
            'path': 'Sequence.ReadGroup',
            'definition': {
                'min': 0,
                'max': '1',
                'type': [{'code': 'string'}]
            }
        }
    ],
    'searchParams': {}
}

# collect search parameters of Sequence resource
for element in sequence_resource['elements']:
    if 'searchParam' not in element:
        continue
    param_name = element['searchParam']['name']
    param_type = element['searchParam']['type']
    sequence_resource['searchParams'][param_name] = param_type 

# this is used to inform the spec loader
# the exact types of reference search parameters
# E.g. patient is a search parameter of type Patient.
# Some parameter can be references to multiple types of resources
# so it's a list
sequence_reference_types = {
    'patient': ['Patient'],
    'lab': ['Procedure']
}

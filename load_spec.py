import re
import os
import sys
import json
from fhir.sequence import sequence_resource, sequence_reference_types

# RE used to search resource profiles in FHIR's specs. directory
PROFILE_F_RE = re.compile(r'^type-(?P<datatype>\w+).profile.json$|^(?P<resource>\w+).profile.json$')
WARNING = 'WARNING: this is auto generated. Change it at your risk.'

def load_and_process_profile(profile_loc):
    '''
    load a profile file and prepare it as internal structure for specs. code generation
    '''
    with open(profile_loc) as profile_f:
        return process_profile(json.load(profile_f))


def process_profile(profile):
    '''
    Process a resource profile (in FHIR's JSON format)
    as our internal structure for specs. code generation
    '''
    elements = profile['structure'][0]['element']
    search_params = {param['xpath'].replace('f:', '').replace('/', '.'): param
                     for param in profile['structure'][0].get('searchParam', [])
                     if 'xpath' in param}
    # `refeence_types` maintains the mapping
    # between a search parameter of type ResourceReference and possible resource types
    reference_types = {}
    for element in elements:
        path = element['path']
        search_param = search_params.get(path)
        if search_param is not None:
            # delete elements we don't care about
            del search_param['documentation']
            del search_param['xpath']
            element['searchParam'] = search_param
            # get resource type of all resource reference
            # these will be used by a chained query where type of referenced
            # resource might be implied
            if 'type' not in element['definition']:
                continue
            types = []
            for element_type in element['definition']['type']:
                if element_type['code'] == 'ResourceReference':
                    # 'profile' looks something like this [url]/[resource name]
                    reference_type = element_type['profile'].split('/')[-1]
                    types.append(reference_type)

            reference_types[search_param['name']] = types or None

    search_params = {param['name']: param['type']
                     for param in search_params.values()}
    return elements, search_params, reference_types


def load_spec(spec_dir):
    '''
    Load FHIR specs. given directory of all the profiles
    (FHIR uses Profile resource to document specs.)
    '''
    specs = {}
    resources = []
    reference_types = {}
    for f in os.listdir(spec_dir):
        matched = PROFILE_F_RE.match(f)
        if matched is not None:
            profile_loc = os.path.join(spec_dir, f)
            elements, resource_search_params, resource_reference_types = load_and_process_profile(
                profile_loc)
            name = elements[0]['path']
            # manually add assessed-condition into list of serach params
            if name == 'Observation':
                resource_search_params['assessed-condition'] = 'reference'
                resource_reference_types['assessed-condition'] = ['Condition']

            specs[name] = {
                'elements': elements,
                'searchParams': resource_search_params
            }

            if matched.group('resource') is not None:
                resources.append(name)
                reference_types[name] = resource_reference_types

            print 'Loaded %s\'s profile' % name
    # manually load sequence spec
    specs['Sequence'] = sequence_resource
    reference_types['Sequence'] = sequence_reference_types
    resources.append('Sequence')
    print 'manually added Sequence resource for genomic support.'

    with open('fhir/fhir_spec.py', 'w') as spec_target:
        spec_target.write("'''\n%s\n'''" % WARNING)
        spec_target.write('\n')
        spec_target.write('SPECS=' + str(specs))
        spec_target.write('\n')
        spec_target.write('RESOURCES=set(%s)'% str(resources))
        spec_target.write('\n')
        spec_target.write('REFERENCE_TYPES=' + str(reference_types))

if __name__ == '__main__':
    # find out where the specs. directory is.
    # Should be supplied via either command line or config file
    if len(sys.argv) == 2: 
        spec_dir = sys.argv[1]
    else:
        try:
            from config import FHIR_SPEC_DIR
            spec_dir = FHIR_SPEC_DIR
        except ImportError:
            print 'Unable to find FHIR spec directory..'
            print 'specify with `FHIR_SPEC_DIR` in `config.py`'
            print 'or do'
            print '$ python load_spec.py [spec dir]'
            sys.exit(1) 
    load_spec(spec_dir)
    print 'finished.!'

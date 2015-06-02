from flask import request, g
from functools import wraps
from itertools import chain
from models import TTAMClient, TTAMOAuthError
from ..models import Resource
from ..query_builder import COORD_RE, InvalidQuery
from util import SNP_TABLE, slice_, get_snps

PREFIX = 'ttam_'
PREFIX_LEN = len(PREFIX)

class NoTTAMClient(Exception): pass

def acquire_client():
    g.ttam_client = TTAMClient.query.get(request.authorizer.email)


def require_client(adaptor):
    @wraps(adaptor)
    def checked(*args, **kwargs):
        if g.ttam_client is None:
            raise TTAMOAuthError
        return adaptor(*args, **kwargs)
    return checked 


def make_ttam_seq(snp, pid):
    '''
    convert 23andMe snp into a Sequence Resource
    '''
    chrom, pos = SNP_TABLE[snp['location']]
    narrative = '<div xmlns="http://www.w3.org/1999/xhtml">Genotype of %s is %s</div>'% (
            snp['location'],
            snp['call'])
    seq_data = {
        'resourceType': 'Sequence',
        'text': {
            'status': 'generated',
            'div': narrative
        },
        'genomeBuild': 'GRch37', 
        'chromosome': chrom,
        'startPosition': pos,
        'endPosition': pos,
        'observedSeq': list(snp['call']),
        'patient': {'reference': '/Patient/ttam_%s'% pid}
    }
    # we don't really care about the owner here
    # since the main purpose of using Resource class here
    # is to use its `as_repsonse` method
    seq = Resource('Sequence', seq_data, owner_id=None)
    seq.resource_id = 'ttam_%s|%s'% (snp['location'], pid)
    return seq


def make_ttam_patient(profile):
    '''
    convert a 23andme profile into a Patient Resource
    '''
    first_name = profile['first_name']
    last_name = profile['last_name']
    narrative = '<div xmlns="http://www.w3.org/1999/xhtml">%s %s</div>'% (first_name, last_name)
    patient_data = {
        'resourceType': 'Patient',
        'text': {
            'status': 'generated',
            'div': narrative
        },
        'name': [{
            'use': 'official',
            'family': [last_name],
            'given': [first_name]
         }]
    }
    patient = Resource('Patient', patient_data, owner_id=None)
    patient.resource_id = 'ttam_%s'% profile['id']
    return patient
    

def get_one_snp(internal_id):
    #23andMe Sequence id = {rsid}|{profile id}
    rsid, pid = internal_id.split('|')
    data_set = g.ttam_client.get_snps([rsid], pid)
    pid, snps = next(data_set.iteritems())
    return make_ttam_seq(snps[0], pid)


def get_one_patient(pid):
    for patient in g.ttam_client.get_patients():
        if patient['id'] == pid:
            return make_ttam_patient(patient)

def extract_coord(coord):
    args = {}
    matched = COORD_RE.match(coord)
    if matched is None:
        raise InvalidQuery
    args['chrom'] = str(matched.group('chrom'))
    args['start'] = int(matched.group('start'))
    args['end'] = int(matched.group('end'))
    return args

def parse_coords(query):
    overwrite_args = {}
    if 'chromosome' in query:
        overwrite_args['chrom'] = str(query['chromosome'])
    if 'startPosition' in query:
        overwrite_args['start'] = int(query['startPosition'])
    if 'endPosition' in query:
        overwrite_args['end'] = int(query['endPosition'])
    coords = ([dict(overwrite_args)]
            if 'coordinate' not in query or len(overwrite_args) > 0
            else map(extract_coord, query['coordinate'].split(',')))
    return coords
    

def extract_pids(query):
    extern_pids = query['patient'].split(',')
    return [pid[PREFIX_LEN:]
            for pid in extern_pids
            if pid.startswith(PREFIX)]


@require_client
def get_one(resource_type, resource_id):
    internal_id = resource_id[PREFIX_LEN:]
    if resource_type == 'Sequence':
        return get_one_snp(internal_id)
    else:
        return get_one_patient(internal_id)


@require_client
def get_many(resource_type, query, offset, limit):
    if resource_type == 'Sequence':
        limit /= g.ttam_client.count_patients()
        coords = parse_coords(query)
        snps = list(chain(*[get_snps(**coord) for coord in coords]))
        rsids, num_snps = slice_(snps, offset, limit)
        if num_snps == 0 or len(rsids) == 0:
            # here we either  find no snps
            # or we find snps but don't have to make any
            # query because of paging (i.e. limit is 0 or overly large offset)
            return [], num_snps
        pids = (extract_pids(query)
                if 'patient' in query
                else g.ttam_client.get_profiles())
        snps_data = g.ttam_client.get_snps(rsids, pids)
        seqs = []
        for pid, snps in snps_data.iteritems():
            for snp in snps:
                seqs.append(make_ttam_seq(snp, pid)) 
        return seqs, num_snps*len(pids)
    else:
        # patient
        patients = g.ttam_client.get_patients()
        patients, count = slice_(patients, offset, limit)
        return map(make_ttam_patient, patients), count

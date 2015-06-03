from os import path
from pysam import TabixFile, asTuple

SNP_FILE = path.join(path.dirname(path.abspath(__file__)), 'snps.sorted.txt.gz')

SNP_IDX = 1 
CHROM_IDX = 2
POS_IDX = 3

def get_snp_data(*args, **kwargs):
    return TabixFile(SNP_FILE, parser=asTuple()).\
            fetch(*args, **kwargs)


def slice_(xs, offset, limit):
    '''
    safe version of xs[offset:offset+limit]
    return (sliced_collection, total_count)
    '''
    num_items = len(xs)
    offset = offset if offset < num_items else num_items
    bound = offset + limit
    bound = bound if bound < num_items else num_items
    return xs[offset:bound], num_items


def get_snps(chrom=None, start=None, end=None):
    # TODO: make this deterministic
    return {row[SNP_IDX]: (row[CHROM_IDX], row[POS_IDX]) for row in get_snp_data(chrom, start, end)}


def get_coord(snp):
    for row in get_snp_data():
        _, rsid, row, pos = row
        if rsid == snp:
            return row, pos

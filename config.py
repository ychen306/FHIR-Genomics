# settings for Postgres
PGUSERNAME = 'smart'
PGPASSWORD = 'smart'
DBNAME = 'xyz'

APP_CONFIG = {
        'SQLALCHEMY_DATABASE_URI': "postgresql+psycopg2://%s:%s@localhost/%s"% (
            PGUSERNAME,
            PGPASSWORD,
            DBNAME),
        'TTAM_CONFIG': {
            'redirect_uri': 'http://localhost:5000/ttam/recv_redirect',
            'client_id': 'ae4ae237a6a8a0c7dd27112ad4db2710',
            'client_secret': '0441a01fb79e5d72f25f6f350ccffe13',
            'scope': 'basic names genomes',
            'auth_uri': 'https://api.23andme.com/authorize/'
        }
}

# Put Your host name here
HOST = 'localhost:5000'

FHIR_SPEC_DIR = '/Users/tom/workspace/fhir-spec/site'
# the example resource parser right now is still pretty slow
# also, due to the fact that SQLAlchemy is not very good at bulk insert,
# if the vcf file is too large, the example loader is gonna run for decades
MAX_SEQ_PER_FILE = 1000
# ratio between Conditions and Sequences, the example loader uses this to
# randomly create GeneticObservation, which associates the two resources.
CONDITION_TO_SEQ_RATIO = 0.3

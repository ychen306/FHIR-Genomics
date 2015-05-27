'''
Script to prepare a local postgresql instance for the server,
for more advanced usage, well, this won't help 
'''
import os
import subprocess
from config import PGUSERNAME, PGPASSWORD, DBNAME

os.environ['PGPASSWORD'] = PGPASSWORD
subprocess.call('psql -U%s -c "CREATE DATABASE %s"'% (PGUSERNAME, DBNAME), shell=True)

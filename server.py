import subprocess
from multiprocessing import cpu_count
from fhir import create_app
from config import APP_CONFIG, HOST
# use this for WSGI server
# e.g. `$ gunicorn server:app`
app = create_app(APP_CONFIG)


if __name__ == '__main__':
    num_workers = cpu_count() * 2 + 1
    subprocess.call('gunicorn -w %d -b %s -D server:app'% (num_workers, HOST), shell=True)

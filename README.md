Reference API server of SMART Genomics

## How to use it
1. Change the application settings in `config.py`, including what SQL database you would like to use.
3. Load FHIR's spec with the script `load_spec.py`
4. Get the WSGI app with
```
$ python app.py
```
or get the WSGI object with
```py
from app import create_app
# set `sync_db` to be False is you've gotten the database setup
my_app = create_app(sync_db=True)
```

Reference API server of SMART Genomics

## How to use it
1. Change the application settings in `config.py`, including what SQL database you would like to use.
3. Optional: load FHIR's spec with the script `load_spec.py`.
You don't need to do this unless you have your own FHIR spec.
4. Setup database and load sample data with
```
# note that this will also clear the database
$ python app.py reload
```
5. Run the server locally with
```
$ python app.py
```
or get the WSGI object with
```py
from app import create_app

my_app = create_app()
```

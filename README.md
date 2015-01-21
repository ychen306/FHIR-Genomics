Reference API server of SMART Genomics

## How to use it
* Change the application settings in `config.py`.
* Optional: load your version of FHIR spec with the script `load_spec.py`, which will update `fhir_spec.py`.
* Setup database and load sample data with
```
# note that this will also clear the database
$ python fhir_genomics.py reload
```
* Run the server locally with
```
$ python fhir_genomics.py
```
* The WSGI objct is located in server.py, which you can use like this
```
$ gunicorn server:app 
```

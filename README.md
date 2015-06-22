Reference API server of SMART Genomics

## How to use it
* Change the application settings in `config.py` 
(Currently we uses PostgresSQL for development, and our script `setup_db.py` is written specifically for Postgres, you can switch to SQLite by using the proper SQL connection url in `config.py`. MySQL is however not supported right now. Contributions to support MySQL are welcomed).
* Optional: load your version of FHIR spec with the script `load_spec.py`, which will update `fhir/fhir_spec.py`.
* If you haven't created the database you specified in `config.py`, simply use command below to create it
```
$ python setup_db.py
``` 
* Load sample data with
```
$ python load_example.py
```
* To run with `gunicorn` do
```
$ python server.py run
```
* Alternatively you can use `flask`'s debug instance like this
```
$ python server.py run --debug
```
* To wipe out the database (for debugging or whatever reason), do
```
$ python server.py clear
```

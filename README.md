Reference API server of SMART Genomics

## How to use it
* Change the application settings in `config.py` 
(currently the server supports SQLite3 and PostgreSQL, MySQL is however not supported because SQLAlchemy currently fails to generate correct query on complex scenario. Helps on adding support fo MySQL will be welcomed).
* Optional: load your version of FHIR spec with the script `load_spec.py`, which will update `fhir_spec.py`.
* Setup database and load sample data with
```
# note that this will also clear the database
$ python setup_db.py
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

Reference API server of SMART Genomics

## Note
URL for `assessedCondition` in `GeneticObservation` is `http://genomics.smartplatforms.org/dictionary/GeneticObservation#AssessedCondition`. If the URL doesn't match this, the server can't index the resource properly and won't be able to respond to search with parameter `assesed-condition`.

## How to use it
1. Install dependency with

	```
	# this might require previledge (e.g. sudo)
	# or use virtualenv instead
	$ pip install -r requirements.txt
	```
2. Rename `config.py.default` as `config.py` and fill in settings as you desire. See comments in `config.py.default` for detailed instructions.
Currently we use PostgresSQL for development, and our script `setup_db.py` is written specifically for Postgres, you can switch to SQLite by using the proper SQL connection url in `config.py`. MySQL is however not supported right now. Contributions to support MySQL are welcomed.
3. Optional: load your version of FHIR spec with the script `load_spec.py`, which will update `fhir/fhir_spec.py`.
4. If you haven't created the database you specified in `config.py`, simply use command below to create it
	
	```
	$ python setup_db.py
	``` 
5. Load sample data with

	```
	$ python load_example.py
	```
6. To run with `gunicorn` do

	```
	$ python server.py run
	```
7. Alternatively you can use `flask`'s debug instance like this

	```
	$ python server.py run --debug
	```
8. To wipe out the database (for debugging or whatever reason), do

	```
	$ python server.py clear
	```

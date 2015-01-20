from fhir_genomics import create_app
# use this for WSGI server
# e.g. `$ gunicorn server:app`
app = create_app()

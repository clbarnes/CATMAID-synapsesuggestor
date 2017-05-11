# CATMAID-synapsesuggestor

synapsesuggestor is a django application which acts as a drop-in
extension for CATMAID.

## Quick start

1. Install synapsesuggestor in whichever python environment is running
CATMAID with `python setup.py install`

2. Add "synapsesuggestor" to your INSTALLED_APPS setting like this:

```python
INSTALLED_APPS = [
    ...
    'synapsesuggestor',
]
```

3. Include the synapsesuggestor URLconf in your project urls.py like this:

    url(r'^synapsesuggestor/', include('synapsesuggestor.urls')),

4. Run `python manage.py migrate` to create the synapsesuggestor models.

5. Run `python manage.py collectstatic -l` to pick up the
synapsesuggestor's static files.

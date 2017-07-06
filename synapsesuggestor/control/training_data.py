from __future__ import division
import random
import sys

from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view

from catmaid.control.common import get_request_list
from catmaid.models import Relation


def sample_treenodes(request, project_id):
    """
    Return a list of treenode IDs and their locations randomly sampled from the entire project.
    """
    # todo: test
    seed = int(request.GET.get('seed', random.randint(0, sys.maxsize)))
    count = int(request.GET.get('count', 50))

    cursor = connection.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM treenode tn WHERE tn.project_id = %s;
    ''', (project_id, ))
    total = cursor.fetchone()[0]

    assert count < total, \
        'Too many ({}) treenodes requested, only {} exist in project {}'.format(count, total, project_id)

    # Do most of the cutting down in SQL, but this doesn't guarantee the number of returned items, so get a larger
    # sample than required, then pare it down further in python
    leeway_factor = 3
    cursor.execute('''
        SELECT tn2.id, tn2.location_x, tn2.location_y, tn2.location_z FROM (
            SELECT * FROM treenode tn1
              WHERE tn1.project_id = %s
          ) tn2
          TABLESAMPLE BERNOULLI (%s)
            REPEATABLE (%s);
    ''', (project_id, min((count*leeway_factor*100)/total, 100), seed))

    rows = cursor.fetchall()
    sampler = random.Random(seed)
    sample = sampler.sample(rows, count)

    return JsonResponse({
        'seed': seed,
        'columns': ['treenode_id', 'xp', 'yp', 'zp'],
        'data': sample
    })


@api_view(['GET'])
def treenodes_by_label(request, project_id=None):
    """Return all treenodes in the project associated with the given tags.
    ---
    parameters:
        - name: tags
          description: label names to find treenodes associated with
          required: true
          type: array
          items:
            type: str
          paramType: form
    """
    # todo: test
    labels = get_request_list(request.GET, 'tags', tuple())
    columns = ['tag_name', 'treenode_id', 'xp', 'yp', 'zp']

    if not labels:
        return JsonResponse({'columns': columns, 'data': []})

    labeled_as_relation = Relation.objects.get(project=project_id, relation_name='labeled_as')

    cursor = connection.cursor()
    cursor.execute("""
        SELECT ci.name, t.id, t.location_x, t.location_y, t.location_z
          FROM class_instance ci
          JOIN treenode_class_instance tci
            ON tci.class_instance_id = ci.id
          JOIN treenode t
            ON tci.treenode_id = t.id
          WHERE ci.project_id = %s
            AND tci.relation_id = %s
            AND ci.name = ANY(%s)
          GROUP BY ci.name;
    """, (project_id, labeled_as_relation.id, labels))

    return JsonResponse({'columns': columns, 'data': cursor.fetchall()})

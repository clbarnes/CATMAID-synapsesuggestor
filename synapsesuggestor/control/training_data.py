from __future__ import division
import random
import sys

from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view

from catmaid.control.common import get_request_list, get_relation_to_id_map
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
        SELECT id, location_x, location_y, location_z FROM treenode WHERE project_id = %s;
    ''', (project_id))
    rows = cursor.fetchall()

    sampler = random.Random(seed)
    sample = sampler.sample(rows, min(count, len(rows)))

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
            AND ci.name = ANY(%s);
    """, (project_id, labeled_as_relation.id, labels))

    return JsonResponse({'columns': columns, 'data': cursor.fetchall()})


@api_view(['GET'])
def synapse_convex_hull(request, project_id=None):
    """
    Return a geoJSON polygon per z slice with the convex hull of all
    treenodes associated with synaptic connectors, in project space.

    Returns an array of (location_z, geojson_str) pairs
    """
    shrink_volume = request.GET.get("shrink_volume", 1)

    cursor = connection.cursor()
    relations = get_relation_to_id_map(project_id, cursor=cursor)

    syn_ids = [relations.get('synaptic_to'.format(side), -1) for side in ('pre', 'post')]

    cursor.execute("""
        SELECT subq.z, st_asgeojson(st_concavehull(st_collect(subq.geom), %(shrink_volume)s))
        FROM (
            SELECT st_makepoint(tn.location_x, tn.location_y, tn.location_z), tn.location_z
              FROM treenode tn
              JOIN treenode_connector tn_c
                ON tn_c.treenode_id = tn.id
              JOIN relation r
                ON tn_c.relation_id = r.id
              WHERE r.relation_name = ANY(ARRAY['presynaptic_to', 'postsynaptic_to'])
                AND tn.project_id = %(pid)s
        ) AS subq (geom, z)
        GROUP BY subq.z;
    """, {"shrink_volume": shrink_volume, "syn_ids": syn_ids, "pid": project_id})

    return JsonResponse(cursor.fetchall(), safe=False)

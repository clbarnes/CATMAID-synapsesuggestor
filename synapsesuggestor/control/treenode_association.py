# -*- coding: utf-8 -*-
"""
Methods used by the skeleton-node association code
"""
import json
import logging

from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view

from catmaid.control.authentication import requires_user_role
from catmaid.control.common import get_request_list
from synapsesuggestor.models import ProjectSynapseSuggestionWorkflow
from synapsesuggestor.control.common import list_into_query, get_most_recent_project_SS_workflow, \
    get_project_SS_workflow, get_translation_resolution


logger = logging.getLogger(__name__)

@api_view(['POST'])
def add_treenode_synapse_associations(request, project_id=None):
    """
    POST request which adds a set of treenode-synapse associations to the database.
    ---
    parameters:
      - name: project_workflow_id
        type: integer
        required: false
        description: ID of project synapse suggestion workflow
      - name: associations
        type: array
        items:
          type: array
          items:
            type: integer
        required: false
        description:> Array of JSON-encoded arrays of length 3, whose items are a synapse slice ID, treenode ID and
          contact area estimation
    """
    # todo: add null -> tn.id association if no synapses are found
    # todo: should take SSW and figure out PSSW itself
    # todo: add return type

    pssw_id = int(request.POST.get(
        'project_workflow_id', get_most_recent_project_SS_workflow(project_id).id
    ))
    associations = get_request_list(request.POST, 'associations', tuple(), json.loads)

    if not associations:
        return JsonResponse([], safe=False)

    rows = [(syn, treenode, contact_px, pssw_id) for syn, treenode, contact_px in associations]

    query, cursor_args = list_into_query('''
        INSERT INTO synapse_slice_treenode (
          synapse_slice_id, treenode_id, contact_px, project_synapse_suggestion_workflow_id
        )
        VALUES {}
        RETURNING id;
    ''', rows, fmt='(%s, %s, %s, %s)')

    cursor = connection.cursor()
    cursor.execute(query, cursor_args)

    return JsonResponse(cursor.fetchall(), safe=False)


@api_view(['GET'])
def get_treenode_associations(request, project_id=None):
    """
    GET request which takes a skeleton ID and returns its treenode associations with synapse objects under the synapse
    suggestion workflow most recently associated with this project.
    ---
    parameters:
      - name: skid
        type: integer
        required: true
        description: Skeleton ID for which to get synapses
      - name: project_workflow_id
        type: integer
        required: false
    """
    # todo: take set of nodes instead
    # todo: improve error handling

    skel_id = int(request.GET['skid'])
    pssw_id = int(request.GET.get(
        'project_workflow_id', get_most_recent_project_SS_workflow(project_id).id
    ))

    cursor = connection.cursor()

    cursor.execute('''
        SELECT sstn.treenode_id, ssso.synapse_object_id, sum(sstn.contact_px) FROM synapse_slice_treenode sstn
          INNER JOIN project_synapse_suggestion_workflow pssw
            ON sstn.project_synapse_suggestion_workflow_id = pssw.id
          INNER JOIN synapse_slice_synapse_object ssso
            ON sstn.synapse_slice_id = ssso.synapse_slice_id
          INNER JOIN treenode tn
            ON sstn.treenode_id = tn.id
          WHERE tn.skeleton_id = %s
            AND pssw.id = %s
          GROUP BY sstn.treenode_id, ssso.synapse_object_id;
    ''', (skel_id, pssw_id))

    return JsonResponse(cursor.fetchall(), safe=False)


@api_view(['GET'])
def get_synapse_slices_near_skeletons(request, project_id=None):
    """
    Find synapse slices which are within a given distance of a particular skeleton.

    Returns {columns: [...], data: [[...], ...]}

    synapse bounds are in stack coordinates

    XY bounds are given in [xmin, ymin, xmax, ymax] order
    ---
    parameters:
      - name: skid
        type: integer
        required: true
        description: Skeleton ID for which to get synapses
      - name: project_workflow_id
        type: integer
        required: false
      - name: distance
        type: float
        required: false
        description: distance, in nm, within which to find synapses
    """
    skel_id = int(request.GET['skid'])
    pssw_id = int(request.GET.get('project_workflow_id', get_most_recent_project_SS_workflow(project_id).id))
    distance = float(request.GET.get('distance', 0))
    dimensions = 2  # int(request.GET.get('dimensions', 2))

    cursor = connection.cursor()

    ssw_id = ProjectSynapseSuggestionWorkflow.objects.get(id=pssw_id).synapse_suggestion_workflow_id

    translation, resolution = get_translation_resolution(project_id, ssw_id, cursor)
    offset_xs, offset_ys, offset_zs = translation / resolution

    columns = ['skeleton_id', 'treenode_id', 'synapse_object_id', 'synapse_slice_ids', 'synapse_z_s',
               'synapse_bounds_s']

    if dimensions == 2:

        cursor.execute('''
            SELECT tn.skeleton_id, tn.id, ss_so2.synapse_object_id, array_agg(DISTINCT ss2.id), 
              tile2.z_tile_idx, ARRAY[
                ST_XMin(ST_Extent(ss2.convex_hull_2d)),
                ST_YMin(ST_Extent(ss2.convex_hull_2d)),
                ST_XMax(ST_Extent(ss2.convex_hull_2d)),
                ST_YMax(ST_Extent(ss2.convex_hull_2d))
              ]
            FROM synapse_slice ss1
            INNER JOIN synapse_detection_tile tile1
              ON ss1.synapse_detection_tile_id = tile1.id
            INNER JOIN treenode tn
              ON tile1.z_tile_idx = (tn.location_z / %s) - %s
              AND ST_DWithin(
                    ST_MakePoint((tn.location_x / %s) - %s, (tn.location_y / %s) - %s),
                    ss1.convex_hull_2d, 
                    (%s / %s) - %s
                )
            INNER JOIN synapse_slice_synapse_object ss_so1
              ON ss_so1.synapse_slice_id = ss1.id
            INNER JOIN synapse_slice_synapse_object ss_so2
              ON ss_so1.synapse_object_id = ss_so2.synapse_object_id
            INNER JOIN synapse_slice ss2
              ON ss_so2.synapse_slice_id = ss2.id
            INNER JOIN synapse_detection_tile tile2
              ON ss2.synapse_detection_tile_id = tile2.id
            WHERE tn.skeleton_id = %s
              AND tn.project_id = %s
              AND tile1.synapse_suggestion_workflow_id = %s
            GROUP BY ss_so2.synapse_object_id, tn.skeleton_id, tn.id, tile2.z_tile_idx;
        ''', (
                resolution[2], offset_zs,
                resolution[0], offset_xs, resolution[1], offset_ys,
                distance, resolution[0], offset_xs,  # assumes xy isotropy
                skel_id, project_id, ssw_id
            )
        )

        data = cursor.fetchall()
    elif dimensions == 3:
        raise NotImplementedError('Synapse slices near skeletons is only implemented for 2D search')
    else:
        raise ValueError('`dimensions` must be 2 or 3')

    return JsonResponse({'columns': columns, 'data': data})

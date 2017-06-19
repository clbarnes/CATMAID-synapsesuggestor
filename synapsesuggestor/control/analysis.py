# -*- coding: utf-8 -*-
"""
Methods called by the frontend analysis widget
"""

from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view

from catmaid.control.common import get_request_list


@api_view(['GET'])
def get_synapse_slice_details(request, project_id=None):
    """
    Get the details of synapse slices detected in the given workflow ID associated with the given skeleton IDs.

    Returns an object with two properties: array of arrays whose items are:

    synapse slice ID
    synapse object ID to which the synapse slice belongs
    treenode ID with which the synapse slice is associated
    skeleton ID to which the treenode belongs
    x coordinate, in stack space, of the synapse slice centroid
    y coordinate, in stack space, of the synapse slice centroid
    z coordinate/ slice index of the synapse slice
    area, in pixels, of the synapse slice
    uncertainty of the synapse slice detection

    Note that slice IDs are not unique, as an object will be returned for each synapse slice
    ---
    parameters:
      - name: workflow_id
        description: ID of synapse suggestion workflow through which synapse slices were detected
        type: integer
        required: true
        paramType: form
      - name: skeleton_ids
        description: Skeletons to get synapse slices associated with
        type: array
        items:
          type: integer
        paramType: form
        required: false
    type:
      columns:
        type: array
        items:
          type: string
        description: headers for columns in data array
        required: true
      data:
        type: array
        items:
          type: array
        description: > array of arrays, each row of which contains data about a single synapse slice - treenode
        interaction. Note that slice IDs are not unique for this reason.
        required: true
    """

    ssw_id = request.GET['workflow_id']
    skids = get_request_list(request.GET, 'skeleton_ids', tuple(), int)

    #syn slice id, node id, skel id, syn obj id, size_px, uncertainty, x, y, z

    cursor = connection.cursor()
    cursor.execute('''
        SELECT ss.id, ss_so.synapse_object_id, tn.id, tn.skeleton_id, ss.xs_centroid, ss.ys_centroid, tile.z_tile_idx, 
        ss.size_px, ss.uncertainty
          FROM synapse_slice ss
            INNER JOIN synapse_slice_synapse_object ss_so
              ON ss_so.synapse_slice_id = ss.id
            INNER JOIN synapse_slice_treenode ss_tn
              ON ss_tn.synapse_slice_id = ss.id
            INNER JOIN treenode tn
              ON tn.id = ss_tn.treenode_id
            INNER JOIN synapse_detection_tile tile
              ON ss.synapse_detection_tile_id = tile.id
            INNER JOIN synapse_suggestion_workflow ssw
              ON tile.synapse_suggestion_workflow_id = ssw.id
          WHERE tn.project_id = %s
            AND ssw.id = %s
            AND tn.skeleton_id = ANY(%s);
    ''', (project_id, ssw_id, skids))

    columns = ['slice', 'object', 'node', 'skeleton', 'xs', 'ys', 'zs', 'size', 'uncertainty']
    return JsonResponse({'columns': columns, 'data': cursor.fetchall()})

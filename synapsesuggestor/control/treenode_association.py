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
from synapsesuggestor.control.common import list_into_query, get_most_recent_project_SS_workflow


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

    # todo: assert that slices are associated with the correct workflow
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

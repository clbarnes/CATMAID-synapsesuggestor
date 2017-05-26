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


def add_treenode_synapse_associations(request, project_id=None):
    """
    POST request which adds a set of treenode-synapse associations to the database.
    
    Parameters
    ----------
    request
    project_id

    Returns
    -------

    """
    # todo: add null -> tn.id association if no synapses are found

    algo_version = request.POST['algo_version']
    associations = get_request_list(request.POST, 'associations', tuple(), json.loads)

    if not associations:
        return

    rows = [(syn, treenode, algo_version, contact_px) for syn, treenode, contact_px in associations]

    query, cursor_args = list_into_query('''
        INSERT INTO synapse_slice_treenode (
          synapse_slice_id, treenode_id, skeleton_association_algorithm_id, contact_px
        )
        VALUES {};
    ''', rows, fmt='(%s, %s, %s, %s)')

    cursor = connection.cursor()
    cursor.execute(query, cursor_args)


def get_treenode_associations(request, project_id=None):
    """
    GET request which takes a skeleton ID and returns its treenode associations with synapses under the synapse 
    suggestion workflow most recently associated with this project.
    
    skid
    
    Parameters
    ----------
    request
    project_id

    Returns
    -------

    """
    skel_id = int(request.GET['skid', 0])

    newest_pssw_id = get_most_recent_project_SS_workflow(project_id).id

    cursor = connection.cursor()

    cursor.execute('''
        SELECT DISTINCT sstn.treenode_id, sstn.synapse_slice_id FROM synapse_slice_treenode sstn
          INNER JOIN synapse_association_algorithm saa
            ON sstn.synapse_association_algorithm_id = saa.id
          INNER JOIN treenode tn
            ON sstn.treenode_id = tn.id
          INNER JOIN project_synapse_suggestion_workflow pssw
            ON pssw.synapse_association_algorithm_id = saa.id
          WHERE tn.skeleton_id = %s
            AND pssw.id = %s;
    ''', (skel_id, newest_pssw_id))

    # todo: allow user to choose from different PSSWs, or default to most recent in project

    return JsonResponse(cursor.fetchall(), safe=False)
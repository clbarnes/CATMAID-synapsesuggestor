"""
Methods used by the skeleton-node association code
"""
import json
import logging

from django.db import connection
from rest_framework.decorators import api_view

from catmaid.control.authentication import requires_user_role
from catmaid.control.common import get_request_list
from synapsesuggestor.control.common import list_into_query


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

# -*- coding: utf-8 -*-
"""
Methods called by the frontend analysis widget
"""

from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view

from catmaid.control.common import get_request_list


def get_synapse_object_details(request, project_id=None):
    """

    Parameters
    ----------
    request
    project_id

    Returns
    -------

    """

    ssw_id = request.GET['workflow_id']
    skids = get_request_list(request.GET, 'skids', tuple(), int)

    '''SELECT '''

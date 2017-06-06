# -*- coding: utf-8 -*-
"""
Methods used by the skeleton-node association code
"""

from django.http import JsonResponse
from django.db import transaction
from rest_framework.decorators import api_view

from catmaid.control.authentication import requires_user_role
from synapsesuggestor.models import (
    SynapseSuggestionWorkflow, ProjectSynapseSuggestionWorkflow, SynapseDetectionAlgorithm,
    SynapseAssociationAlgorithm, SynapseDetectionTiling
)


def get_workflow(request, project_id=None):
    """
    Get or create all of the models required to establish a workflow.

    Parameters
    ----------
    request
    project_id

    Returns
    -------

    """
    stack_id = int(request.GET['stack_id'])
    tile_size = int(request.GET.get('tile_size', 512))
    detection_hash = request.GET['detection_hash']

    tiling = SynapseDetectionTiling.objects.get_or_create(
        stack_id=stack_id, tile_height_px=tile_size, tile_width_px=tile_size
    )[0]
    detection_algorithm = SynapseDetectionAlgorithm.objects.get_or_create(hashcode=detection_hash)[0]
    # todo: deal with image store
    workflow = SynapseSuggestionWorkflow.objects.get_or_create(
        synapse_detection_tiling=tiling, synapse_detection_algorithm=detection_algorithm
    )[0]

    return JsonResponse({
        'tile_size': {'height_px': tiling.tile_height_px, 'width_px': tiling.tile_width_px},
        'workflow_id': workflow.id,
        'detection_algorithm_id': detection_algorithm.id
    })


def get_project_workflow(request, project_id=None):
    """

    Parameters
    ----------
    request
    project_id

    Returns
    -------

    """
    workflow_id = int(request.GET['workflow_id'])
    association_hash = request.GET['association_hash']

    association_algorithm = SynapseAssociationAlgorithm.objects.get_or_create(hashcode=association_hash)[0]
    project_workflow = ProjectSynapseSuggestionWorkflow.objects.get_or_create(
        synapse_suggestion_workflow_id=workflow_id, project_id=project_id,
        synapse_association_algorithm=association_algorithm
    )[0]

    return JsonResponse({
        'association_algorithm_id': association_algorithm.id,
        'project_workflow_id': project_workflow.id
    })

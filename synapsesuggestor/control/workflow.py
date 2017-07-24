# -*- coding: utf-8 -*-
"""
Methods used by the skeleton-node association code
"""

from django.http import JsonResponse
from django.db import connection
from rest_framework.decorators import api_view

from catmaid.control.authentication import requires_user_role
from synapsesuggestor.models import (
    SynapseSuggestionWorkflow, ProjectSynapseSuggestionWorkflow, SynapseDetectionAlgorithm,
    SynapseAssociationAlgorithm, SynapseDetectionTiling
)


@api_view(['GET'])
def get_workflow(request, project_id=None):
    """
    Get or create all of the models required to establish a workflow.
    """
    stack_id = int(request.GET['stack_id'])
    tile_size = request.GET.get('tile_size')
    detection_hash = request.GET.get('detection_hash')

    tiling = SynapseDetectionTiling.objects.get_or_create(
        stack_id=stack_id, tile_height_px=int(tile_size) if tile_size else 512, tile_width_px=int(tile_size)
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


@api_view(['GET'])
def get_project_workflow(request, project_id=None):
    """
    Get or create all of the models required to establish a project workflow.
    """
    workflow_id = request.GET.get('workflow_id')
    association_hash = request.GET.get('association_hash')

    association_algorithm = SynapseAssociationAlgorithm.objects.get_or_create(hashcode=association_hash)[0]
    project_workflow = ProjectSynapseSuggestionWorkflow.objects.get_or_create(
        synapse_suggestion_workflow_id=workflow_id, project_id=project_id,
        synapse_association_algorithm=association_algorithm
    )[0]

    return JsonResponse({
        'association_algorithm_id': association_algorithm.id,
        'project_workflow_id': project_workflow.id
    })


@api_view(['GET'])
def get_workflow_info(request, project_id=None):
    stack_id = int(request.GET['stack_id'])

    workflows_info = _get_valid_workflows(project_id, stack_id)

    return JsonResponse({'workflows': workflows_info})


def _get_valid_workflows(project_id, stack_id):
    columns = [
        'workflow_id', 'detection_algo_id', 'detection_algo_hash', 'detection_algo_date',
        'detection_algo_notes',
        'project_workflow_id', 'association_algo_id', 'association_algo_hash', 'association_algo_date',
        'association_algo_notes',
        'tile_height_px', 'tile_width_px'
    ]

    cursor = connection.cursor()

    cursor.execute('''
        SELECT DISTINCT
          ssw.id, sda.id, sda.hashcode, sda.date, sda.notes,
          pssw.id, saa.id, saa.hashcode, saa.date, saa.notes,
          tiling.tile_height_px, tiling.tile_width_px
          FROM project_synapse_suggestion_workflow pssw
          INNER JOIN synapse_association_algorithm saa
            ON pssw.synapse_association_algorithm_id = saa.id
          INNER JOIN synapse_suggestion_workflow ssw
            ON pssw.synapse_suggestion_workflow_id = ssw.id
          INNER JOIN synapse_detection_algorithm sda
            ON ssw.synapse_detection_algorithm_id = sda.id
          INNER JOIN synapse_detection_tiling tiling
            ON ssw.synapse_detection_tiling_id = tiling.id
          INNER JOIN stack
            ON tiling.stack_id = stack.id
          WHERE pssw.project_id = %s
            AND tiling.stack_id = %s
          ORDER BY sda.date DESC, saa.date DESC;
    ''', (project_id, stack_id))

    output = []
    for row in cursor.fetchall():
        output.append(dict(zip(columns, row)))

    return output


@api_view(['GET'])
def get_valid_algorithms(project_id, stack_id):
    # todo: test

    info = _get_valid_workflows(project_id, stack_id)

    detection_algos = set()
    association_algos = set()
    valid_pairs = set()

    for row in info:
        detection_algos.add((row['detection_algo_hash'], row['detection_algo_date'], row['detection_algo_notes']))
        association_algos.add((row['association_algo_hash'], row['association_algo_date'], row['association_algo_notes']))
        valid_pairs.add((row['detection_algo_hash'], row['association_algo_hash']))

    return JsonResponse({
        'detection_algos': [
            {'hashcode': hashcode, 'created': created, 'notes': notes}
            for hashcode, created, notes in sorted(detection_algos, key=lambda x: x[1], reverse=True)
        ],
        'association_algos': [
            {'hashcode': hashcode, 'created': created, 'notes': notes}
            for hashcode, created, notes in sorted(association_algos, key=lambda x: x[1], reverse=True)
        ],
        'detection_association_pairs': list(valid_pairs)
    })

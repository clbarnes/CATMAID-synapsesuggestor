# -*- coding: utf-8 -*-
"""
Methods called by the frontend analysis widget
"""
from __future__ import division
import numpy as np

from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view

from catmaid.control.common import get_request_list

from synapsesuggestor.control.common import get_most_recent_project_SS_workflow
from synapsesuggestor.models import ProjectSynapseSuggestionWorkflow, SynapseSuggestionWorkflow


@api_view(['GET'])
def get_skeleton_synapses(request, project_id=None):
    """
    Get the details of synapse slices detected in the given workflow ID associated with the given skeleton IDs.

    Returns an object with two properties: array of arrays whose items are:

    synapse object ID
    array of treenode IDs on the given skeleton with which the synapse object is associated
    skeleton ID
    x coordinate, in stack space, of the synapse object centroid
    y coordinate, in stack space, of the synapse object centroid
    z coordinate/ slice index of the synapse object centroid
    array of z slices in which the synapse object exists (may contain duplicates)
    size, in pixels, of the synapse object (sum of its slices)
    contact area, in pixels, of the synapse object's interactions with the skeleton
    average uncertainty of the synapse slice detection

    ---
    parameters:
      - name: workflow_id
        description: ID of synapse suggestion workflow through which synapse slices were detected
        type: integer
        required: false
        paramType: form
      - name: skeleton_id
        description: Skeleton to get synapse slices associated with
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
        description: > array of arrays, each row of which contains data about a single synapse object and its
          interaction with the given skeleton
        required: true
    """

    # todo: weight averages by slice size

    columns = [
        'synapse', 'nodes', 'skeleton_id',
        'xs', 'ys', 'zs', 'z_slices',
        'size_px', 'contact_px', 'uncertainty_avg'
    ]
    skid = request.GET.get('skeleton_id')
    if skid is None:
        return JsonResponse({'columns': columns, 'data': []})

    ssw_id = request.GET.get('workflow_id')

    if ssw_id is None:
        pssw = get_most_recent_project_SS_workflow(project_id)
    else:
        pssw = ProjectSynapseSuggestionWorkflow.objects.get(synapse_suggestion_workflow_id=ssw_id, project_id=project_id)

    cursor = connection.cursor()

    # todo: why is this casting necessary? unit tests produced strings
    cursor.execute('''
        SELECT 
            ss_so_synapse_object_id, array_agg(tn_id), tn_skeleton_id,
            cast(round(avg(that_ss_xs_centroid)) as int), cast(round(avg(that_ss_ys_centroid)) as int), 
            cast(round(avg(tile_z_tile_idx)) as int), array_agg(tile_z_tile_idx),
            sum(that_ss_size_px), sum(ss_tn_contact_px), avg(that_ss_uncertainty)
        FROM (
            SELECT DISTINCT ON (that_ss.id) 
              ss_so.synapse_object_id, tn.id, tn.skeleton_id,
              that_ss.xs_centroid, that_ss.ys_centroid, tile.z_tile_idx,
              that_ss.size_px, ss_tn.contact_px, that_ss.uncertainty
            FROM treenode tn
              INNER JOIN synapse_slice_treenode ss_tn
                ON tn.id = ss_tn.treenode_id 
              INNER JOIN synapse_slice this_ss
                ON ss_tn.synapse_slice_id = this_ss.id
              INNER JOIN synapse_slice_synapse_object ss_so
                ON this_ss.id = ss_so.synapse_slice_id
              INNER JOIN synapse_slice that_ss
                ON ss_so.synapse_slice_id = that_ss.id
              INNER JOIN synapse_detection_tile tile
                ON that_ss.synapse_detection_tile_id = tile.id
            WHERE tn.skeleton_id = %s
              AND ss_tn.project_synapse_suggestion_workflow_id = %s
        ) as rows (
          ss_so_synapse_object_id, tn_id, tn_skeleton_id,
          that_ss_xs_centroid, that_ss_ys_centroid, tile_z_tile_idx,
          that_ss_size_px, ss_tn_contact_px, that_ss_uncertainty
        )
        GROUP BY ss_so_synapse_object_id, tn_skeleton_id;
    ''', (skid, pssw.id))

    return JsonResponse({'columns': columns, 'data': cursor.fetchall()})


def _get_translation_resolution(project_id, ssw_id, cursor=None):
    """
    Return the translation and resolution for converting between stack and project coordinates.

    Args:
      project_id(int):
      ssw_id(int): Synapse suggestion workflow ID
      cursor(django.db.connection.cursor, optional):  (Default value = None)

    Returns:
      tuple:  (numpy.ndarray, numpy.ndarray)
        Translation is the location of the stack origin, in project space
        Resolution is the size of a stack pixel, in project space
    """
    if cursor is None:
        cursor = connection.cursor()

    cursor.execute('''
        SELECT 
          (ps.translation).x, (ps.translation).y, (ps.translation).z, 
          (stack.resolution).x, (stack.resolution).y, (stack.resolution).z  
        FROM synapse_suggestion_workflow ssw
          INNER JOIN synapse_detection_tiling tiling
            ON ssw.synapse_detection_tiling_id = tiling.id
          INNER JOIN stack
            ON tiling.stack_id = stack.id
          INNER JOIN project_stack ps
            ON ps.stack_id = stack.id
          WHERE ps.project_id = %s
            AND ssw.id = %s
          LIMIT 1;
    ''', (project_id, ssw_id))

    trans_res = cursor.fetchone()

    return np.array(trans_res[:3]), np.array(trans_res[-3:])


@api_view(['POST'])
def get_intersecting_connectors(request, project_id=None):
    """
    Given a set of synapse objects, return information connectors and treenodes they may be associated with.
    ---
    parameters:
      - name: workflow_id
        description: ID of synapse suggestion workflow through which synapse slices were detected
        type: integer
        required: false
        paramType: form
      - name: synapse_object_ids
        description: Synapse objects to find information about
        type: array
        items:
            type: integer
        paramType: form
        required: false
      - name: tolerance
        description: > minimum XY distance, in project space, used to determine whether a connector edge is associated
          with a synapse slice. Default 0 (geometric intersection).
        type: float
        required: false
        paramType: form
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
        description: > array of arrays, each row of which contains data about a single synapse object-connector edge
        intersection
        required: true
    """

    columns = [
        'synapse_id', 'connector_id',
        'connector_x', 'connector_y', 'connector_z',
        'connector_confidence', 'connector_creator',
        'relation_name', 'edge_confidence',
        'treenode_id', 'treenode_x', 'treenode_y', 'treenode_z',
        'skeleton_id'
    ]

    tolerance = int(request.POST.get('tolerance', 0))

    obj_ids = get_request_list(request.POST, 'synapse_object_ids', tuple(), int)
    if not obj_ids:
        return JsonResponse({'columns': columns, 'data': []})

    ssw_id = request.POST.get('workflow_id')
    if ssw_id is None:
        ssw_id = get_most_recent_project_SS_workflow(project_id).synapse_suggestion_workflow_id

    cursor = connection.cursor()

    translation, resolution = _get_translation_resolution(project_id, ssw_id, cursor)

    offset_xs, offset_ys, offset_zs = translation / resolution

    cursor.execute('''
      SELECT obj_edge.obj_id,
        c.id, c.location_x, c.location_y, c.location_z, c.confidence, c.user_id,
        relation.relation_name, tc.confidence,
        tn.id, tn.location_x, tn.location_y, tn.location_z, 
        tn.skeleton_id
      FROM (
        SELECT DISTINCT ss_so.synapse_object_id, tce.id
          FROM synapse_slice_synapse_object ss_so
          INNER JOIN synapse_slice ss
            ON ss_so.synapse_slice_id = ss.id
          INNER JOIN synapse_detection_tile tile
            ON ss.synapse_detection_tile_id = tile.id
          INNER JOIN treenode_connector_edge tce
            ON (tile.z_tile_idx + %s) * %s BETWEEN ST_ZMin(tce.edge) AND ST_ZMax(tce.edge)
            AND ST_DWithin(tce.edge, ST_TransScale(ss.convex_hull_2d, %s, %s, %s, %s), %s)
          WHERE ss_so.synapse_object_id = ANY(%s::bigint[])
            AND tce.project_id = %s
      ) as obj_edge (obj_id, tce_id)
      INNER JOIN treenode_connector tc
        ON tc.id = obj_edge.tce_id
      INNER JOIN relation
        ON tc.relation_id = relation.id
      INNER JOIN connector c
        ON c.id = tc.connector_id
      INNER JOIN treenode tn
        ON tc.treenode_id = tn.id
      WHERE relation.relation_name = ANY(ARRAY['presynaptic_to', 'postsynaptic_to']);
    ''', (
        offset_zs, resolution[2],
        offset_xs, offset_ys, resolution[0], resolution[1], tolerance,
        obj_ids, project_id
    ))

    return JsonResponse({'columns': columns, 'data': cursor.fetchall()})

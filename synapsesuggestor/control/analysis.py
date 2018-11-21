# -*- coding: utf-8 -*-
"""
Methods called by the frontend analysis widget
"""
from __future__ import division

from collections import Counter

from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view

from catmaid.control.common import get_request_list

from synapsesuggestor.control.common import get_most_recent_project_SS_workflow, get_translation_resolution, \
    get_project_SS_workflow


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

    pssw = get_project_SS_workflow(project_id, request.GET.get('workflow_id'))

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


@api_view(['POST'])
def get_intersecting_connectors(request, project_id=None):
    """
    Given a set of synapse objects, return information connectors and treenodes they may be associated with.

    1 row per synapse object - connector intersection.
    treenode_ids: array of treenodes which have edges to the connector
    skeleton_ids: array of skeletons to which those treenodes belong
    distance: shortest 2D distance from the synapse object to one of the edges associated with the connector

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
      - name: mode
        description: > 'edge' or 'node': whether to look for intersection with the connector node itself, or
          treenode-connector edges associated with the connector
        type: string
        required: false
        paramType: form
      - name: tolerance
        description: > minimum XY distance, in project space, used to determine whether a geometry is associated
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
        'synapse_object_id',
        'connector_id', 'connector_x', 'connector_y', 'connector_z', 'connector_confidence', 'connector_creator',
        'skeleton_ids', 'treenode_ids', 'distance'
    ]

    mode = request.POST.get('mode', 'edge')

    tolerance = float(request.POST.get('tolerance', 0))

    obj_ids = get_request_list(request.POST, 'synapse_object_ids', tuple(), int)
    if not obj_ids:
        return JsonResponse({'columns': columns, 'data': []})

    ssw_id = request.POST.get('workflow_id')
    if ssw_id is None:
        ssw_id = get_most_recent_project_SS_workflow(project_id).synapse_suggestion_workflow_id

    cursor = connection.cursor()

    translation, resolution = get_translation_resolution(project_id, ssw_id, cursor)

    offset_xs, offset_ys, offset_zs = translation / resolution

    params = {
        'obj_ids': obj_ids,
        'offset_xs': offset_xs,
        'offset_ys': offset_ys,
        'offset_zs': offset_zs,
        'resolution_x': resolution[0],
        'resolution_y': resolution[1],
        'resolution_z': resolution[2],
        'tolerance': tolerance,
        'project_id': project_id
    }

    modes = {
        'edge': _get_intersecting_connectors_edge,
        'node': _get_intersecting_connectors_node,
        # 'box': _get_intersecting_connectors_box  # todo?
    }

    data = modes[mode](cursor, **params)

    return JsonResponse({'columns': columns, 'data': data})


def _get_intersecting_connectors_edge(cursor=None, **kwargs):
    cursor = cursor or connection.cursor()

    cursor.execute('''
          SELECT subq.syn_id, subq.c_id, subq.c_x, subq.c_y, subq.c_z, subq.c_conf, subq.c_user,
            array_agg(tn.skeleton_id), array_agg(tn.id), subq.min_dist
          FROM (
            SELECT
              ss_so.synapse_object_id,
              c.id, c.location_x, c.location_y, c.location_z, c.confidence, c.user_id,
              min(ST_Distance(tce.edge, ss_trans.geom_2d))
            FROM synapse_slice_synapse_object ss_so
            INNER JOIN unnest(%(obj_ids)s::BIGINT[]) AS syns (id)
              ON ss_so.synapse_object_id = syns.id
            INNER JOIN (
              SELECT ss.id, ss.synapse_detection_tile_id, ST_TransScale(
                ss.geom_2d, %(offset_xs)s, %(offset_ys)s, %(resolution_x)s, %(resolution_y)s
              )
                FROM synapse_slice ss
            ) AS ss_trans (id, synapse_detection_tile_id, geom_2d)
              ON ss_trans.id = ss_so.synapse_slice_id
            INNER JOIN synapse_detection_tile tile
              ON ss_trans.synapse_detection_tile_id = tile.id
            INNER JOIN treenode_connector_edge tce
              ON (tile.z_tile_idx + %(offset_zs)s) * %(resolution_z)s BETWEEN ST_ZMin(tce.edge) AND ST_ZMax(tce.edge)
              AND ST_DWithin(tce.edge, ss_trans.geom_2d, %(tolerance)s)
            INNER JOIN treenode_connector tc
              ON tc.id = tce.id
            INNER JOIN relation
              ON tc.relation_id = relation.id
            INNER JOIN connector c
              ON c.id = tc.connector_id
            WHERE tce.project_id = %(project_id)s
              AND relation.relation_name = ANY(ARRAY['presynaptic_to', 'postsynaptic_to'])
            GROUP BY ss_so.synapse_object_id, c.id
          ) AS subq (syn_id, c_id, c_x, c_y, c_z, c_conf, c_user, min_dist)
          INNER JOIN treenode_connector tc2
            ON tc2.connector_id = subq.c_id
          INNER JOIN treenode tn
            ON tc2.treenode_id = tn.id
          GROUP BY subq.syn_id, subq.c_id, subq.c_x, subq.c_y, subq.c_z, subq.c_conf, subq.c_user, subq.min_dist;
        ''', kwargs)

    return cursor.fetchall()


def _get_intersecting_connectors_node(cursor=None, **kwargs):
    # todo: test
    cursor = cursor or connection.cursor()

    cursor.execute('''
      SELECT subq.syn_id, subq.c_id, subq.c_x, subq.c_y, subq.c_z, subq.c_conf, subq.c_user,
        array_agg(tn.skeleton_id), array_agg(tn.id), subq.min_dist
      FROM (
        SELECT
          ss_so.synapse_object_id,
          c.id, c.location_x, c.location_y, c.location_z, c.confidence, c.user_id,
          min(ST_Distance(ST_MakePoint(c.location_x, c.location_y), ss_trans.geom_2d))
        FROM synapse_slice_synapse_object ss_so
        INNER JOIN unnest(%(obj_ids)s::BIGINT[]) AS syns (id)
          ON ss_so.synapse_object_id = syns.id
        INNER JOIN (
          SELECT ss.id, ss.synapse_detection_tile_id, ST_TransScale(
            ss.geom_2d, %(offset_xs)s, %(offset_ys)s, %(resolution_x)s, %(resolution_y)s
          )
            FROM synapse_slice ss
        ) AS ss_trans (id, synapse_detection_tile_id, geom_2d)
          ON ss_trans.id = ss_so.synapse_slice_id
        INNER JOIN synapse_detection_tile tile
          ON ss_trans.synapse_detection_tile_id = tile.id
        INNER JOIN connector c
          ON (tile.z_tile_idx + %(offset_zs)s) * %(resolution_z)s = c.location_z
          -- better way to handle geom?
          AND ST_DWithin(ST_MakePoint(c.location_x, c.location_y), ss_trans.geom_2d, %(tolerance)s)
          AND c.project_id = %(project_id)s
        GROUP BY ss_so.synapse_object_id, c.id
      ) AS subq (syn_id, c_id, c_x, c_y, c_z, c_conf, c_user, min_dist)
      INNER JOIN treenode_connector tc2
        ON tc2.connector_id = subq.c_id
      INNER JOIN treenode tn
        ON tc2.treenode_id = tn.id
      GROUP BY subq.syn_id, subq.c_id, subq.c_x, subq.c_y, subq.c_z, subq.c_conf, subq.c_user, subq.min_dist;
    ''', kwargs)

    return cursor.fetchall()


@api_view(['GET'])
def get_synapse_extents(request, project_id=None):
    """
    Given a set of synapse objects, and optional padding parameters, get the bounding cuboid of the synapse in stack
    coordinates.
    ---
    parameters:
      - name: synapse_object_ids
        description: IDs of synapse objects to get 3D extents for
        type: array
        items:
          type: integer
        required: false
        paramType: form
      - name: z_padding
        description: number of z slices to extend the top and bottom of the bounding box by (default 1)
        type: integer
        required: false
        paramType: form
      - name: xy_padding
        description: number of pixels to extend the bounding box by in the xy plane (default 10)
        type: integer
        required: false
        paramType: form
    type:
      object
    """
    # todo: test
    syn_ids = get_request_list(request.GET, 'synapse_object_ids', tuple(), int)

    if not syn_ids:
        return JsonResponse({})

    z_pad = int(request.GET.get('z_padding', 0))
    xy_pad = int(request.GET.get('xy_padding', 0))

    cursor = connection.cursor()
    # could use ST_Extent, but would then have to interrogate str to add padding
    cursor.execute('''
        SELECT ss_so.synapse_object_id, array_agg(ss.id),
            min(ST_XMin(ss.geom_2d)) - %(xy_pad)s, max(ST_XMax(ss.geom_2d)) + %(xy_pad)s,
            min(ST_YMin(ss.geom_2d)) - %(xy_pad)s, max(ST_YMax(ss.geom_2d)) + %(xy_pad)s,
            min(tile.z_tile_idx) - %(z_pad)s, max(tile.z_tile_idx) + %(z_pad)s
          FROM synapse_slice_synapse_object ss_so
          INNER JOIN synapse_slice ss
            ON ss_so.synapse_slice_id = ss.id
          INNER JOIN synapse_detection_tile tile
            ON ss.synapse_detection_tile_id = tile.id
          WHERE ss_so.synapse_object_id = ANY(%(syn_ids)s::bigint[])
          GROUP BY ss_so.synapse_object_id;
    ''', {'z_pad': z_pad, 'xy_pad': xy_pad, 'syn_ids': syn_ids})

    output = dict()

    for syn_id, slice_ids, xmin, xmax, ymin, ymax, zmin, zmax in cursor.fetchall():
        output[syn_id] = {
            'synapse_slice_ids': list(slice_ids),
            'extents': {
                'xmin': int(xmin),
                'xmax': int(xmax),
                'ymin': int(ymin),
                'ymax': int(ymax),
                'zmin': int(zmin),
                'zmax': int(zmax)
            }
        }

    return JsonResponse(output)


def _skeletons_from_synapse_objects(syn_objs, project_id, cursor=None):
    """

    :param syn_objs: collection of synapse object IDs
    :param project_id:
    :param cursor:
    :return: collection of (syn_obj_id, [tn_ids, ...], skid, sum(contact_area))
    """
    cursor = cursor or connection.cursor()

    cursor.execute('''
            SELECT
                ss_so.synapse_object_id, array_agg(tn.id), tn.skeleton_id, sum(ss_tn.contact_px)
              FROM synapse_slice_synapse_object ss_so
              INNER JOIN unnest(%(syns)s::bigint[]) AS syns(id)
                ON ss_so.synapse_object_id = syns.id
              INNER JOIN synapse_slice_treenode ss_tn
                ON ss_tn.synapse_slice_id = ss_so.synapse_slice_id
              INNER JOIN treenode tn
                ON tn.id = ss_tn.treenode_id
              WHERE tn.project_id = %(pid)s
              GROUP BY ss_so.synapse_object_id, tn.skeleton_id;
        ''', {'pid': project_id, 'syns': syn_objs})

    return cursor.fetchall()


@api_view(['POST'])
def get_partners(request, project_id=None):
    """
    Given a list of synapse object IDs, return a table-like response with headers

    synapse_object_id, tnids, skid, contact_px

    Where there is one row per skeleton the synapse interacts with,
    the list of treenodes it interacts with, and the summed contact area (in px)

    """
    syn_ids = get_request_list(request.POST, 'synapse_object_ids', tuple(), int)

    response = {'columns': ['synapse_object_id', 'tnids', 'skid', 'contact_px']}

    if not syn_ids:
        response['data'] = []
        return JsonResponse(response)

    response['data'] = _skeletons_from_synapse_objects(syn_ids, project_id)
    return JsonResponse(response)


def _synapse_objects_from_skeletons(skids, project_id, pssw_id, cursor=None):
    """

    :param skids: collection of skeleton IDs
    :param project_id:
    :param pssw_id:
    :param threshold: Minimum number of given skeletons
    :param cursor:
    :return: collection of [skid, synapse_object_id, [tnids, ...], total_contact_px]
    """
    cursor = cursor or connection.cursor()
    cursor.execute('''
        SELECT
            tn.skeleton_id, ss_so.synapse_object_id, array_agg(tn.id), sum(ss_tn.contact_px)
          FROM treenode tn
          INNER JOIN unnest(%(skids)s::bigint[]) as sk(id)
            ON sk.id = tn.skeleton_id
          INNER JOIN synapse_slice_treenode ss_tn
            ON tn.id = ss_tn.treenode_id
          INNER JOIN synapse_slice_synapse_object ss_so
            ON ss_tn.synapse_slice_id = ss_so.synapse_slice_id
          WHERE tn.project_id = %(pid)s
            AND ss_tn.project_synapse_suggestion_workflow_id = %(pssw_id)s
          GROUP BY tn.skeleton_id, ss_so.synapse_object_id;
    ''', {"skids": skids, "pid": project_id, "pssw_id": pssw_id})
    return cursor.fetchall()


@api_view(['POST'])
def get_synapses_between(request, project_id=None):
    """
    Takes project_id from URL, list of skeleton_ids, workflow_id

    Returns dict of column names ("columns") and data. Columns are
        skeleton_id, synapse_object_id, treenode_ids, contact_px
    Only if synapse object intersects with more than one query skeleton

    :param request:
    :param project_id:
    :return:
    """
    skel_ids = get_request_list(request.POST, 'skeleton_ids', tuple(), int)
    pssw = get_project_SS_workflow(project_id, request.POST.get('workflow_id'))

    response = {"columns": ["skeleton_id", "synapse_object_id", "treenode_ids", "contact_px"]}

    if not skel_ids:
        response['data'] = []
        return JsonResponse(response)

    all_sk_syn = _synapse_objects_from_skeletons(skel_ids, project_id, pssw.id)
    syn_counts = Counter(row[1] for row in all_sk_syn)

    response['data'] = [row for row in all_sk_syn if syn_counts[row[1]] > 1]
    return JsonResponse(response)

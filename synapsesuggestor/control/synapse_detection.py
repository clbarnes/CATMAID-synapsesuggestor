# -*- coding: utf-8 -*-
"""
Methods used by the synapse detection code
"""
import json
import logging

import networkx as nx

from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view

from catmaid.control.authentication import requires_user_role
from catmaid.control.common import get_request_list
from synapsesuggestor.control.common import list_into_query
from synapsesuggestor.models import SynapseDetectionTile, SynapseObject


logger = logging.getLogger(__name__)


def get_detected_tiles(request, project_id=None):
    """
    GET request which returns the set of tile indices which have been addressed by the given synapse suggestion
    workflow.

    GET parameters:
    workflow_id
    """

    ssw_id = request.GET['workflow_id']

    cursor = connection.cursor()

    cursor.execute('''
        SELECT sdt.x_tile_idx, sdt.y_tile_idx, sdt.z_tile_idx
          FROM synapse_detection_tile sdt
          INNER JOIN synapse_suggestion_workflow ssw
            ON sdt.synapse_suggestion_workflow_id = ssw.id
          WHERE ssw.id = %s;
    ''', (ssw_id,))

    return JsonResponse(cursor.fetchall(), safe=False)


def add_synapse_slices_from_tile(request, project_id=None):
    """
    POST request which adds synapse slices from one tile to the database and returns the mapping from their naive IDs to
     database IDs. This must be done one tile at a time because inserting the tile images into the volume store
     requires the database IDs.

    This function does not agglomerate 2D synapse slices into 3D synapse objects.

    POST parameters:
    x_idx: integer x index of tile
    y_idx: integer y index of tile
    z_idx: integer z index of tile
    workflow_id
    synapse_slices: JSON string encoding dict of synapse slice information of form
        {
            "id": naive ID of synapse slice
            "wkt_str": Multipoint WKT string describing synapse's geometry
            "xs_centroid": integer centroid in x dimension, stack coordinates
            "ys_centroid": integer centroid in y dimension, stack coordinates,
            "size_px"
            "uncertainty"
        }
    tolerance: Geometries are simplified before entering the database. This specifies the tolerance parameter
        used by the Ramer-Douglas-Peucker simplification algorithm. Note that due to this simplification,
        there may be a small difference between a synapseslice's size_px and its ST_Area(geom_2d).
    """
    ssw_id = request.POST['workflow_id']
    synapse_slices = get_request_list(request.POST, 'synapse_slices', tuple(), json.loads)
    tile_x_idx = int(request.POST['x_idx'])
    tile_y_idx = int(request.POST['y_idx'])
    tile_z_idx = int(request.POST['z_idx'])
    rdp_tolerance = float(request.POST.get('tolerance', 1))

    tile, created = SynapseDetectionTile.objects.get_or_create(
        synapse_suggestion_workflow_id=ssw_id,
        x_tile_idx=tile_x_idx,
        y_tile_idx=tile_y_idx,
        z_tile_idx=tile_z_idx
    )
    tile_id = tile.id

    if not synapse_slices:
        return JsonResponse(dict())

    syn_slice_rows = [
        (tile_id, d['wkt_str'], d['size_px'], int(d['xs_centroid']), int(d['ys_centroid']), d['uncertainty'])
        for d in synapse_slices
    ]

    query, args = list_into_query(
        '''
            INSERT INTO synapse_slice (
              synapse_detection_tile_id, geom_2d, size_px, xs_centroid, ys_centroid, uncertainty
            )
            VALUES {}
            RETURNING id;
        ''',
        syn_slice_rows,
        fmt='(%s, ST_Simplify(ST_GeomFromText(%s), {}), %s, %s, %s, %s)'.format(rdp_tolerance)
    )

    cursor = connection.cursor()
    cursor.execute(query, args)
    new_ids = cursor.fetchall()  # todo: check these are in same order as input
    id_mapping = {syn_slice['id']: new_id[0] for syn_slice, new_id in zip(synapse_slices, new_ids)}
    return JsonResponse(id_mapping)


def _get_synapse_slice_adjacencies(synapse_slice_ids, cursor=None):
    """
    Get adjacencies between given synapse slices and all other synapse slices which refer to synapse detection tiles
    which refer to the same synapse suggestion workflow.

    Args:
        synapse_slice_ids(list):

    Returns:
        networkx.Graph: Graph where nodes are synapse slices and edges are spatial adjacencies
    """
    if cursor is None:
        cursor = connection.cursor()

    graph = nx.Graph()
    graph.add_nodes_from(synapse_slice_ids)
    # get rows of synapse slices of interest; join to their tiles; join to z-adjacent tiles; join to synapse slices
    # in those tiles which are also xy-adjacent and do not have the same ID
    query, args = list_into_query('''
        SELECT this_slice.id, that_slice.id FROM synapse_slice this_slice
          INNER JOIN (VALUES {}) these_ids (id)
            ON these_ids.id = this_slice.id
          INNER JOIN synapse_detection_tile this_tile
            ON this_tile.id = this_slice.synapse_detection_tile_id
          INNER JOIN synapse_suggestion_workflow ssw
            ON this_tile.synapse_suggestion_workflow_id = ssw.id
          INNER JOIN synapse_detection_tile that_tile
            ON abs(this_tile.z_tile_idx - that_tile.z_tile_idx) <= 1
            AND abs(this_tile.y_tile_idx - that_tile.y_tile_idx) <= 1
            AND abs(this_tile.x_tile_idx - that_tile.x_tile_idx) <= 1
            AND that_tile.synapse_suggestion_workflow_id = ssw.id
          INNER JOIN synapse_slice that_slice
            ON that_slice.synapse_detection_tile_id = that_tile.id
            AND ST_DWithin(this_slice.geom_2d, that_slice.geom_2d, 1.1)
            AND this_slice.id != that_slice.id;
    ''', synapse_slice_ids, fmt='(%s)')
    cursor.execute(query, args)
    results = cursor.fetchall()
    graph.add_edges_from(results)
    return graph


def _adjacencies_to_slice_clusters(adjacencies, cursor=None):
    """
    Find the connected components of the adjacency graph and include slices not in the original graph,
    but which share a synapse object with those which are, as well as the mappings from connected components to the
    set of synapse objects its slices are already associated with.

    This function is terrible.

    Args:
        adjacencies(networkx.Graph): Graph where nodes are synapse slices and edges are spatial adjacencies

    Returns:
        list: List whose items are a tuple of a set of slice IDs which form an object, and a set of existing synapse
            object IDs associated with that set of slices
    """
    if cursor is None:
        cursor = connection.cursor()

    query, cursor_args = list_into_query('''
            SELECT DISTINCT ss_so2.synapse_slice_id, ss_so2.synapse_object_id FROM synapse_slice_synapse_object ss_so
              INNER JOIN (VALUES {}) ss_interest (id)
                ON ss_so.synapse_slice_id = ss_interest.id
              INNER JOIN synapse_slice_synapse_object ss_so2
                ON ss_so.synapse_object_id = ss_so2.synapse_object_id;
        ''', adjacencies.nodes(), '(%s)')
    cursor.execute(query, cursor_args)

    existing_slice_to_obj = dict()
    existing_obj_to_slices = dict()
    for slice, obj in cursor.fetchall():
        existing_slice_to_obj[slice] = obj
        if obj not in existing_obj_to_slices:
            existing_obj_to_slices[obj] = set()
        existing_obj_to_slices[obj].add(slice)

    for slice_group in existing_obj_to_slices.values():
        # order doesn't matter
        adjacencies.add_path(slice_group)

    out = []
    for connected_component in nx.connected_components(adjacencies):
        possible_objects = {None}
        for slice_id in connected_component:
            possible_objects.add(existing_slice_to_obj.get(slice_id))
        possible_objects.remove(None)
        slices = set(connected_component)
        out.append((slices, possible_objects))

    return out


def _agglomerate_synapse_slices(slice_clusters, cursor=None):
    """
    - If a new synapse slice should belong to an existing synapse object, add it
    - If a new synapse slice bridges the gap between existing synapse objects, remap all slices belonging to the
    obsolete object
    - If a new synapse slice does not belong to an existing synapse object, create it

    Args:
        slice_clusters(list): Each item of the list is a tuple of two sets. The first is a set of synapse slice IDs
            which should combine into a single synapse object the second is a set of synapse object IDs already
            associated with this slice set.
        cursor(django.db.connection.cursor):

    Returns:
        dict: Mapping from synapse slice ID to synapse object ID
    """
    if cursor is None:
        cursor = connection.cursor()

    new_mappings = dict()
    unmapped_syn_slice_groups = []
    bulk_create_args = []
    for slice_ids, possible_object_ids in slice_clusters:
        if possible_object_ids:
            min_id = min(possible_object_ids)
            for slice_id in slice_ids:
                new_mappings[slice_id] = min_id
        else:
            unmapped_syn_slice_groups.append(slice_ids)
            bulk_create_args.append(SynapseObject())

    new_syn_objs = SynapseObject.objects.bulk_create(bulk_create_args)

    for syn_slice_group, new_syn_obj in zip(unmapped_syn_slice_groups, new_syn_objs):
        new_mappings.update({syn_slice: new_syn_obj.id for syn_slice in syn_slice_group})

    logger.info('Inserting new slice:object mappings')
    query, cursor_args = list_into_query("""
        INSERT INTO synapse_slice_synapse_object AS ss_so (synapse_slice_id, synapse_object_id)
          VALUES {}
          ON CONFLICT (synapse_slice_id)
            DO UPDATE SET synapse_object_id = EXCLUDED.synapse_object_id;
    """, new_mappings.items(), fmt='(%s, %s)')
    cursor.execute(query, cursor_args)

    return dict(new_mappings)


def _delete_unused_synapse_objects(cursor=None):
    """
    Delete any synapse objects not referred to by any synapse slice : synapse object mappings.

    Args:
        cursor(django.db.connection.cursor):

    Returns:
        list: IDs of deleted synapse objects
    """
    if cursor is None:
        cursor = connection.cursor()

    cursor.execute('''
        DELETE FROM synapse_object so
          WHERE NOT EXISTS (
            SELECT * FROM synapse_slice_synapse_object ss_so
              WHERE so.id = ss_so.synapse_object_id
          )
          RETURNING so.id;
    ''')

    return [item[0] for item in cursor.fetchall()]


@api_view(['POST'])
def agglomerate_synapse_slices(request, project_id=None):
    """
    POST request which agglomerates given synapse slices into synapse objects (including agglomerating with existing
    unspecified slices).
    ---
    parameters:
      - name: synapse_slices
        description: List of synapse slice IDs to use as seeds for synapse object creation
        type: array
        items:
          type: integer
        required: false
        paramType: form
    type:
      slice_object_mappings:
        required: true
        type: object
        description: object whose keys are synapse slice IDs and values are synapse object IDs they now belong to
      deleted_objects:
        required: true
        type: array
        items:
          type: integer
        description: array of synapse object IDs deleted due to lack of synapse slices mapping to them.
    """
    synapse_slice_ids = get_request_list(request.POST, 'synapse_slices', tuple(), int)

    cursor = connection.cursor()

    if synapse_slice_ids:
        adjacencies = _get_synapse_slice_adjacencies(synapse_slice_ids, cursor)
        ext_adjacencies = _adjacencies_to_slice_clusters(adjacencies, cursor)
        new_mappings = _agglomerate_synapse_slices(ext_adjacencies, cursor)
    else:
        new_mappings = dict()

    deleted_objects = _delete_unused_synapse_objects(cursor)
    return JsonResponse({'slice_object_mappings': new_mappings, 'deleted_objects': deleted_objects})

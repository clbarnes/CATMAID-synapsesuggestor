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
from synapsesuggestor.models import SynapseDetectionTile


logger = logging.getLogger(__name__)


def get_detected_tiles(request, project_id=None):
    """
    GET request which returns the set of tile indices which have been addressed by the given synapse suggestion
    workflow.

    GET parameters:
    workflow_id

    Parameters
    ----------
    request
    project_id

    Returns
    -------
    list of lists
        List of [x, y, z] indices of tiles which have been processed by the synapse detector
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
            "wkt_str": Multipoint WKT string describing synapse's geometry (will be convex hulled)
            "xs_centroid": integer centroid in x dimension, stack coordinates
            "ys_centroid": integer centroid in y dimension, stack coordinates,
            "size_px"
            "uncertainty"
        }

    Parameters
    ----------
    request
    project_id

    Returns
    -------
    dict
        Mapping from naive IDs to database IDs
    """
    ssw_id = request.POST['workflow_id']
    synapse_slices = get_request_list(request.POST, 'synapse_slices', tuple(), json.loads)
    tile_x_idx = int(request.POST['x_idx'])
    tile_y_idx = int(request.POST['y_idx'])
    tile_z_idx = int(request.POST['z_idx'])

    tile, created = SynapseDetectionTile.objects.get_or_create(
        synapse_suggestion_workflow_id=ssw_id,
        x_tile_idx=tile_x_idx,
        y_tile_idx=tile_y_idx,
        z_tile_idx=tile_z_idx
    )
    tile_id = tile.id

    syn_slice_rows = [
        (tile_id, d['wkt_str'], d['size_px'], int(d['xs_centroid']), int(d['ys_centroid']), d['uncertainty'])
        for d in synapse_slices
    ]

    print(syn_slice_rows)

    query, args = list_into_query(
        '''
            INSERT INTO synapse_slice (
              synapse_detection_tile_id, convex_hull_2d, size_px, xs_centroid, ys_centroid, uncertainty
            )
            VALUES {}
            RETURNING id;
        ''',
        syn_slice_rows,
        fmt='(%s, ST_ConvexHull(ST_GeomFromText(%s)), %s, %s, %s, %s)'
    )

    cursor = connection.cursor()
    cursor.execute(query, args)
    new_ids = cursor.fetchall()  # todo: check these are in same order as input
    id_mapping = {syn_slice['id']: new_id[0] for syn_slice, new_id in zip(synapse_slices, new_ids)}
    return JsonResponse(id_mapping)


def _get_synapse_slice_adjacencies(synapse_slice_ids):
    """
    Get adjacencies between given synapse slices and all other synapse slices which refer to synapse detection tiles
    which refer to the same synapse suggestion workflow.

    Parameters
    ----------
    synapse_slice_ids : list

    Returns
    -------
    networkx.Graph
        Graph of synapse slice adjacencies, whose node set is a superset of the given synapse slice IDs
    """
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
            ON this_tile.id = this_slice.tile_synapse_detection_algorithm_id
          INNER JOIN synapse_suggestion_workflow ssw
            ON this_tile.synapse_suggestion_workflow_id = ssw.id
          INNER JOIN synapse_detection_tile that_tile
            ON abs(this_tile.z_tile_idx - that_tile.z_tile_idx) <= 1
            AND abs(this_tile.y_tile_idx - that_tile.y_tile_idx) <= 1
            AND abs(this_tile.x_tile_idx - that_tile.x_tile_idx) <= 1
            AND that_tile.synapse_suggestion_workflow_id = ssw.id
          INNER JOIN synapse_slice that_slice
            ON that_slice.synapse_detection_tile_id = that_tile.id
            AND ST_DWithin(this_slice.convex_hull_2d, that_slice.convex_hull_2d, 1.1)
            AND this_slice.id != that_slice.id;
    ''', synapse_slice_ids, fmt='(%s)')
    cursor.execute(query, args)
    results = cursor.fetchall()
    graph.add_edges_from(results)
    return graph


def _agglomerate_synapse_slices(synapse_slice_ids):
    """
    - Find adjacencies between given synapse slices and all other synapse slices
    - If a new synapse slice should belong to an existing synapse object, add it
    - If a new synapse slice bridges the gap between existing synapse objects, remap all slices belonging to the
    obsolete object
    - If a new synapse slice does not belong to an existing synapse object, create it

    Parameters
    ----------
    synapse_slice_ids

    Returns
    -------

    """
    adjacencies = _get_synapse_slice_adjacencies(synapse_slice_ids)

    # get existing synapse slice -> synapse object mappings for synapse slices involved in adjacencies with given
    # synapse slices

    cursor = connection.cursor()
    query, cursor_args = list_into_query('''
        SELECT ss_so2.synapse_slice_id, ss_so2.synapse_object_id FROM synapse_slice_synapse_object ss_so
          INNER JOIN (VALUES {}) ss_interest (id)
            ON ss_so.synapse_slice_id = ss_interest.id
          INNER JOIN synapse_slice_synapse_object ss_so2
            ON ss_so.synapse_object_id = ss_so2.synapse_object_id;
    ''', adjacencies.nodes(), '(%s)')
    cursor.execute(query, cursor_args)
    existing_syn_slice_to_obj = dict(cursor.fetchall())

    # initialise list of new mappings to add, and old objects to remove

    new_mappings = []
    obsolete_objects = set()

    # list of lists: each inner list is a group of adjacent synapse slices
    unmapped_syn_slices = []

    for syn_slice_group in nx.connected_components(adjacencies):
        # get object IDs already associated with slices in this new object
        syn_obj_ids = {
            existing_syn_slice_to_obj[slice_id]
            for slice_id in syn_slice_group
            if slice_id in existing_syn_slice_to_obj
        }

        if len(syn_obj_ids) == 0:
            # these need a new object created
            unmapped_syn_slices.append(syn_slice_group)
        else:
            # of the existing objects associated with these slices, pick one
            min_obj_id = min(syn_obj_ids)
            # get set of slices, new and existing, to map to a single existing object
            slices_to_map = set(syn_slice_group).union(
                key for key, value in existing_syn_slice_to_obj.items()
                if value in syn_obj_ids and value != min_obj_id
            )
            new_mappings.extend((slice_id, min_obj_id) for slice_id in slices_to_map)
            obsolete_objects.update(syn_obj_id for syn_obj_id in syn_obj_ids if syn_obj_id != min_obj_id)

    if obsolete_objects:  # todo: do this in SQL? probably possible with delete using and count
        logger.info('Deleting obsolete synapse objects')
        query, cursor_args = list_into_query("DELETE FROM synapse_object WHERE id IN ({});", obsolete_objects)
        cursor.execute(query, cursor_args)

    logger.info('Creating new synapse objects')
    query, args = list_into_query('''
        INSERT INTO synapse_object (id)
          VALUES {}
          RETURNING id;
    ''', ['DEFAULT' for _ in unmapped_syn_slices], fmt='(%s)')
    cursor.execute(query, args)

    for syn_slice_group, new_syn_obj_tup in zip(unmapped_syn_slices, cursor.fetchall()):
        new_mappings.extend((syn_slice, new_syn_obj_tup[0]) for syn_slice in syn_slice_group)

    logger.info('Inserting new slice:object mappings')
    query, cursor_args = list_into_query("""
        INSERT INTO synapse_slice_synapse_object AS ss_so (synapse_slice_id, synapse_object_id)
          VALUES {} AS new (slice_id, obj_id)
          ON CONFLICT (ss_so.synapse_slice_id)
            DO UPDATE SET ss_so.synapse_object_id = new.obj_id;
    """, new_mappings, fmt='(%s, %s)')  # todo: check this

    cursor.execute(query, cursor_args)

    return dict(new_mappings)


def agglomerate_synapse_slices(request, project_id=None):
    """
    POST request which agglomerates given synapse slices into synapse objects (including agglomerating with existing
    unspecified slices).

    POST parameters:
    synapse_slices[]: list of synapse slice IDs

    Parameters
    ----------
    request
    project_id

    Returns
    -------
    dict
        New mappings from synapse slice ID to synapse object ID.
    """
    synapse_slice_ids = get_request_list(request.POST, 'synapse_slices', tuple, int)
    new_mappings = _agglomerate_synapse_slices(synapse_slice_ids)
    return JsonResponse(new_mappings)

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
from synapsesuggestor.control.common import list_into_query, list_into_query_multi


logger = logging.getLogger(__name__)


def get_undetected_tiles(request, project_id=None):
    """
    POST request which takes a list of tiles and a synapse detection algorithm ID and returns the subset of those 
    tiles which have not been processed by that synapse detection algorithm.

    POST parameters:
    algo_version: integer version number of synapse detection algorithm
    stack_mirror: integer ID of stack mirror on which tiling is based
    tile_idxs[]: jQuery or CATMAID-formatted list of strings which are JSON-formatted arrays of the [x, y, 
    z] indices of the tile

    Parameters
    ----------
    request
    project_id

    Returns
    -------
    list of lists
        List of [x, y, z] indices of tiles which have not been processed by the synapse detector
    """

    # todo: replace with something which calculates tiles itself and just needs the skeleton

    algo_version = int(request.POST.get('algo_version', 0))
    stack_mirror = int(request.POST.get('stack_mirror', 0))

    tile_idxs = set(get_request_list(request.POST, 'tile_idxs', tuple(), lambda x: tuple(json.loads(x))))

    # x, y, z, stack_mirror, algo_version
    temp_rows = (t_idx + (stack_mirror, algo_version) for t_idx in tile_idxs)

    cursor = connection.cursor()

    query, args = list_into_query('''
        SELECT tsda.x_tile_idx, tsda.y_tile_idx, tsda.z_tile_idx FROM tile_synapse_detection_algorithm tsda
          INNER JOIN ( VALUES {temp_rows} ) tmp (x, y, z, mirror, algo)
            ON  tsda.x_tile_idx = tmp.x
            AND tsda.y_tile_idx = tmp.y
            AND tsda.z_tile_idx = tmp.z
            AND tsda.stack_mirror_id = tmp.mirror
            AND tsda.synapse_detection_algorithm_id = tmp.algo;
    ''', temp_rows, fmt='(%s, %s, %s, %s, %s)')

    cursor.execute(query, args)

    processed_idxs = ((x, y, z) for x, y, z, _, _ in cursor.fetchall())

    fresh_tile_idxs = list(tile_idxs.difference(processed_idxs))

    return JsonResponse(fresh_tile_idxs, safe=False)


def get_unassociated_nodes(request, project_id=None):
    """
    GET request which takes a skeleton ID and returns treenodes which belong to that skeleton and have not been 
    addressed by this version of the skeleton association algorithm.

    GET parameters:
    algo_version: integer skeleton association algorithm version
    skid: skeleton ID from which to pull nodes and check whether they have been addressed 

    Parameters
    ----------
    request
    project_id

    Returns
    -------
    list
        List of node IDs to check for association with synapses
    """

    # todo: check if nodes have a detected synapse slice near them?

    algo_version = int(request.GET.get('algo_version', 0))
    skel_id = int(request.GET.get('skid', 0))

    cursor = connection.cursor()

    cursor.execute('''
        SELECT DISTINCT tn.id FROM treenode tn 
          JOIN synapse_slice_treenode sst
            ON sst.treenode_id = tn.id
          WHERE tn.skeleton_id = %s
            AND sst.skeleton_association_algorithm_id != %s;
    ''', (skel_id, algo_version))

    node_ids = [row[0] for row in cursor.fetchall()]

    return JsonResponse(node_ids, safe=False)


def delete_synapse_slices_from_tile(request, project_id=None):
    """
    GET request which takes a tile's x, y, and z index and the stack mirror, and deletes synapse slices associated 
    with that.

    GET parameters:
    x_idx: x index of tile
    x_idx: y index of tile
    x_idx: z index of tile
    stack_mirror: ID of stack mirror
    algo_version: synapse detection algorithm version

    Parameters
    ----------
    request
    project_id

    Returns
    -------

    """
    stack_mirror = int(request.GET['stack_mirror'])
    tile_idx_xyz = (
        int(request.GET['x_idx']),
        int(request.GET['y_idx']),
        int(request.GET['z_idx'])
    )
    algo_version = int(request.GET['algo_version'])

    cursor = connection.cursor()
    cursor.execute('''
        DELETE FROM synapse_slice ss
          USING tile_synapse_detection_algorithm tsda
          WHERE ss.tile_synapse_detection_algorithm_id = tsda.id
          AND tsda.x_tile_idx = %s 
          AND tsda.y_tile_idx = %s 
          AND tsda.z_tile_idx = %s
          AND tsda.stack_mirror_id = %s
          AND tsda.synapse_detection_algorithm_id = %s;
    ''', tile_idx_xyz + (stack_mirror, algo_version))  # todo: am I using this right?


def _get_or_create_tile_synapse_detection_algorithm(tile_idx_xyz, stack_mirror, algo_version):
    """
    Gets the ID of the requested TileSynapseDetectionAlgorithm object, creating it if it doesn't exist.
    
    Parameters
    ----------
    tile_idx_xyz : tuple of int
        (x, y, z) index of tile
    stack_mirror : int
        Stack mirror ID
    algo_version : int
        Synapse detection algorithm version

    Returns
    -------
    int
        TileSynapseDetectionAlgorithm object ID
    """
    cursor = connection.cursor()
    cursor.execute('''
            INSERT INTO tile_synapse_detection_algorithm AS tsda (
              x_tile_idx, y_tile_idx, z_tile_idx, stack_mirror, synapse_detection_algorithm_id
            )
            SELECT %s, %s, %s, %s, %s
              WHERE NOT EXISTS (
                SELECT id FROM tsda
                  WHERE tsda.stack_mirror_id = %s
                    AND tsda.synapse_detection_algorithm_id = %s
                    AND tsda.x_tile_idx = %s
                    AND tsda.y_tile_idx = %s
                    AND tsda.z_tile_idx = %s;
              )
            LIMIT 1
            RETURNING id;
        ''', (tile_idx_xyz + (stack_mirror, algo_version)) * 2)  # todo: check this
    return cursor.fetchone()[0]


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
    stack_mirror: integer stack mirror ID
    algo_version: integer synapse detection algorithm ID
    synapse_slices: JSON string encoding dict of synapse slice information of form
        {
            "id": naive ID of synapse slice
            "wkt_str": Multipoint WKT string describing synapse's geometry (will be convex hulled)
            "xs_centroid": integer centroid in x dimension, stack coordinates
            "ys_centroid": integer centroid in y dimension, stack coordinates
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
    synapse_slices = get_request_list(request.POST, 'synapse_slices', tuple(), json.loads)
    tile_idx_xyz = (
        int(request.POST['x_idx']),
        int(request.POST['y_idx']),
        int(request.POST['z_idx'])
    )
    stack_mirror = int(request.POST['stack_mirror'])
    algo_version = int(request.POST['algo_version'])

    tsda_id = _get_or_create_tile_synapse_detection_algorithm(
        tile_idx_xyz, stack_mirror, algo_version
    )

    syn_slice_rows = [
        (tsda_id, d['wkt_str'], d['size_px'], d['xs_centroid'], d['ys_centroid'])
        for d in synapse_slices
    ]

    query, args = list_into_query_multi('''
        INSERT INTO synapse_slices (
          tile_synapse_detection_algorithm_id, convex_hull_2d, size_px, xs_centroid, ys_centroid
        ) 
        VALUES {syn_slice_rows}
        RETURNING id;
    ''', fmt={'syn_slice_rows': '(%s, ST_ConvexHull(ST_GeomFromText(%s)), %s, %s, %s)'}, syn_slice_rows=syn_slice_rows)

    cursor = connection.cursor()
    cursor.execute(query, args)
    new_ids = cursor.fetchall()  # todo: check these are in same order as input
    id_mapping = {syn_slice['id']: new_id[0] for syn_slice, new_id in zip(synapse_slices, new_ids)}
    return JsonResponse(id_mapping)


def _get_synapse_slice_adjacencies(synapse_slice_ids):
    """
    Get adjacencies between given synapse slices and all other synapse slices in the database.
    
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
          INNER JOIN tile_synapse_detection_algorithm this_tile
            ON this_tile.id = this_slice.tile_synapse_detection_algorithm_id
          INNER JOIN tile_synapse_detection_algorithm that_tile
            ON abs(this_tile.z_tile_idx - that_tile.z_tile_idx) <= 1
          INNER JOIN synapse_slice that_slice
            ON that_tile.id = that_slice.tile_synapse_detection_algorithm_id
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
    # todo: constrain to synapse slices gleaned from the same stack mirror?
    adjacencies = _get_synapse_slice_adjacencies(synapse_slice_ids)

    cursor = connection.cursor()
    query, cursor_args = list_into_query('''
        SELECT sl_obj.synapse_slice_id, sl_obj.synapse_object_id FROM synapse_slice_synapse_object sl_obj
          INNER JOIN (VALUES {}) syn_sl (id) 
            ON (syn_sl.id = sl_obj.synapse_slice_id);
    ''', adjacencies.nodes(), fmt='(%s)')
    cursor.execute(query, cursor_args)
    existing_syn_slice_to_obj = dict(cursor.fetchall())

    new_mappings = []
    obsolete_objects = set()

    unmapped_syn_slices = []

    for syn_slice_group in nx.connected_components(adjacencies):
        syn_obj_ids = {
            existing_syn_slice_to_obj[slice_id]
            for slice_id in syn_slice_group
            if slice_id in existing_syn_slice_to_obj
        }

        if len(syn_obj_ids) == 0:
            unmapped_syn_slices.append(syn_slice_group)
        else:
            min_id = min(syn_obj_ids)
            new_mappings.extend((slice_id, min_id) for slice_id in syn_slice_group)
            obsolete_objects.update(syn_obj_id for syn_obj_id in syn_obj_ids if syn_obj_id != min_id)

    if obsolete_objects:  # todo: do this in SQL? probably possible with delete using and count
        logger.info('Deleting obsolete synapse objects')
        query, cursor_args = list_into_query("DELETE FROM synapse_object WHERE id IN ({});", obsolete_objects)
        cursor.execute(query, cursor_args)

    logger.info('Creating new synapse objects')
    query = '''
        INSERT INTO synapse_object (id)
          VALUES {}
          RETURNING id;
    '''.format(', '.join('(DEFAULT)' for _ in unmapped_syn_slices))
    cursor.execute(query)

    for syn_slice_group, new_syn_obj in zip(unmapped_syn_slices, cursor.fetchall()):
        new_mappings.extend((syn_slice, new_syn_obj) for syn_slice in syn_slice_group)

    logger.info('Inserting new slice:object mappings')
    query, cursor_args = list_into_query("""
        INSERT INTO synapse_slice_synapse_object AS ss_so (synapse_slice_id, synapse_object_id)
          VALUES {} AS new (slice_id, obj_id)
          ON CONFLICT (ss_so.synapse_slice_id)
            DO UPDATE SET ss_so.synapse_object_id = new.obj_id;
    """, new_mappings, fmt='(%s, %s)')  # todo: check this

    cursor.execute(query, cursor_args)


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

    """
    synapse_slice_ids = get_request_list(request.POST, 'synapse_slices', tuple, int)
    _agglomerate_synapse_slices(synapse_slice_ids)

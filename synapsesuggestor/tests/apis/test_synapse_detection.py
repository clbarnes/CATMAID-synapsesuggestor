# -*- coding: utf-8 -*-
import json
from unittest import skip

import numpy as np
from six import assertCountEqual

from django.db import connection

from synapsesuggestor.models import SynapseSliceSynapseObject, SynapseObject, SynapseSlice
from synapsesuggestor.tests.common import SynapseSuggestorTestCase

URL_PREFIX = '/ext/synapsesuggestor/synapse-detection'

# Synapse geometries are simplified; default value is 1, which breaks most of the test data
RDP_TOLERANCE = 0.1


def close_ring(coord_lst):
    if coord_lst[-1] == coord_lst[0]:
        return coord_lst
    else:
        return coord_lst + [coord_lst[0]]


def get_slice_geom(*ss_ids):
    cursor = connection.cursor()
    output = dict()
    for ss_id in ss_ids:
        cursor.execute('SELECT ST_AsGeoJSON(ss.geom_2d) FROM synapse_slice ss WHERE ss.id = %s;', (ss_id, ))
        output[ss_id] = json.loads(cursor.fetchone()[0])

    return output


class SynapseDetectionApiTests(SynapseSuggestorTestCase):
    def test_get_detected_tiles(self):
        self.fake_authentication()

        response = self.client.get(
            URL_PREFIX + '/tiles/detected',
            {'workflow_id': self.test_ssw_id}
        )
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))

        expected_result = [[0, 0, 0], [0, 0, 1]]
        assertCountEqual(self, expected_result, parsed_response)

    def test_get_detected_tiles_empty(self):
        other_ssw_id = 500

        self.fake_authentication()

        response = self.client.get(
            URL_PREFIX + '/tiles/detected',
            {'workflow_id': other_ssw_id}
        )
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))

        expected_result = []
        self.assertListEqual(expected_result, parsed_response)

    def create_synapse_slice_data(self, coords, tile_idx, size_px=50, uncertainty=0.5, workflow_id=None):
        """
        Create data to be posted to CATMAID for creating any number of synapse slices

        Parameters
        ----------
        coords : list of list of tuple
        tile_idx
        id
        size_px
        uncertainty

        Returns
        -------
        tuple of (dict, list)
            Dictionary of data to post to add_synapse_slices_from_tile and list of raw IDs
        """
        if workflow_id is None:
            workflow_id = self.test_ssw_id

        orig_ids = []
        dict_strs = []
        for idx, coord_lst in enumerate(coords, 1):
            geom = {"type": "Polygon", "coordinates": [close_ring(coord_lst)]}
            xs_centroid = int(np.mean([x for x, _ in coord_lst]))
            ys_centroid = int(np.mean([y for _, y in coord_lst]))

            orig_ids.append(idx)

            dict_strs.append(json.dumps(
                {
                    'id': idx,
                    'geom': geom,
                    'xs_centroid': xs_centroid,
                    'ys_centroid': ys_centroid,
                    'size_px': size_px,
                    'uncertainty': uncertainty
                }
            ))

        data = {
            'workflow_id': workflow_id,
            'x_idx': tile_idx[0],
            'y_idx': tile_idx[1],
            'z_idx': tile_idx[2],
            'synapse_slices': dict_strs,
            'tolerance': RDP_TOLERANCE
        }

        return data, orig_ids

    def test_add_synapse_slices_from_tile(self):
        """Depends on get_detected_tiles"""
        self.fake_authentication()

        syn1_coords = [(0, 0), (1, 0), (1, 1), (0, 1)]
        syn2_coords = [(1, 0), (2, 0), (2, 1), (1, 1)]
        tile_idxs = [0, 0, 1]
        data, orig_ids = self.create_synapse_slice_data([syn1_coords, syn2_coords], tile_idxs)

        response = self.client.post(URL_PREFIX + '/tiles/insert-synapse-slices', data)
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))

        self.assertEqual(len(parsed_response), len(orig_ids))
        self.assertSetEqual({int(key) for key in parsed_response.keys()}, set(orig_ids))
        self.assertEqual(len(parsed_response), len(set(parsed_response.values())))

    def insert_synapses(self, z, *toplefts, **kwargs):
        """
        Insert synapses into the database at the given locations

        Parameters
        ----------
        z : int
            z index of synapse slice
        topleft : tuple
            x, y coordinates of top left point of 1x1x1 synapse slice
        kwargs
            Can include 'width' and 'height' (default 1)

        Returns
        -------
        list
            IDs of the inserted synapses
        """
        width = kwargs.get('width', 1)
        height = kwargs.get('height', 1)

        syn_coords = []
        for topleft in toplefts:
            x, y = topleft
            syn_coords.append([(x, y), (x + width, y), (x + width, y + height), (x, y + height)])

        data, orig_ids = self.create_synapse_slice_data(syn_coords, (0, 0, z))

        response = self.client.post(URL_PREFIX + '/tiles/insert-synapse-slices', data)
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(parsed_response), len(toplefts))

        return [parsed_response[str(orig_id)] for orig_id in orig_ids]

    def test_simplified_geom(self):
        """Test that unnecessary points are removed from a geometry"""
        input_coord_list = [(0, 0), (1, 0), (1, 0.5), (1, 1), (0, 1), (0, 0)]
        data, orig_ids = self.create_synapse_slice_data([input_coord_list], [0, 0, 0])
        response = self.client.post(URL_PREFIX + '/tiles/insert-synapse-slices', data)
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))
        new_id = parsed_response[str(orig_ids[0])]

        geom = get_slice_geom(new_id)[new_id]
        outer_ring = geom['coordinates'][0]
        self.assertEqual(len(outer_ring), len(input_coord_list) - 1)  # remove a coord
        self.assertSetEqual({tuple(xy) for xy in outer_ring}, {(0, 0), (1, 0), (1, 1), (0, 1)})

    @skip("Database does not force geometries into particular orientation")
    def test_RHR_geom(self):
        """Test that the stored geometry returns a left-hand-rule-compliant geometry (exterior counter-clockwise)"""
        order = ('cw', 'counter_cw')

        coords = {
            'cw': [[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]],
            'counter_cw': [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
        }

        data, orig_ids = self.create_synapse_slice_data([coords[key] for key in order], [0, 0, 0])
        orig_ids = dict(zip(order, orig_ids))
        response = self.client.post(URL_PREFIX + '/tiles/insert-synapse-slices', data)
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))
        new_ids = {key: parsed_response[str(value)] for key, value in orig_ids.items()}

        id_geoms = get_slice_geom(*list(new_ids.values()))
        geoms = {key: id_geoms[value] for key, value in new_ids.items()}
        self.assertListEqual(geoms['cw']['coordinates'], geoms['counter_cw']['coordinates'])  # output geoms identical
        self.assertListEqual(geoms['cw']['coordinates'], [coords['counter_cw']])  # output geoms are both CCW

    def agglomerate_synapses(self, syn_ids):
        """
        Agglomerate synapses, test and parse response

        Parameters
        ----------
        syn_ids : list of (str or int)
            Synapse slices to be used as the seed for agglomeration

        Returns
        -------
        dict
            Mapping from synapse slice IDs to synapse object IDs
        """
        response = self.client.post(URL_PREFIX + '/slices/agglomerate', {'synapse_slices': syn_ids})
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content.decode('utf-8'))

    def test_agglomerate_synapse_slices_deletes_object(self):
        """
        Test that the agglomerate endpoint deletes empty synapse objects
        """
        self.fake_authentication()

        parsed_response = self.agglomerate_synapses([])
        self.assertListEqual(parsed_response['deleted_objects'], [2])

        syn_objs = SynapseObject.objects.filter(pk=2)
        self.assertEqual(syn_objs.exists(), False)

    def test_agglomerate_synapse_slices_xy_adjacent(self):
        """
        Depends on add_synapse_slices_from_tile

        Test that two adjacent synapses on the same Z plane are agglomerated.
        """
        self.fake_authentication()

        new_ids = self.insert_synapses(0, (0, 1))

        parsed_response = self.agglomerate_synapses(new_ids)

        expected_response = {str(new_ids[0]): 1, '2': 1, '3': 1}

        self.assertDictEqual(expected_response, parsed_response['slice_object_mappings'])

    def test_agglomerate_synapse_slices_z_adjacent(self):
        """
        Depends on add_synapse_slices_from_tile

        Test that two adjacent synapses on different Z planes are agglomerated
        """
        self.fake_authentication()

        new_ids = self.insert_synapses(1, (0, 0))

        parsed_response = self.agglomerate_synapses(new_ids)

        expected_response = {str(new_ids[0]): 1, '2': 1, '3': 1}

        self.assertDictEqual(expected_response, parsed_response['slice_object_mappings'])

    def test_agglomerate_synapse_slices_separate(self):
        """
        Depends on add_synapse_slices_from_tile

        Test that a new synapse slice separated from existing synapse slices is not agglomerated with them,
        and a new synapse object is created for it.
        """
        self.fake_authentication()
        existing_mappings = SynapseSliceSynapseObject.objects.all()
        len(existing_mappings)  # force query to evaluate

        new_ids = self.insert_synapses(0, (0, 3))

        parsed_response = self.agglomerate_synapses(new_ids)

        expected_key = str(new_ids[0])

        self.assertListEqual([expected_key], list(parsed_response['slice_object_mappings']))

        new_mappings = SynapseSliceSynapseObject.objects.filter(synapse_slice_id=new_ids[0])
        self.assertEqual(len(new_mappings), 1)
        self.assertNotIn(new_mappings[0].synapse_object_id, [m.synapse_object_id for m in existing_mappings])

    def test_agglomerate_synapse_slices_two_objects(self):
        """
        Depends on add_synapse_slices_from_tile and agglomerate_synapse_slices

        Test that two distinct synapse objects can be merged into one if a new slice is added bridging them.
        """
        self.fake_authentication()

        # set up distant syn slice with its own syn object
        # should be identical to test_agglomerate_synapse_slices_separate
        new_ids = self.insert_synapses(0, (0, 3))
        parsed_response = self.agglomerate_synapses(new_ids)
        self.assertEqual(len(parsed_response['slice_object_mappings']), 1)

        # set up a bridge synapse which will force all of them to agglomerate
        new_ids = self.insert_synapses(0, (0, 1), height=2)
        parsed_response = self.agglomerate_synapses(new_ids)

        # check all 4 syn slices are merged
        self.assertEqual(len(parsed_response['slice_object_mappings']), 4)
        # check they all map to the same synapse object
        self.assertEqual(len(set(parsed_response['slice_object_mappings'].values())), 1)

        # test old mapping was cleared up
        mappings = SynapseSliceSynapseObject.objects.all()
        self.assertEqual(len(mappings), 4)  # there is still only 1 mapping per slice
        self.assertEqual(len({m.synapse_object_id for m in mappings}), 1)  # all mappings point to the same object

    def test_agglomerate_synapses_same_slice(self):
        """
        Depends on add_synapse_slices_from_tile

        Test that cases where the same synapse slice ID is passed in twice does not raise errors.
        """
        self.fake_authentication()

        new_ids = self.insert_synapses(0, (0, 1))
        duplicated_new_ids = list(new_ids) * 2

        parsed_response = self.agglomerate_synapses(duplicated_new_ids)

        expected_response = {str(new_ids[0]): 1, '2': 1, '3': 1}

        self.assertDictEqual(expected_response, parsed_response['slice_object_mappings'])

    def clear_synapses(self):
        for model in SynapseSlice, SynapseObject, SynapseSliceSynapseObject:
            model.objects.all().delete()
            self.assertEqual(model.objects.count(), 0)

    def test_agglomerate_synapses_double_association(self):
        """
        Depends on add_synapse_slices_from_tile and agglomerate_synapse_slices

        Test that when new synapse slices are added which straddle an existing multi-slice object, they are all
        agglomerated together (original bug tried to map slice to two different synapse objects)
        """
        self.fake_authentication()
        self.clear_synapses()

        leftmost_ids = self.insert_synapses(0, (0, 0))
        self.agglomerate_synapses(leftmost_ids)
        right_orig_ids = self.insert_synapses(0, (5, 0), (7, 0), width=2)
        self.agglomerate_synapses(right_orig_ids)

        self.assertEqual(SynapseObject.objects.count(), 2)
        self.assertEqual(SynapseSliceSynapseObject.objects.count(), SynapseSlice.objects.count())

        bridge_ids = self.insert_synapses(0, (1, 0), (3, 0), width=2)
        rightmost_ids = self.insert_synapses(0, (9, 0))
        self.agglomerate_synapses(bridge_ids + rightmost_ids)

        self.assertEqual(SynapseObject.objects.count(), 1)
        self.assertEqual(SynapseSliceSynapseObject.objects.count(), SynapseSlice.objects.count())

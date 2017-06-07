# -*- coding: utf-8 -*-
import json

import numpy as np
from six import assertCountEqual

from synapsesuggestor.models import SynapseSliceSynapseObject, SynapseObject
from synapsesuggestor.tests.common import SynapseSuggestorTestCase

URL_PREFIX = '/synapsesuggestor/synapse-detection'


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
            wkt_str = 'MULTIPOINT({})'.format(','.join('{} {}'.format(x, y) for x, y in coord_lst))
            xs_centroid = int(np.mean([x for x, _ in coord_lst]))
            ys_centroid = int(np.mean([y for _, y in coord_lst]))

            orig_ids.append(idx)

            dict_strs.append(json.dumps(
                {
                    'id': idx,
                    'wkt_str': wkt_str,
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
            'synapse_slices': dict_strs
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

        self.assertEqual(len(orig_ids), len(parsed_response))
        self.assertSetEqual(set(orig_ids), {int(key) for key in parsed_response.keys()})
        self.assertEqual(len(parsed_response), len(set(parsed_response.values())))

    def insert_synapse(self, z, *toplefts):
        """
        Insert a single synapse into the database at the given location

        Parameters
        ----------
        z : int
            z index of synapse slice
        topleft : tuple
            x, y coordinates of top left point of 1x1x1 synapse slice

        Returns
        -------
        list
            IDs of the inserted synapses
        """
        syn_coords = []
        for topleft in toplefts:
            x, y = topleft
            syn_coords.append([(x, y), (x+1, 7), (x+1, y+1), (x, y+1)])

        data, orig_ids = self.create_synapse_slice_data(syn_coords, (0, 0, z))

        response = self.client.post(URL_PREFIX + '/tiles/insert-synapse-slices', data)
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(parsed_response), len(toplefts))

        return [parsed_response[str(orig_id)] for orig_id in orig_ids]

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
        self.fake_authentication()

        parsed_response = self.agglomerate_synapses([])
        self.assertListEqual(parsed_response['deleted_objects'], [2])

        syn_objs = SynapseObject.objects.filter(pk=2)
        self.assertEqual(syn_objs.exists(), False)

    def test_agglomerate_synapse_slices_xy_adjacent(self):
        """Depends on add_synapse_slices_from_tile"""
        self.fake_authentication()

        new_ids = self.insert_synapse(0, (0, 1))

        parsed_response = self.agglomerate_synapses(new_ids)

        expected_response = {str(new_ids[0]): 1, '2': 1, '3': 1}

        self.assertDictEqual(expected_response, parsed_response['slice_object_mappings'])

    def test_agglomerate_synapse_slices_z_adjacent(self):
        """Depends on add_synapse_slices_from_tile"""
        self.fake_authentication()

        new_ids = self.insert_synapse(1, (0, 0))

        parsed_response = self.agglomerate_synapses(new_ids)

        expected_response = {str(new_ids[0]): 1, '2': 1, '3': 1}

        self.assertDictEqual(expected_response, parsed_response['slice_object_mappings'])

    def test_agglomerate_synapse_slices_separate(self):
        """Depends on add_synapse_slices_from_tile"""
        self.fake_authentication()
        existing_mappings = SynapseSliceSynapseObject.objects.all()
        len(existing_mappings)  # force query to evaluate

        new_ids = self.insert_synapse(0, (0, 3))

        parsed_response = self.agglomerate_synapses(new_ids)

        expected_key = str(new_ids[0])

        self.assertListEqual([expected_key], list(parsed_response['slice_object_mappings']))

        new_mappings = SynapseSliceSynapseObject.objects.filter(synapse_slice_id=new_ids[0])
        self.assertEqual(len(new_mappings), 1)
        self.assertNotIn(new_mappings[0].synapse_object_id, [m.synapse_object_id for m in existing_mappings])

    def test_agglomerate_synapse_slices_two_objects(self):
        """Depends on add_synapse_slices_from_tile and agglomerate_synapse_slices"""
        self.fake_authentication()

        # set up distant syn slice with its own syn object
        # should be identical to test_agglomerate_synapse_slices_separate
        new_ids = self.insert_synapse(0, (0, 3))
        parsed_response = self.agglomerate_synapses(new_ids)
        self.assertEqual(len(parsed_response['slice_object_mappings']), 1)

        # set up a bridge synapse which will force all of them to agglomerate
        new_ids = self.insert_synapse(0, (0, 2))
        parsed_response = self.agglomerate_synapses(new_ids)

        self.assertEqual(len(parsed_response['slice_object_mappings']), 3)  # all 3 existing syn slices are involved in the merge
        self.assertEqual(len(set(parsed_response['slice_object_mappings'].values())), 1)  # they all map to the same synapse object

        # test old mapping was cleared up
        mappings = SynapseSliceSynapseObject.objects.all()
        self.assertEqual(len(mappings), 4)  # there is still only 1 mapping per slice
        self.assertEqual(len({m.synapse_object_id for m in mappings}), 1)  # all mappings point to the same object

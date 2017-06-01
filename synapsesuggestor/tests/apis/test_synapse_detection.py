# -*- coding: utf-8 -*-
import json

from six import assertCountEqual

from synapsesuggestor.tests.apis.common import SynapseSuggestorApiTestCase

URL_PREFIX = '/synapsesuggestor/synapse-detection'


class SynapseDetectionApiTests(SynapseSuggestorApiTestCase):
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

    def test_add_synapse_slices_from_tile(self):
        new_synapses = [
            {
                'id': 1,
                'wkt_str': 'MULTIPOINT(0 0, 1 0, 1 1, 0 1)',
                'xs_centroid': 0,
                'ys_centroid': 0,
                'size_px': 50,
                'uncertainty': 0.5
            },
            {
                'id': 2,
                'wkt_str': 'MULTIPOINT(1 0, 2 0, 2 1, 1 1)',
                'xs_centroid': 1,
                'ys_centroid': 1,
                'size_px': 50,
                'uncertainty': 0.5
            },
        ]

        orig_ids = [syn['id'] for syn in new_synapses]

        data = {
            'workflow_id': self.test_ssw_id,
            'x_idx': 0,
            'y_idx': 0,
            'z_idx': 1,
            'synapse_slices': [json.dumps(syn) for syn in new_synapses]
        }

        response = self.client.post(URL_PREFIX + '/tiles/insert-synapse-slices', data)
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))
        print(parsed_response)

        self.assertEqual(len(new_synapses), len(parsed_response))
        self.assertSetEqual(set(orig_ids), set(parsed_response))
        self.assertEqual(len(parsed_response), set(parsed_response.values()), 'New synapse IDs are repeated')

    def test_agglomerate_synapse_slices(self):
        pass

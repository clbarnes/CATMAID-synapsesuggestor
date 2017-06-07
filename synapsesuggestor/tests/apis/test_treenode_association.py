# -*- coding: utf-8 -*-
import json

from six import assertCountEqual

from synapsesuggestor.tests.common import SynapseSuggestorTestCase


URL_PREFIX = '/synapsesuggestor/treenode-association'


class TreenodeAssociationApiTests(SynapseSuggestorTestCase):
    def get_response(self, *args, **kwargs):
        response = self.client.get(*args, **kwargs)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content.decode('utf-8'))

    def test_get_treenode_associations(self):
        synapse_obj_id = 1

        self.fake_authentication()
        parsed_response = self.get_response(
            URL_PREFIX + '/{}/get'.format(self.test_project_id),
            {'skid': self.test_skeleton_id}
        )
        expected_result = [[self.test_treenode_id, synapse_obj_id, 5]]

        self.assertListEqual(expected_result, parsed_response)

    def test_get_treenode_associations_empty(self):
        other_skid = 235

        self.fake_authentication()
        parsed_response = self.get_response(
            URL_PREFIX + '/{}/get'.format(self.test_project_id),
            {'skid': other_skid}
        )

        self.assertListEqual([], parsed_response)

    def test_add_treenode_synapse_associations(self):
        syn_slice_ids = [2, 3]
        syn_obj_id = 1
        other_skid = 235
        other_tns = [237, 239]
        contact_px = 10

        associations = [
            json.dumps([syn_slice_id, other_tn, contact_px])
            for syn_slice_id, other_tn in zip(syn_slice_ids, other_tns)
        ]

        self.fake_authentication()
        response = self.client.post(
            URL_PREFIX + '/{}/add'.format(self.test_project_id),
            {'algo_version': 1, 'associations': associations}
        )
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(parsed_response), 2)

        parsed_response = self.get_response(
            URL_PREFIX + '/{}/get'.format(self.test_project_id),
            {'skid': other_skid}
        )

        expected_result = [[other_tn, syn_obj_id, contact_px] for other_tn in other_tns]

        assertCountEqual(self, expected_result, parsed_response)

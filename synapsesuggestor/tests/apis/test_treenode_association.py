# -*- coding: utf-8 -*-
import json

from six import assertCountEqual

from synapsesuggestor.tests.common import SynapseSuggestorTestCase


URL_PREFIX = '/ext/synapsesuggestor/treenode-association'

SYN_SLICE_NEAR_SKEL_COLS = ['skeleton_id', 'treenode_id', 'synapse_object_id', 'synapse_slice_ids', 'synapse_z_s',
               'synapse_bounds_s']

def stack_to_project(translation, resolution, coords_s):
    """Convert a dictionary of stack coordinates into a dictionary of project coordinates"""
    return {dim: val * resolution[dim] + translation[dim] for dim, val in coords_s.items()}


def project_to_stack(translation, resolution, coords_p):
    """Convert a dictionary of project coordinates into a dictionary of stack coordinates"""
    return {dim: int(val - translation[dim] / resolution[dim]) for dim, val in coords_p.items()}


def stack_distance_to_project(resolution, distance_s):
    assert resolution['x'] == resolution['y'], 'Resolution is XY anisotropic'
    return distance_s * resolution['x']


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
            {'project_workflow_id': self.test_pssw_id, 'associations': associations}
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

    def _get_stack_info(self):
        stack_response = self.client.get(
            '/{}/stack/{}/info'.format(self.test_project_id, self.test_stack_id),
        )
        self.assertEqual(stack_response.status_code, 200)
        return json.loads(stack_response.content.decode('utf-8'))

    def _create_treenodes(self, coords_s, parent_id=-1):
        if isinstance(coords_s, dict):
            coords_s = [coords_s]

        stack_info = self._get_stack_info()

        treenode_ids = []
        skid = None

        for coord_s_dict in coords_s:
            coords_p = stack_to_project(stack_info['translation'], stack_info['resolution'], coord_s_dict)

            response = self.client.post(
                '/{}/treenode/create'.format(self.test_project_id),
                {
                    'x': coords_p['x'],
                    'y': coords_p['y'],
                    'z': coords_p['z'],
                    'parent_id': parent_id
                }
            )
            self.assertEqual(response.status_code, 200)
            treenode_info = json.loads(response.content.decode('utf-8'))
            treenode_ids.append(treenode_info['treenode_id'])
            assert skid is None or skid == treenode_info['skeleton_id'], 'Inconsistent skeleton ID'
            skid = treenode_info['skeleton_id']

        return {
            'treenode_ids': treenode_ids, 'skeleton_id': skid,
            'resolution': stack_info['resolution'], 'translation': stack_info['translation']
        }

    def test_get_synapse_slices_near_skeleton_single(self):
        self.fake_authentication()
        distance_s = 1

        treenodes_info = self._create_treenodes({'x': 2.5, 'y': 0.5, 'z': 0})
        distance_p = stack_distance_to_project(treenodes_info['resolution'], distance_s)

        params = {'skid': treenodes_info['skeleton_id'], 'pssw_id': self.test_pssw_id, 'distance': distance_p}
        response = self.client.get(URL_PREFIX + '/{}/get-distance'.format(self.test_project_id), params)
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))

        expected_response = {
            'columns': SYN_SLICE_NEAR_SKEL_COLS,
            'data': [
                [treenodes_info['skeleton_id'], treenodes_info['treenode_ids'][0], 1, [2, 3], 0, [0.0, 0.0, 2.0, 1.0]]
            ]
        }

        self.assertDictEqual(parsed_response, expected_response)

    def test_get_synapse_slices_near_skeleton_multi(self):
        self.fake_authentication()
        distance_s = 1

        treenodes_info = self._create_treenodes({'x': 1, 'y': 1.5, 'z': 0})
        distance_p = stack_distance_to_project(treenodes_info['resolution'], distance_s)

        params = {'skid': treenodes_info['skeleton_id'], 'pssw_id': self.test_pssw_id, 'distance': distance_p}
        response = self.client.get(URL_PREFIX + '/{}/get-distance'.format(self.test_project_id), params)
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))

        expected_response = {
            'columns': SYN_SLICE_NEAR_SKEL_COLS,
            'data': [
                [treenodes_info['skeleton_id'], treenodes_info['treenode_ids'][0], 1, [2, 3], 0, [0.0, 0.0, 2.0, 1.0]]
            ]
        }

        self.assertDictEqual(parsed_response, expected_response)

    def test_get_synapse_slices_near_skeleton_offset_z(self):
        self.fake_authentication()
        distance_s = 1

        treenodes_info = self._create_treenodes({'x': 1, 'y': 1.5, 'z': 1})
        distance_p = stack_distance_to_project(treenodes_info['resolution'], distance_s)
        params = {'skid': treenodes_info['skeleton_id'], 'pssw_id': self.test_pssw_id, 'distance': distance_p}
        response = self.client.get(URL_PREFIX + '/{}/get-distance'.format(self.test_project_id), params)
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))

        expected_response = {
            'columns': SYN_SLICE_NEAR_SKEL_COLS,
            'data': []
        }

        self.assertDictEqual(parsed_response, expected_response)

    def test_get_synapse_slices_near_skeleton_too_far(self):
        self.fake_authentication()
        distance_s = 1

        treenodes_info = self._create_treenodes({'x': 10, 'y': 1.5, 'z': 0})
        distance_p = stack_distance_to_project(treenodes_info['resolution'], distance_s)
        params = {'skid': treenodes_info['skeleton_id'], 'pssw_id': self.test_pssw_id, 'distance': distance_p}
        response = self.client.get(URL_PREFIX + '/{}/get-distance'.format(self.test_project_id), params)
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))

        expected_response = {
            'columns': SYN_SLICE_NEAR_SKEL_COLS,
            'data': []
        }

        self.assertDictEqual(parsed_response, expected_response)

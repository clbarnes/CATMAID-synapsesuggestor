# -*- coding: utf-8 -*-
import json

import numpy as np

from catmaid.models import ProjectStack, Connector, Relation
from catmaid.control.treenode import _create_treenode, create_connector_link
from synapsesuggestor.tests.common import SynapseSuggestorTestCase

URL_PREFIX = '/synapsesuggestor/analysis'


class AnalysisApiTests(SynapseSuggestorTestCase):
    inside_ss_2 = (0.5, 0.5, 0)
    inside_ss_3 = (1.5, 0.5, 0)

    outside_ss = (1, 3, 0)

    test_syn_obj_id = 1

    def skeleton_synapses(self, ssw_id=None, skid=None):
        params = dict()
        if ssw_id is not None:
            params['workflow_id'] = ssw_id
        if skid is not None:
            params['skeleton_id'] = skid

        response = self.client.get(URL_PREFIX + '/{}/skeleton-synapses'.format(self.test_project_id), params)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content.decode('utf-8'))

    def test_skeleton_synapses_successful(self):
        self.fake_authentication()
        parsed_response = self.skeleton_synapses(self.test_ssw_id, self.test_skeleton_id)

        expected_response = {
            "columns": [
                'synapse', 'nodes', 'skeleton_id',
                'xs', 'ys', 'zs', 'z_slices',
                'size_px', 'contact_px', 'uncertainty_avg'
            ],
            "data": [[1, [self.test_treenode_id], self.test_skeleton_id, 0, 0, 0, [0], 50, 5, 0.5]]
        }

        self.assertDictEqual(expected_response, parsed_response)

    def create_treenode_connector(
        self, treenode_xyz_s, connector_xyz_s, relation_name='presynaptic_to', stack_id=None,
        project_id=None
    ):
        """

        Args:
            treenode_xyz_s(tuple):  In stack space, the XYZ coordinates of the treenode
            connector_xyz_s(tuple):  In stack space, the XYZ coordinates of the connector node
            relation_name(str):  Should be 'presynaptic_to' or 'postsynaptic_to'
            stack_id(int):
            project_id(int):

        Returns:

        """
        if stack_id is None:
            stack_id = self.test_stack_id
        if project_id is None:
            project_id = self.test_project_id

        confidence = 0

        ps = ProjectStack.objects.get(project_id=project_id, stack_id=stack_id)

        relation = Relation.objects.get(project_id=project_id, relation_name=relation_name)

        translation = np.array([getattr(ps.translation, dim) for dim in 'xyz'])
        resolution = np.array([getattr(ps.stack.resolution, dim) for dim in 'xyz'])

        treenode_xyz_p = np.array(treenode_xyz_s) * resolution + translation
        connector_xyz_p = np.array(connector_xyz_s) * resolution + translation

        new_treenode = _create_treenode(
            project_id, self.test_user, self.test_user,
            treenode_xyz_p[0], treenode_xyz_p[1], treenode_xyz_p[2],
            0, confidence, -1, -1, None
        )

        new_connector = Connector.objects.create(
            user=self.test_user,
            editor=self.test_user,
            project=ps.project,
            location_x=connector_xyz_p[0],
            location_y=connector_xyz_p[1],
            location_z=connector_xyz_p[2],
            confidence=confidence
        )

        created_links = create_connector_link(
            project_id, self.test_user.id, new_treenode.treenode_id, new_treenode.skeleton_id,
            [[new_connector.id, relation.id, confidence]]
        )

        return {
            'treenode_id': new_treenode.treenode_id,
            'skeleton_id': new_treenode.skeleton_id,
            'connector_id': new_connector.id,
            'relation_name': relation_name
        }

    def get_intersecting_connectors(self, obj_ids=None, workflow_id=None):
        data = dict()
        if obj_ids is not None:
            data['synapse_object_ids'] = list(obj_ids)
        if workflow_id is not None:
            data['workflow_id'] = workflow_id

        response = self.client.post(URL_PREFIX + '/{}/intersecting-connectors'.format(self.test_project_id), data)
        self.assertEqual(response.status_code, 200)
        parsed_response = json.loads(response.content.decode('utf-8'))

        if parsed_response['data']:
            self.assertEqual(len(parsed_response['columns']), len(parsed_response['data'][0]))

        return parsed_response

    def test_intersecting_connectors_successful(self):
        self.fake_authentication()
        tc_info = self.create_treenode_connector(self.outside_ss, self.inside_ss_2)

        parsed_response = self.get_intersecting_connectors([self.test_syn_obj_id], self.test_ssw_id)

        self.assertEqual(len(parsed_response['data']), 1)

        response_dict = dict(zip(parsed_response['columns'], parsed_response['data'][0]))

        self.assertEqual(response_dict['synapse_id'], self.test_syn_obj_id)
        self.assertEqual(response_dict['connector_id'], tc_info['connector_id'])
        self.assertEqual(response_dict['treenode_id'], tc_info['treenode_id'])
        self.assertEqual(response_dict['skeleton_id'], tc_info['skeleton_id'])

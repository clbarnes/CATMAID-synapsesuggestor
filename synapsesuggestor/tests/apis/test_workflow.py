# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json

from synapsesuggestor.models import (
    SynapseSuggestionWorkflow, SynapseDetectionAlgorithm, SynapseDetectionTiling,
    ProjectSynapseSuggestionWorkflow, SynapseAssociationAlgorithm
)
from synapsesuggestor.tests.common import SynapseSuggestorTestCase

URL_PREFIX = '/ext/synapsesuggestor'


class WorkflowApiTests(SynapseSuggestorTestCase):
    def get_workflow(self, stack_id, tile_size, detection_hash):
        params = {'stack_id': stack_id, 'tile_size': tile_size, 'detection_hash': detection_hash}
        response = self.client.get(URL_PREFIX + '/synapse-detection/workflow', params)
        self.assertEqual(response.status_code, 200)

        return json.loads(response.content.decode('utf-8'))

    def get_project_workflow(self, workflow_id, association_hash, project_id=None):
        if project_id is None:
            project_id = self.test_project_id
        params = {'workflow_id': workflow_id, 'association_hash': association_hash}
        response = self.client.get(URL_PREFIX + '/treenode-association/{}/workflow'.format(project_id), params)
        self.assertEqual(response.status_code, 200)

        return json.loads(response.content.decode('utf-8'))

    def test_get_workflow_exists(self):
        self.fake_authentication()
        tiling_count = SynapseDetectionTiling.objects.count()
        det_algo_count = SynapseDetectionAlgorithm.objects.count()

        parsed_response = self.get_workflow(3, 512, '0')

        expected_response = {
            'tile_size': {'height_px': 512, 'width_px': 512},
            'workflow_id': 1,
            'detection_algorithm_id': 1
        }

        self.assertDictContainsSubset(expected_response, parsed_response)

        new_tiling_count = SynapseDetectionTiling.objects.count()
        self.assertEqual(tiling_count, new_tiling_count)
        new_det_algo_count = SynapseDetectionAlgorithm.objects.count()
        self.assertEqual(det_algo_count, new_det_algo_count)

    def test_get_workflow_not_exists(self):
        """New tiling, algorithm and workflow"""
        self.fake_authentication()

        tiling_count = SynapseDetectionTiling.objects.count()
        det_algo_count = SynapseDetectionAlgorithm.objects.count()
        workflow_count = SynapseSuggestionWorkflow.objects.count()

        parsed_response = self.get_workflow(3, 256, 'not_an_existing_hash')

        expected_response = {
            'tile_size': {'height_px': 256, 'width_px': 256},
        }

        self.assertDictContainsSubset(expected_response, parsed_response)

        new_tiling_count = SynapseDetectionTiling.objects.count()
        self.assertEqual(tiling_count + 1, new_tiling_count)
        new_det_algo_count = SynapseDetectionAlgorithm.objects.count()
        self.assertEqual(det_algo_count + 1, new_det_algo_count)
        new_workflow_count = SynapseSuggestionWorkflow.objects.count()
        self.assertEqual(workflow_count + 1, new_workflow_count)

    def test_get_workflow_bump_algo(self):
        """New algorithm and workflow"""
        self.fake_authentication()

        tiling_count = SynapseDetectionTiling.objects.count()
        det_algo_count = SynapseDetectionAlgorithm.objects.count()
        workflow_count = SynapseSuggestionWorkflow.objects.count()

        parsed_response = self.get_workflow(3, 512, 'not_an_existing_hash')

        expected_response = {
            'tile_size': {'height_px': 512, 'width_px': 512},
        }

        self.assertDictContainsSubset(expected_response, parsed_response)

        new_tiling_count = SynapseDetectionTiling.objects.count()
        self.assertEqual(tiling_count, new_tiling_count)
        new_det_algo_count = SynapseDetectionAlgorithm.objects.count()
        self.assertEqual(det_algo_count + 1, new_det_algo_count)
        new_workflow_count = SynapseSuggestionWorkflow.objects.count()
        self.assertEqual(workflow_count + 1, new_workflow_count)

    def test_get_workflow_new_tiling(self):
        """New tiling and workflow"""
        self.fake_authentication()

        tiling_count = SynapseDetectionTiling.objects.count()
        det_algo_count = SynapseDetectionAlgorithm.objects.count()
        workflow_count = SynapseSuggestionWorkflow.objects.count()

        parsed_response = self.get_workflow(3, 256, '0')

        expected_response = {
            'tile_size': {'height_px': 256, 'width_px': 256},
            'detection_algorithm_id': 1
        }

        self.assertDictContainsSubset(expected_response, parsed_response)

        new_tiling_count = SynapseDetectionTiling.objects.count()
        self.assertEqual(tiling_count + 1, new_tiling_count)
        new_det_algo_count = SynapseDetectionAlgorithm.objects.count()
        self.assertEqual(det_algo_count, new_det_algo_count)
        new_workflow_count = SynapseSuggestionWorkflow.objects.count()
        self.assertEqual(workflow_count + 1, new_workflow_count)

    def test_get_project_workflow_exists(self):
        self.fake_authentication()

        project_workflow_count = ProjectSynapseSuggestionWorkflow.objects.count()
        assoc_algo_count = SynapseAssociationAlgorithm.objects.count()

        parsed_response = self.get_project_workflow(1, '0')

        expected_response = {
            'association_algorithm_id': 1,
            'project_workflow_id': 1
        }

        self.assertDictEqual(expected_response, parsed_response)

        new_project_workflow_count = ProjectSynapseSuggestionWorkflow.objects.count()
        self.assertEqual(project_workflow_count, new_project_workflow_count)
        new_assoc_algo_count = SynapseAssociationAlgorithm.objects.count()
        self.assertEqual(assoc_algo_count, new_assoc_algo_count)

    def test_get_project_workflow_not_exists(self):
        """Depends on get_workflow"""
        self.fake_authentication()

        project_workflow_count = ProjectSynapseSuggestionWorkflow.objects.count()
        assoc_algo_count = SynapseAssociationAlgorithm.objects.count()

        new_workflow_info = self.get_workflow(3, 512, 'not an existing hash')

        parsed_response = self.get_project_workflow(new_workflow_info['workflow_id'], 'not an algorithm')

        incorrect_response = {
            'association_algorithm_id': 1,
            'project_workflow_id': 1
        }

        self.assertNotEqual(incorrect_response['association_algorithm_id'], parsed_response['association_algorithm_id'])
        self.assertNotEqual(incorrect_response['project_workflow_id'], parsed_response['project_workflow_id'])

        new_project_workflow_count = ProjectSynapseSuggestionWorkflow.objects.count()
        self.assertEqual(project_workflow_count + 1, new_project_workflow_count)
        new_assoc_algo_count = SynapseAssociationAlgorithm.objects.count()
        self.assertEqual(assoc_algo_count + 1, new_assoc_algo_count)

    def test_get_project_workflow_new_algorithm(self):
        self.fake_authentication()

        project_workflow_count = ProjectSynapseSuggestionWorkflow.objects.count()
        assoc_algo_count = SynapseAssociationAlgorithm.objects.count()

        parsed_response = self.get_project_workflow(1, 'not an algorithm')

        incorrect_response = {
            'association_algorithm_id': 1,
            'project_workflow_id': 1
        }

        self.assertNotEqual(incorrect_response['association_algorithm_id'], parsed_response['association_algorithm_id'])
        self.assertNotEqual(incorrect_response['project_workflow_id'], parsed_response['project_workflow_id'])

        new_project_workflow_count = ProjectSynapseSuggestionWorkflow.objects.count()
        self.assertEqual(project_workflow_count + 1, new_project_workflow_count)
        new_assoc_algo_count = SynapseAssociationAlgorithm.objects.count()
        self.assertEqual(assoc_algo_count + 1, new_assoc_algo_count)

    def test_get_project_workflow_new_project(self):
        self.fake_authentication()

        project_workflow_count = ProjectSynapseSuggestionWorkflow.objects.count()
        assoc_algo_count = SynapseAssociationAlgorithm.objects.count()

        parsed_response = self.get_project_workflow(1, '0', 2)

        self.assertEqual(1, parsed_response['association_algorithm_id'])
        self.assertNotEqual(1, parsed_response['project_workflow_id'])

        new_project_workflow_count = ProjectSynapseSuggestionWorkflow.objects.count()
        self.assertEqual(project_workflow_count + 1, new_project_workflow_count)
        new_assoc_algo_count = SynapseAssociationAlgorithm.objects.count()
        self.assertEqual(assoc_algo_count, new_assoc_algo_count)

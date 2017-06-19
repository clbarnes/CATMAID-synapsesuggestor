# -*- coding: utf-8 -*-
import json

from synapsesuggestor.tests.common import SynapseSuggestorTestCase

URL_PREFIX = '/synapsesuggestor/analysis'


class AnalysisApiTests(SynapseSuggestorTestCase):
    def slices_detail(self, ssw_id=None, skids=None):
        params = dict()
        if ssw_id is not None:
            params['workflow_id'] = ssw_id
        if skids is not None:
            params['skeleton_ids'] = skids

        response = self.client.get(URL_PREFIX + '/{}/slices-detail'.format(self.test_project_id), params)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content.decode('utf-8'))

    def test_successful_result(self):
        self.fake_authentication()
        parsed_response = self.slices_detail(self.test_ssw_id, [self.test_skeleton_id])

        expected_response = {
          "columns": ["slice", "object", "node", "skeleton", "xs", "ys", "zs", "size", "uncertainty"],
          "data": [[2, 1, 7, 1, 0, 0, 0, 50, 0.5]]
        }

        self.assertDictEqual(expected_response, parsed_response)

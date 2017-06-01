# -*- coding: utf-8 -*-
from catmaid.tests.apis.common import CatmaidApiTestCase


class SynapseSuggestorApiTestCase(CatmaidApiTestCase):
    fixtures = CatmaidApiTestCase.fixtures + ['synapsesuggestor_testdata']

    @classmethod
    def setUpTestData(cls):
        super(SynapseSuggestorApiTestCase, cls).setUpTestData()
        cls.test_ssw_id = 1
        cls.test_treenode_id = 7
        cls.test_skeleton_id = 1

# -*- coding: utf-8 -*-
from catmaid.tests.apis.common import CatmaidApiTestCase


class SynapseSuggestorTestCase(CatmaidApiTestCase):
    fixtures = CatmaidApiTestCase.fixtures + ['synapsesuggestor_testdata.json']

    @classmethod
    def setUpTestData(cls):
        super(SynapseSuggestorTestCase, cls).setUpTestData()
        cls.test_ssw_id = 1
        cls.test_pssw_id = 1
        cls.test_treenode_id = 7
        cls.test_skeleton_id = 1
        cls.test_stack_id = 3

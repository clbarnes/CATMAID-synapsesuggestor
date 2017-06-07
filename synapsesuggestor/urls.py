# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url

from synapsesuggestor.control import (treenode_association as node_assoc, synapse_detection as syn_det, workflow)

app_name = 'synapsesuggestor'

urlpatterns = []

# synapse detection endpoints

urlpatterns += [
    url(r'^synapse-detection/tiles/detected$', syn_det.get_detected_tiles),
    url(r'^synapse-detection/tiles/insert-synapse-slices$', syn_det.add_synapse_slices_from_tile),
    url(r'^synapse-detection/slices/agglomerate$', syn_det.agglomerate_synapse_slices),
    url(r'^synapse-detection/workflow$', workflow.get_workflow),
]

# treenode association endpoints

urlpatterns += [
    url(r'^treenode-association/(?P<project_id>\d+)/get$', node_assoc.get_treenode_associations),
    url(r'^treenode-association/(?P<project_id>\d+)/add$', node_assoc.add_treenode_synapse_associations),
    url(r'^treenode-association/(?P<project_id>\d+)/workflow', workflow.get_project_workflow),
]

# workflow endpoints


# analysis endpoints

urlpatterns += [

]

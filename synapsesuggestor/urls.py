# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url

from synapsesuggestor.control import (
    treenode_association as node_assoc, synapse_detection as syn_det, workflow, analysis, training_data
)

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

# algorithms endpoints

urlpatterns += [
    url(r'^algorithms/(?P<project_id>\d+)$', node_assoc.get_treenode_associations),
]

# analysis endpoints

urlpatterns += [
    url(r'^analysis/(?P<project_id>\d+)/skeleton-synapses$', analysis.get_skeleton_synapses),
    url(r'^analysis/(?P<project_id>\d+)/intersecting-connectors$', analysis.get_intersecting_connectors),
    url(r'^analysis/(?P<project_id>\d+)/workflow-info$', workflow.get_workflow_info),
    url(r'^analysis/synapse-extents', analysis.get_synapse_extents),
]

# training data endpoints

urlpatterns += [
    url(r'^training-data/(?P<project_id>\d+)/treenodes/sample$', training_data.sample_treenodes),
    url(r'^training-data/(?P<project_id>\d+)/treenodes/label$', training_data.treenodes_by_label)
]

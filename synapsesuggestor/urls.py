# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf.urls import url

from synapsesuggestor.control import (treenode_association as node_assoc, synapse_detection as syn_det, common)

# common

urlpatterns = [
    url('^algo-version$', common.get_or_create_algo_version)
]

# synapse detection endpoints

urlpatterns += [
    url('^synapsedetection/', syn_det.)
]

# treenode association endpoints

urlpatterns += [
    url('^treenodeassociation/', node_assoc.)
]

# analysis endpoints

urlpatterns += [

]

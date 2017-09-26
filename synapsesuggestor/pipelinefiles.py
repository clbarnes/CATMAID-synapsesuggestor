# -*- coding: utf-8 -*-
from __future__ import unicode_literals

"""Specifies static assets (CSS, JS) required by the CATMAID front-end.

This module specifies all the static files that are required by the
synapsesuggestor front-end.
"""

from collections import OrderedDict

JAVASCRIPT = OrderedDict()

JAVASCRIPT['synapsesuggestor'] = {
    'source_filenames': (
        'synapsesuggestor/js/widgets/synapse-detection-table.js',
    ),
    'output_filename': 'js/synapsesuggestor.js'
}

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.contrib.gis.db import models as spatial_models

from catmaid.models import Treenode, Stack, StackMirror, Project


class SynapseObject(models.Model):
    """3D synapse object"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    class Meta:
        db_table = 'synapse_object'


class SynapseSuggestionAlgorithm(models.Model):
    """Algorithm used to detect synapses and associate them with skeletons, with version information"""
    hashcode = models.CharField(max_length=64, db_index=True, unique=True)
    date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'synapse_suggestion_algorithm'


class SynapseDetectionTiling(models.Model):
    """Information about how to tile the raw image stack"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    stack = models.ForeignKey(Stack, on_delete=models.CASCADE)

    tile_height_px = models.IntegerField(default=512)
    tile_width_px = models.IntegerField(default=512)

    class Meta:
        db_table = 'synapse_detection_tiling'
        unique_together = ('stack', 'project')


class SynapseSuggestionTile(models.Model):
    """Mapping from tile indices to algorithm which has most recently been used to detect synapses in that tile"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    x_tile_idx = models.IntegerField(db_index=True)
    y_tile_idx = models.IntegerField(db_index=True)
    z_tile_idx = models.IntegerField(db_index=True)

    synapse_detection_tiling = models.ForeignKey(SynapseDetectionTiling, on_delete=models.CASCADE)

    synapse_suggestion_algorithm = models.ForeignKey(SynapseSuggestionAlgorithm, null=True, on_delete=models.CASCADE)

    # pixel_classification_stack = models.ForeignKey(Stack, null=True, on_delete=models.CASCADE)
    # label_stack = models.ForeignKey(Stack, null=True, on_delete=models.CASCADE)

    class Meta:
        db_table = 'tile_synapse_suggestion_algorithm'
        # todo: uniqueness constraint


class SynapseSlice(models.Model):
    """Region of a 2D cross-section of a synapse which appears in one tile"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    synapse_suggestion_tile = models.ForeignKey(SynapseSuggestionTile, on_delete=models.CASCADE)

    convex_hull_2d = spatial_models.PolygonField()
    size_px = models.IntegerField()

    xs_centroid = models.IntegerField(verbose_name='x coord of centroid in stack coordinates')
    ys_centroid = models.IntegerField(verbose_name='y coord of centroid in stack coordinates')

    uncertainty = models.FloatField(null=True)
    # date?
    # user?

    class Meta:
        db_table = 'synapse_slice'


class SynapseSliceSynapseObject(models.Model):
    """Mapping from 2D partial synapse cross-sections to whole 3D synapse objects"""
    synapse_slice = models.OneToOneField(SynapseSlice, unique=True, on_delete=models.CASCADE)
    synapse_object = models.ForeignKey(SynapseObject, on_delete=models.CASCADE)

    class Meta:
        db_table = 'synapse_slice_synapse_object'


class SynapseSliceTreenode(models.Model):
    """Mapping from 2D partial synapse cross-sections to treenodes"""
    synapse_slice = models.ForeignKey(SynapseSlice, on_delete=models.CASCADE)
    treenode = models.ForeignKey(Treenode, on_delete=models.CASCADE)

    synapse_suggestion_algorithm = models.ForeignKey(SynapseSuggestionAlgorithm, on_delete=models.CASCADE)
    contact_px = models.IntegerField(verbose_name='Size in pixels of 1D contact area between neuron and synapse')

    # contact geometry?

    class Meta:
        db_table = 'synapse_slice_treenode'

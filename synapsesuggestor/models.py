# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.contrib.gis.db import models as spatial_models

from catmaid.models import Treenode, Stack, StackMirror, Project


class SynapseDetectionTiling(models.Model):
    """Information about how to tile the raw image stack"""
    stack = models.ForeignKey(Stack, on_delete=models.CASCADE)

    tile_height_px = models.IntegerField(default=512)
    tile_width_px = models.IntegerField(default=512)

    class Meta:
        db_table = 'synapse_detection_tiling'
        unique_together = ('stack', 'tile_height_px', 'tile_width_px')


class Algorithm(models.Model):
    """Abstract model for algorithms"""
    hashcode = models.CharField(max_length=64, db_index=True)
    date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        abstract = True


class SynapseDetectionAlgorithm(Algorithm):
    """Algorithm used for classifying pixels and pulling out synapse slices from them"""
    class Meta:
        db_table = 'synapse_detection_algorithm'


class SynapseImageStore(models.Model):
    """Data store used for intermediate and output pixel labels"""
    pass


class SynapseSuggestionWorkflow(models.Model):
    """Convergence point for information relating to synapse detection"""
    synapse_detection_tiling = models.ForeignKey(SynapseDetectionTiling, on_delete=models.CASCADE)
    synapse_detection_algorithm = models.ForeignKey(SynapseDetectionAlgorithm, on_delete=models.CASCADE)

    # null when obsolete
    synapse_image_store = models.OneToOneField(SynapseImageStore, null=True, default=None, unique=True)

    class Meta:
        db_table = 'synapse_suggestion_workflow'
        unique_together = ('synapse_detection_tiling', 'synapse_detection_algorithm')


class SynapseDetectionTile(models.Model):
    """Mapping from tile indices to algorithm which has most recently been used to detect synapses in that tile"""
    synapse_suggestion_workflow = models.ForeignKey(SynapseSuggestionWorkflow, on_delete=models.CASCADE)

    # todo: replace with Integer3DField?
    x_tile_idx = models.IntegerField(db_index=True)
    y_tile_idx = models.IntegerField(db_index=True)
    z_tile_idx = models.IntegerField(db_index=True)

    class Meta:
        db_table = 'synapse_detection_tile'
        unique_together = ('synapse_suggestion_workflow', 'x_tile_idx', 'y_tile_idx', 'z_tile_idx')


class SynapseSlice(models.Model):
    """Region of a 2D cross-section of a synapse which appears in one tile"""
    synapse_detection_tile = models.ForeignKey(SynapseDetectionTile, on_delete=models.CASCADE)

    convex_hull_2d = spatial_models.PolygonField()
    size_px = models.IntegerField()

    xs_centroid = models.IntegerField(verbose_name='x coord of centroid in stack coordinates')
    ys_centroid = models.IntegerField(verbose_name='y coord of centroid in stack coordinates')

    uncertainty = models.FloatField(null=True)
    # date?
    # user?

    class Meta:
        db_table = 'synapse_slice'


class SynapseObject(models.Model):
    """3D synapse object"""

    class Meta:
        db_table = 'synapse_object'


class SynapseSliceSynapseObject(models.Model):
    """Mapping from 2D partial synapse cross-sections to whole 3D synapse objects"""
    synapse_slice = models.OneToOneField(SynapseSlice, unique=True, on_delete=models.CASCADE)
    synapse_object = models.ForeignKey(SynapseObject, on_delete=models.CASCADE)

    class Meta:
        db_table = 'synapse_slice_synapse_object'


class SynapseAssociationAlgorithm(Algorithm):
    """
    Algorithm for associating synapse slices with treenodes.
    
    In v1, this must be bumped every time the synapse detection algorithm is bumped as it depends on the pixel 
    predictions.
    """

    class Meta:
        db_table = 'synapse_association_algorithm'


class ProjectSynapseSuggestionWorkflow(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    synapse_suggestion_workflow = models.ForeignKey(SynapseSuggestionWorkflow, on_delete=models.CASCADE)
    synapse_association_algorithm = models.ForeignKey(SynapseAssociationAlgorithm, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_synapse_suggestion_workflow'


class SynapseSliceTreenode(models.Model):
    """Mapping from 2D partial synapse cross-sections to treenodes"""
    synapse_slice = models.ForeignKey(SynapseSlice, on_delete=models.CASCADE, null=True)
    treenode = models.ForeignKey(Treenode, on_delete=models.CASCADE)

    synapse_association_algorithm = models.ForeignKey(SynapseAssociationAlgorithm, on_delete=models.CASCADE)
    contact_px = models.IntegerField(verbose_name='Size in pixels of 1D contact area between neuron and synapse')

    # contact geometry?

    class Meta:
        db_table = 'synapse_slice_treenode'

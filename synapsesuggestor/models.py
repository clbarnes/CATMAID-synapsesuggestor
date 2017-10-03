# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.contrib.gis.db import models as spatial_models
from django.utils.encoding import python_2_unicode_compatible

from catmaid.models import Treenode, Stack, StackMirror, Project


@python_2_unicode_compatible
class SynapseDetectionTiling(models.Model):
    """Information about how to tile the raw image stack"""
    stack = models.ForeignKey(Stack, on_delete=models.CASCADE)

    tile_height_px = models.IntegerField(default=512)
    tile_width_px = models.IntegerField(default=512)

    def __str__(self):
        return '{} ({}x{})'.format(self.stack.title, self.tile_width_px, self.tile_height_px)

    class Meta:
        db_table = 'synapse_detection_tiling'
        unique_together = ('stack', 'tile_height_px', 'tile_width_px')


@python_2_unicode_compatible
class Algorithm(models.Model):
    """Abstract model for algorithms"""
    hashcode = models.CharField(max_length=64, db_index=True)
    date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return 'Hash: {} ({})'.format(self.hashcode, self.date)

    class Meta:
        abstract = True


class SynapseDetectionAlgorithm(Algorithm):
    """Algorithm used for classifying pixels and pulling out synapse slices from them"""

    class Meta:
        db_table = 'synapse_detection_algorithm'


class SynapseImageStore(models.Model):
    """Data store used for intermediate and output pixel labels"""

    class Meta:
        db_table = 'synapse_image_store'


@python_2_unicode_compatible
class SynapseSuggestionWorkflow(models.Model):
    """Convergence point for information relating to synapse detection"""
    synapse_detection_tiling = models.ForeignKey(SynapseDetectionTiling, on_delete=models.CASCADE)
    synapse_detection_algorithm = models.ForeignKey(SynapseDetectionAlgorithm, on_delete=models.CASCADE)

    # null when obsolete
    synapse_image_store = models.OneToOneField(SynapseImageStore, null=True, default=None, unique=True)

    def __str__(self):
        return '{}{}'.format(self.id, '' if self.synapse_image_store else ' (read-only)')

    class Meta:
        db_table = 'synapse_suggestion_workflow'
        unique_together = ('synapse_detection_tiling', 'synapse_detection_algorithm')


@python_2_unicode_compatible
class SynapseDetectionTile(models.Model):
    """Mapping from tile indices to algorithm which has most recently been used to detect synapses in that tile"""
    synapse_suggestion_workflow = models.ForeignKey(SynapseSuggestionWorkflow, on_delete=models.CASCADE)

    # todo: replace with Integer3DField?
    x_tile_idx = models.IntegerField(db_index=True)
    y_tile_idx = models.IntegerField(db_index=True)
    z_tile_idx = models.IntegerField(db_index=True)

    def __str__(self):
        return 'x{}y{}z{} in {}'.format(
            self.x_tile_idx, self.y_tile_idx, self.z_tile_idx, self.synapse_suggestion_workflow
        )

    class Meta:
        db_table = 'synapse_detection_tile'
        unique_together = ('synapse_suggestion_workflow', 'x_tile_idx', 'y_tile_idx', 'z_tile_idx')


@python_2_unicode_compatible
class SynapseSlice(models.Model):
    """Region of a 2D cross-section of a synapse which appears in one tile"""
    synapse_detection_tile = models.ForeignKey(SynapseDetectionTile, on_delete=models.CASCADE)

    geom_2d = spatial_models.PolygonField(srid=0, spatial_index=True)
    size_px = models.IntegerField()

    xs_centroid = models.IntegerField(verbose_name='x coord of centroid in stack coordinates')
    ys_centroid = models.IntegerField(verbose_name='y coord of centroid in stack coordinates')

    uncertainty = models.FloatField(null=True)
    # date?
    # user?

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'synapse_slice'


@python_2_unicode_compatible
class SynapseObject(models.Model):
    """3D synapse object"""

    def __str__(self):
        return str(self.id)

    class Meta:
        db_table = 'synapse_object'


@python_2_unicode_compatible
class SynapseSliceSynapseObject(models.Model):
    """Mapping from 2D partial synapse cross-sections to whole 3D synapse objects"""
    synapse_slice = models.OneToOneField(SynapseSlice, unique=True, on_delete=models.CASCADE)
    synapse_object = models.ForeignKey(SynapseObject, on_delete=models.CASCADE)

    def __str__(self):
        return '{} -- {}'.format(self.synapse_slice.id, self.synapse_object.id)

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


@python_2_unicode_compatible
class ProjectSynapseSuggestionWorkflow(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    synapse_suggestion_workflow = models.ForeignKey(SynapseSuggestionWorkflow, on_delete=models.CASCADE)
    synapse_association_algorithm = models.ForeignKey(SynapseAssociationAlgorithm, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '{} -- {} (algo {})'.format(self.project.id, self.synapse_suggestion_workflow.id,
                                           self.synapse_association_algorithm.id)

    class Meta:
        db_table = 'project_synapse_suggestion_workflow'


@python_2_unicode_compatible
class SynapseSliceTreenode(models.Model):
    """Mapping from 2D partial synapse cross-sections to treenodes"""
    synapse_slice = models.ForeignKey(SynapseSlice, on_delete=models.CASCADE, null=True)
    treenode = models.ForeignKey(Treenode, null=True, on_delete=models.CASCADE)

    project_synapse_suggestion_workflow = models.ForeignKey(ProjectSynapseSuggestionWorkflow, on_delete=models.CASCADE)
    contact_px = models.IntegerField(verbose_name='Size in pixels of 1D contact area between neuron and synapse')

    # contact geometry?

    def __str__(self):
        return '{} -- {}'.format(self.synapse_slice.id, self.treenode.id)

    class Meta:
        db_table = 'synapse_slice_treenode'

from __future__ import unicode_literals

from django.db import models
from django.contrib.gis.db import models as spatial_models

from catmaid.models import Treenode, StackMirror


class SynapseObject(models.Model):

    class Meta:
        db_table = 'synapse_object'


class SynapseDetectionAlgorithm(models.Model):
    id = models.IntegerField(primary_key=True)

    date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'synapse_detection_algorithm'


class SkeletonAssociationAlgorithm(models.Model):
    id = models.IntegerField(primary_key=True)

    date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'skeleton_association_algorithm'


class TileSynapseDetectionAlgorithm(models.Model):
    stack_mirror = models.ForeignKey(StackMirror, verbose_name='stack mirror with raw data',
                                     on_delete=models.CASCADE)

    x_tile_idx = models.IntegerField(db_index=True)
    y_tile_idx = models.IntegerField(db_index=True)
    z_tile_idx = models.IntegerField(db_index=True)

    synapse_detection_algorithm = models.ForeignKey(SynapseDetectionAlgorithm, null=True, on_delete=models.CASCADE)

    # label stack mirror?

    class Meta:
        db_table = 'tile_synapse_detection_algorithm'
        unique_together = ('stack_mirror', 'x_tile_idx', 'y_tile_idx', 'z_tile_idx')


class SynapseSlice(models.Model):
    tile_synapse_detection_algorithm = models.ForeignKey(TileSynapseDetectionAlgorithm, on_delete=models.CASCADE)

    convex_hull_2d = spatial_models.PolygonField()
    size_px = models.IntegerField()

    xs_centroid = models.IntegerField(verbose_name='x coord of centroid in stack coordinates')
    ys_centroid = models.IntegerField(verbose_name='y coord of centroid in stack coordinates')

    # uncertainty
    # date?
    # user?
    # centroid?

    class Meta:
        db_table = 'synapse_slice'


class SynapseSliceSynapseObject(models.Model):
    synapse_slice = models.OneToOneField(SynapseSlice, unique=True, on_delete=models.CASCADE)
    synapse_object = models.ForeignKey(SynapseObject, on_delete=models.CASCADE)

    class Meta:
        db_table = 'synapse_slice_synapse_object'


class SynapseSliceTreenode(models.Model):
    synapse_slice = models.ForeignKey(SynapseSlice, on_delete=models.CASCADE)
    treenode = models.ForeignKey(Treenode, on_delete=models.CASCADE)

    skeleton_association_algorithm = models.ForeignKey(SkeletonAssociationAlgorithm, on_delete=models.CASCADE)
    contact_px = models.IntegerField(verbose_name='Size in pixels of 1D contact area between neuron and synapse')

    # contact geometry?

    class Meta:
        db_table = 'synapse_slice_treenode'

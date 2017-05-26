# -*- coding: utf-8 -*-
# Generated by Django 1.9.11 on 2017-05-09 21:19
from __future__ import unicode_literals

import django.contrib.gis.db.models.fields
from django.db import migrations, models, connection
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('catmaid', '0019_add_import_permission'),
    ]

    operations = [
        migrations.CreateModel(
            name='SkeletonAssociationAlgorithm',
            fields=[
                ('id', models.IntegerField(primary_key=True, serialize=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'db_table': 'skeleton_association_algorithm',
            },
        ),
        migrations.CreateModel(
            name='SynapseDetectionAlgorithm',
            fields=[
                ('id', models.IntegerField(primary_key=True, serialize=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'db_table': 'synapse_detection_algorithm',
            },
        ),
        migrations.CreateModel(
            name='SynapseObject',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
            options={
                'db_table': 'synapse_object',
            },
        ),
        migrations.CreateModel(
            name='SynapseSlice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('convex_hull_2d', django.contrib.gis.db.models.fields.PolygonField(srid=4326)),
                ('size_px', models.IntegerField()),
                ('xs_centroid', models.IntegerField(verbose_name='x coord of centroid in stack coordinates')),
                ('ys_centroid', models.IntegerField(verbose_name='y coord of centroid in stack coordinates')),
            ],
            options={
                'db_table': 'synapse_slice',
            },
        ),
        migrations.CreateModel(
            name='SynapseSliceSynapseObject',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('synapse_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='synapsesuggestor.SynapseObject')),
                ('synapse_slice', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='synapsesuggestor.SynapseSlice')),
            ],
            options={
                'db_table': 'synapse_slice_synapse_object',
            },
        ),
        migrations.CreateModel(
            name='SynapseSliceTreenode',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contact_px', models.IntegerField(verbose_name='Size in pixels of 1D contact area between neuron and synapse')),
                ('skeleton_association_algorithm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='synapsesuggestor.SkeletonAssociationAlgorithm')),
                ('synapse_slice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='synapsesuggestor.SynapseSlice')),
                ('treenode', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='catmaid.Treenode')),
            ],
            options={
                'db_table': 'synapse_slice_treenode',
            },
        ),
        migrations.CreateModel(
            name='TileSynapseDetectionAlgorithm',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('x_tile_idx', models.IntegerField(db_index=True)),
                ('y_tile_idx', models.IntegerField(db_index=True)),
                ('z_tile_idx', models.IntegerField(db_index=True)),
                ('stack_mirror', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='catmaid.StackMirror', verbose_name='stack mirror with raw data')),
                ('synapse_detection_algorithm', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='synapsesuggestor.SynapseDetectionAlgorithm')),
            ],
            options={
                'db_table': 'tile_synapse_detection_algorithm',
            },
        ),
        migrations.AddField(
            model_name='synapseslice',
            name='tile_synapse_detection_algorithm',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='synapsesuggestor.TileSynapseDetectionAlgorithm'),
        ),
        migrations.AlterUniqueTogether(
            name='tilesynapsedetectionalgorithm',
            unique_together=set([('stack_mirror', 'x_tile_idx', 'y_tile_idx', 'z_tile_idx')]),
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS synapse_slice_convex_hull_2d ON synapse_slice USING GIST (convex_hull_2d);",
            """
              SELECT setval(
                'synapse_slice_id_seq',(
                  SELECT GREATEST(MAX(id)+1, nextval('synapse_slice_id_seq')) FROM synapse_slice
                )
              );
            """
        )
    ]
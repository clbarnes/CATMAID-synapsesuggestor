from django.contrib import admin

from synapsesuggestor.models import (
    SynapseDetectionTiling, SynapseDetectionAlgorithm, SynapseImageStore,
    SynapseSuggestionWorkflow, SynapseDetectionTile, SynapseSlice, SynapseObject,
    SynapseSliceSynapseObject, SynapseAssociationAlgorithm,
    ProjectSynapseSuggestionWorkflow, SynapseSliceTreenode
)


admin.site.register(SynapseDetectionTiling)

admin.site.register(SynapseDetectionAlgorithm)

admin.site.register(SynapseImageStore)

admin.site.register(SynapseSuggestionWorkflow)

admin.site.register(SynapseDetectionTile)

class SynapseSliceAdmin(admin.ModelAdmin):
    pass

admin.site.register(SynapseSlice, SynapseSliceAdmin)

admin.site.register(SynapseObject)

admin.site.register(SynapseSliceSynapseObject)

admin.site.register(SynapseAssociationAlgorithm)

admin.site.register(ProjectSynapseSuggestionWorkflow)

admin.site.register(SynapseSliceTreenode)

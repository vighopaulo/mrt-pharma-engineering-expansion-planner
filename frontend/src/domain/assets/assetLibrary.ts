/**
 * MRT Pharma Asset Library — a VIEW MODEL over the authoritative equipment
 * catalog. It is NOT a second catalog and NOT a new authoritative record.
 *
 * DOCTRINE (see report): the engineering/catalog layer is the source of truth.
 * An `AssetLibraryEntry` references a catalog record's identity and reports the
 * geometry availability resolved through the registry — it never copies
 * engineering values (throughput/power/CapEx) and never presents generic
 * geometry dimensions as calibrated catalog dimensions.
 *
 * This module is Bentley-free and fully testable offline. It must not query
 * Bentley or manipulate any viewport.
 */
import { assetFamilyForCatalogModality, type AuthoritativeEquipmentRecord } from './catalogAdapter'
import type { AssetFamily } from './types'
import type { AssetRegistry } from './registry'

/** Whether a spatial representation exists for a library entry. */
export type GeometryAvailability = 'GEOMETRY_AVAILABLE' | 'GEOMETRY_NOT_AVAILABLE'

/**
 * Honest dimension status for a library entry. The scanner catalog footprint is
 * NOT_CALIBRATED, so entries must show the catalog dimension state separately
 * from the generic spatial-representation placeholder.
 */
export type LibraryDimensionStatus = 'NOT_CALIBRATED' | 'CALIBRATED'

/**
 * Presentation/domain view model row. References the authoritative catalog
 * record (catalogSource + catalogRecordId); carries only identity + resolved
 * geometry status, never duplicated engineering truth.
 */
export interface AssetLibraryEntry {
    catalogSource: AuthoritativeEquipmentRecord['catalogSource']
    catalogRecordId: string
    assetClass: 'IMAGING'
    modalityGroup: 'PET/CT'
    assetFamily: AssetFamily
    manufacturer: string
    model: string
    displayLabel: string
    geometryAvailability: GeometryAvailability
    /** Present only when geometry is available. */
    geometryRepresentationId?: string
    /** True unless a manufacturer-specific representation is resolved. */
    geometryIsGeneric: boolean
    /** Honest catalog footprint status (scanner catalog = NOT_CALIBRATED). */
    dimensionStatus: LibraryDimensionStatus
    /** Short honest status string for the UI, e.g. generic-representation note. */
    geometryStatusNote: string
}

/**
 * Build a single library entry from an authoritative catalog record, resolving
 * geometry availability through the registry (family-checked, deterministic
 * priority). Returns undefined if the record's modality has no supported family
 * (so unsupported equipment simply does not appear in the PET/CT-scoped library
 * rather than showing a fabricated row).
 */
export function buildAssetLibraryEntry(
    record: AuthoritativeEquipmentRecord,
    registry: AssetRegistry,
): AssetLibraryEntry | undefined {
    const family = assetFamilyForCatalogModality(record.modality, record.configurationNote)
    if (!family || family !== 'PET_CT_SCANNER') {
        // This build is PET/CT-scoped; other families are intentionally excluded.
        return undefined
    }

    const geoRes = registry.resolveCompatibleGeometry(family)
    const available = geoRes.status === 'RESOLVED'
    const geometryIsGeneric = available ? !geoRes.representation.manufacturerSpecific : false

    // Scanner catalog footprints are NOT_CALIBRATED; honor the record flag.
    const dimensionStatus: LibraryDimensionStatus = record.dimensionsCalibrated ? 'CALIBRATED' : 'NOT_CALIBRATED'

    const geometryStatusNote = !available
        ? 'No spatial representation available'
        : geometryIsGeneric
            ? 'Generic spatial representation available'
            : 'Manufacturer-specific representation available'

    return {
        catalogSource: record.catalogSource,
        catalogRecordId: record.catalogRecordId,
        assetClass: 'IMAGING',
        modalityGroup: 'PET/CT',
        assetFamily: family,
        manufacturer: record.manufacturer,
        model: record.model,
        // Label from authoritative identity, never a generic geometry name.
        displayLabel: `${record.manufacturer} ${record.model}`,
        geometryAvailability: available ? 'GEOMETRY_AVAILABLE' : 'GEOMETRY_NOT_AVAILABLE',
        geometryRepresentationId: available ? geoRes.representation.geometryRepresentationId : undefined,
        geometryIsGeneric,
        dimensionStatus,
        geometryStatusNote,
    }
}

/**
 * Build the PET/CT-scoped Asset Library from a set of authoritative catalog
 * records. Records whose modality is not a supported PET/CT family are omitted.
 * Deterministic ordering: by manufacturer then model.
 */
export function buildPetCtAssetLibrary(
    records: readonly AuthoritativeEquipmentRecord[],
    registry: AssetRegistry,
): AssetLibraryEntry[] {
    const entries: AssetLibraryEntry[] = []
    for (const rec of records) {
        const entry = buildAssetLibraryEntry(rec, registry)
        if (entry) entries.push(entry)
    }
    return entries.sort((a, b) =>
        a.manufacturer === b.manufacturer ? a.model.localeCompare(b.model) : a.manufacturer.localeCompare(b.manufacturer),
    )
}

/**
 * MRT Pharma — authoritative equipment catalog → spatial AssetDefinition adapter.
 *
 * DOCTRINE: the engineering/catalog layer is authoritative. This adapter
 * translates an AuthoritativeEquipmentRecord into a spatial `AssetDefinition`
 * by REFERENCE (catalogSource + catalogRecordId + engineeringMetadataReference),
 * never by copying engineering values (throughput, power, cooling, CapEx, OPEX,
 * capacity) into the spatial domain.
 *
 * The authoritative scanner catalog lives in the Python backend
 * (`scanner_equipment_catalog.json` / `scanner_catalog.py`). The frontend cannot
 * import Python, so `AuthoritativeEquipmentRecord` mirrors ONLY the identity
 * fields of that catalog. Records provided to this adapter must be either:
 *   - REPOSITORY_SOURCE_DERIVED: values copied verbatim from the real catalog
 *     JSON (marked so), OR
 *   - TEST_FIXTURE: clearly-marked non-production fixtures for resolver tests.
 * This module never fabricates real-company specifications.
 */
import {
    ASSET_FAMILY_CLASS,
    type AssetCapabilities,
    type AssetClass,
    type AssetDefinition,
    type AssetDimensions,
    type AssetFamily,
} from './types'

/** Provenance of an AuthoritativeEquipmentRecord handed to the adapter. */
export type CatalogRecordProvenance = 'REPOSITORY_SOURCE_DERIVED' | 'TEST_FIXTURE'

/** Which authoritative catalog a record came from. */
export type CatalogSource =
    | 'scanner_equipment_catalog.json'
    | 'cyclotron_equipment_catalog.json'
    | 'generator_equipment_catalog.json'
    | 'TEST_FIXTURE_CATALOG'

/**
 * Identity-only mirror of an authoritative equipment catalog record. Engineering
 * values (throughput/power/CapEx/…) are intentionally NOT represented here — they
 * remain in the authoritative backend catalog and are referenced, not copied.
 */
export interface AuthoritativeEquipmentRecord {
    catalogSource: CatalogSource
    catalogRecordId: string // == catalog_model_id in the backend catalog
    manufacturer: string
    model: string
    /** Backend modality string, e.g. "PET" (PET/CT), "SPECT", "CYCLOTRON". */
    modality: string
    /** e.g. "Integrated diagnostic CT (PET/CT)"; identity/config note only. */
    configurationNote?: string
    /** Whether the catalog record carries CALIBRATED footprint dimensions. */
    dimensionsCalibrated: boolean
    provenance: CatalogRecordProvenance
    /** Optional catalog version, if the backend record exposes one. */
    catalogVersion?: string
}

/** Typed adapter failure states (no vague generic errors for normal failures). */
export type AdapterResult =
    | { ok: true; definition: AssetDefinition }
    | { ok: false; reason: AdapterFailure; message: string }

export type AdapterFailure =
    | 'UNSUPPORTED_ASSET_FAMILY'
    | 'INVALID_CATALOG_ADAPTER'

/**
 * Map an authoritative catalog modality string to a spatial AssetFamily.
 * Only mappings we can support are returned; anything else is unsupported.
 */
export function assetFamilyForCatalogModality(modality: string, configurationNote?: string): AssetFamily | undefined {
    const m = modality.trim().toUpperCase()
    const note = (configurationNote ?? '').toUpperCase()
    if (m === 'PET') {
        // The scanner catalog models PET as PET/CT (ct_configuration integrated).
        return 'PET_CT_SCANNER'
    }
    if (m === 'PET/MR' || m === 'PET_MR') return 'PET_MR_SCANNER'
    if (m === 'SPECT') {
        return note.includes('CT') ? 'SPECT_CT_SCANNER' : 'GAMMA_CAMERA'
    }
    if (m === 'CYCLOTRON') return 'CYCLOTRON'
    return undefined
}

export interface AdaptOptions {
    /** The spatial AssetDefinition id to assign (distinct from the catalog id). */
    assetDefinitionId: string
    /**
     * Geometry representation this definition defaults to. The caller resolves a
     * COMPATIBLE representation; the adapter records it but does not itself pick
     * geometry (resolution lives in the registry).
     */
    defaultGeometryRepresentationId: string
    /**
     * Dimensions to attach. Because scanner catalog footprints are NOT_CALIBRATED,
     * callers pass geometry-native/placeholder dims with honest provenance — never
     * present them as calibrated catalog dimensions.
     */
    dimensions: AssetDimensions
    capabilities?: AssetCapabilities
}

/**
 * Adapt an authoritative catalog record into a spatial AssetDefinition.
 * displayName derives from the authoritative manufacturer + model (never a
 * generic geometry label). Engineering data is referenced, not copied.
 */
export function adaptCatalogRecordToAssetDefinition(
    record: AuthoritativeEquipmentRecord,
    options: AdaptOptions,
): AdapterResult {
    if (!record.catalogRecordId?.trim() || !record.manufacturer?.trim() || !record.model?.trim()) {
        return { ok: false, reason: 'INVALID_CATALOG_ADAPTER', message: 'catalog record missing identity fields' }
    }
    const family = assetFamilyForCatalogModality(record.modality, record.configurationNote)
    if (!family) {
        return {
            ok: false,
            reason: 'UNSUPPORTED_ASSET_FAMILY',
            message: `no spatial AssetFamily mapping for modality '${record.modality}'`,
        }
    }
    const assetClass: AssetClass = ASSET_FAMILY_CLASS[family]

    const definition: AssetDefinition = {
        assetDefinitionId: options.assetDefinitionId,
        assetClass,
        assetFamily: family,
        // Authoritative identity drives the label — NOT the generic geometry.
        displayName: `${record.manufacturer} ${record.model}`,
        manufacturer: record.manufacturer,
        model: record.model,
        catalogReference: `${record.catalogSource}#${record.catalogRecordId}`,
        engineeringMetadataReference: {
            catalogReference: record.catalogRecordId,
            // Resolved means the reference points at a real authoritative record.
            resolved: record.provenance === 'REPOSITORY_SOURCE_DERIVED',
            note:
                record.provenance === 'REPOSITORY_SOURCE_DERIVED'
                    ? `Authoritative record in ${record.catalogSource}; engineering values referenced, not duplicated.`
                    : 'TEST_FIXTURE record; not production catalog data.',
        },
        defaultGeometryRepresentationId: options.defaultGeometryRepresentationId,
        defaultDimensions: options.dimensions,
        capabilities: options.capabilities ?? {},
    }
    return { ok: true, definition }
}

/**
 * REPOSITORY_SOURCE_DERIVED record for GE Discovery MI, copied verbatim from the
 * authoritative `scanner_equipment_catalog.json` identity fields (modality PET,
 * ct_configuration "Integrated diagnostic CT (PET/CT)"; footprint NOT_CALIBRATED).
 * This is NOT fabricated — it mirrors the real backend catalog record.
 */
export const GE_DISCOVERY_MI_RECORD: AuthoritativeEquipmentRecord = {
    catalogSource: 'scanner_equipment_catalog.json',
    catalogRecordId: 'GE_DISCOVERY_MI',
    manufacturer: 'GE HealthCare',
    model: 'Discovery MI',
    modality: 'PET',
    configurationNote: 'Integrated diagnostic CT (PET/CT)',
    dimensionsCalibrated: false, // scanner catalog dimensions_footprint_notes = NOT_CALIBRATED
    provenance: 'REPOSITORY_SOURCE_DERIVED',
    catalogVersion: '1.0',
}

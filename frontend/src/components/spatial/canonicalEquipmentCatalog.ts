/**
 * canonicalEquipmentCatalog — pure, Bentley-free FRONTEND MIRROR of the
 * authoritative MRT Pharma equipment catalogs.
 *
 * DOCTRINE (Build 1B):
 *   The backend Python catalogs are the SINGLE SOURCE OF TRUTH for equipment
 *   identity, physical envelope, production capacity, and cost. This module is a
 *   BY-REFERENCE mirror: every entry carries the backend `catalogModelId`
 *   (== catalog_model_id) plus ONLY the fields the spatial-binding layer needs:
 *     - display identity (manufacturer + model), for honest labels
 *     - a PHYSICAL ENVELOPE **only where the backend catalog carries a
 *       CALIBRATED footprint** (IBA Cyclone KEY/KIUBE manufacturer-calibrated;
 *       ACSI TR-24 site-calibrated). Everywhere else the envelope provenance is
 *       NOT_CALIBRATED and the numeric envelope is a clearly-labelled
 *       GENERIC_ENGINEERING_PLACEHOLDER used ONLY so a proxy box can be drawn.
 *     - CROSSWALK POINTERS (capacity / production / cost authority ids) that
 *       name WHERE the authoritative number lives — never the number itself.
 *
 *   NO equipment class is invented here. This mirror enumerates exactly the
 *   three canonical equipment classes present in the backend catalogs
 *   (CYCLOTRON, GENERATOR, SCANNER) plus the two canonical MRT facility spatial
 *   classes (MRT radiopharmacy vestibule, MRT endpoint). Families such as
 *   SYNTHESIS_MODULE / HOT_CELL / DOSE_CALIBRATOR that exist only as an enum in
 *   the spatial types but have NO backend catalog are intentionally absent
 *   (NOT_IN_CURRENT_PROJECT_SCOPE).
 *
 *   FABRICATED_COSTS = NO. FABRICATED_CAPACITY = NO. Where the backend records a
 *   value as NOT_CALIBRATED, this mirror preserves NOT_CALIBRATED — it never
 *   substitutes a plausible-looking number.
 */

import type { AssetFamily, DimensionProvenance } from '../../domain/assets/types'

// ---------------------------------------------------------------------------
// Canonical class taxonomy (mirrors the three backend catalogs, nothing more)
// ---------------------------------------------------------------------------

/** The three canonical equipment classes that HAVE a backend catalog. */
export type CanonicalEquipmentClass = 'CYCLOTRON' | 'GENERATOR' | 'SCANNER'

/** The two canonical MRT facility spatial classes (not in the 3 equipment catalogs). */
export type CanonicalMrtFacilityClass = 'MRT_RADIOPHARMACY_VESTIBULE' | 'MRT_ENDPOINT'

/** Which authoritative backend catalog a model came from. */
export type CanonicalCatalogSource =
    | 'cyclotron_equipment_catalog.json'
    | 'generator_equipment_catalog.json'
    | 'scanner_equipment_catalog.json'
    | 'canonical_spatial_authority.py'
    | 'shared_mrt_multistream_authority.py'

// ---------------------------------------------------------------------------
// Crosswalk pointers — WHERE the authoritative number lives, never the number
// ---------------------------------------------------------------------------

/** Calibration status of a crosswalked value, mirrored from the backend. */
export type CrosswalkCalibration =
    | 'MANUFACTURER_CALIBRATED'
    | 'SITE_CALIBRATED'
    | 'LITERATURE_CALIBRATED'
    | 'NOT_CALIBRATED'
    | 'STUDY_LEVEL_ANCHOR'

/**
 * A by-reference pointer to an authoritative engineering value. `authorityRef`
 * names the backend module/field/record that owns the value; `calibration`
 * mirrors the backend's own honesty flag. `note` is free text (never a secret).
 * The numeric value is intentionally absent — it is consumed from the backend,
 * not duplicated into the spatial layer.
 */
export interface CrosswalkPointer {
    authorityRef: string
    calibration: CrosswalkCalibration
    note?: string
}

/** Physical envelope, mirrored ONLY where the backend carries calibrated dims. */
export interface CanonicalEnvelope {
    /** local X (m) */ width: number
    /** local Y (m) */ depth: number
    /** local Z (m) */ height: number
    provenance: DimensionProvenance
    /** Backend calibration status behind the numbers (for honest display). */
    calibration: CrosswalkCalibration
    note?: string
}

// ---------------------------------------------------------------------------
// Canonical equipment model (mirror record)
// ---------------------------------------------------------------------------

export interface CanonicalEquipmentModel {
    /** == backend catalog_model_id. Stable cross-layer identity. */
    catalogModelId: string
    canonicalClass: CanonicalEquipmentClass
    catalogSource: CanonicalCatalogSource
    manufacturer: string
    model: string
    /** Spatial AssetFamily this model renders as, when one exists (else undefined). */
    assetFamily?: AssetFamily
    /**
     * Clinical program function(s) this model is eligible to occupy (matching
     * clinicalProgram.CLINICAL_FUNCTIONS). Informational binding hint only — this
     * mirror never enforces equipment↔room compatibility (that authority does not
     * exist in the backend → NOT_CALIBRATED).
     */
    eligibleClinicalFunctions: readonly string[]
    /** Physical envelope (calibrated where the backend has it; placeholder otherwise). */
    envelope: CanonicalEnvelope
    /** Capacity crosswalk (e.g. generator reference-activity options). */
    capacityCrosswalk: CrosswalkPointer
    /** Production crosswalk (e.g. cyclotron EOB MBq; scanner acquisition minutes). */
    productionCrosswalk: CrosswalkPointer
    /** Cost crosswalk (CapEx authority id). */
    costCrosswalk: CrosswalkPointer
    /** Free-text provenance note mirrored from the backend record (no secrets). */
    provenanceNote?: string
}

export interface CanonicalMrtFacilityModel {
    canonicalClass: CanonicalMrtFacilityClass
    catalogSource: CanonicalCatalogSource
    assetFamily: AssetFamily
    displayName: string
    /** Cost crosswalk — the distinct MRT vestibule / light-MRT endpoint authority. */
    costCrosswalk: CrosswalkPointer
    provenanceNote?: string
}

// ---------------------------------------------------------------------------
// Shared crosswalk constants (ids only — never values)
// ---------------------------------------------------------------------------

/** Study-level cyclotron installation CapEx anchor (CapEx not in the catalog). */
const CYCLOTRON_CAPEX_REF = 'models.PlannerAssumptions.cyclotron_installation_capex'
/** Generic study-level PET scanner CapEx anchor (scanner catalog CapEx NOT_CALIBRATED). */
const SCANNER_CAPEX_REF = 'models.PlannerAssumptions.scanner_capex'

/** Envelope used ONLY to draw a proxy box when the backend has no calibrated dims. */
function placeholderEnvelope(note: string): CanonicalEnvelope {
    // A single, honest, clearly-labelled engineering placeholder. NOT a spec.
    return {
        width: 2.0,
        depth: 2.0,
        height: 2.0,
        provenance: 'GENERIC_ENGINEERING_PLACEHOLDER',
        calibration: 'NOT_CALIBRATED',
        note,
    }
}

/** A calibrated envelope mirrored verbatim from the backend catalog. */
function calibratedEnvelope(width: number, depth: number, height: number, calibration: CrosswalkCalibration, note: string): CanonicalEnvelope {
    return { width, depth, height, provenance: calibration === 'SITE_CALIBRATED' ? 'CATALOG' : 'CALIBRATED', calibration, note }
}

const CYCLOTRON_FUNCTIONS = ['CYCLOTRON'] as const
const GENERATOR_FUNCTIONS = ['RADIOPHARMACY', 'DOSE_DISPENSING'] as const
const PET_SCANNER_FUNCTIONS = ['PET_CT_SCANNER_ROOM'] as const
const SPECT_SCANNER_FUNCTIONS = ['SPECT_CT_SCANNER_ROOM'] as const

// ---------------------------------------------------------------------------
// CYCLOTRON models (cyclotron_equipment_catalog.json, schema 1.1) — 17 models
// ---------------------------------------------------------------------------

function cyclotron(
    catalogModelId: string,
    manufacturer: string,
    model: string,
    envelope: CanonicalEnvelope,
    production: CrosswalkPointer,
    provenanceNote?: string,
): CanonicalEquipmentModel {
    return {
        catalogModelId,
        canonicalClass: 'CYCLOTRON',
        catalogSource: 'cyclotron_equipment_catalog.json',
        manufacturer,
        model,
        assetFamily: 'CYCLOTRON',
        eligibleClinicalFunctions: CYCLOTRON_FUNCTIONS,
        envelope,
        capacityCrosswalk: {
            authorityRef: `cyclotron_equipment_catalog.json#${catalogModelId}.max_simultaneous_production_streams`,
            calibration: 'MANUFACTURER_CALIBRATED',
            note: 'Simultaneous production streams / supported radionuclides in the backend catalog.',
        },
        productionCrosswalk: production,
        costCrosswalk: {
            authorityRef: CYCLOTRON_CAPEX_REF,
            calibration: 'STUDY_LEVEL_ANCHOR',
            note: 'CapEx is NOT in the cyclotron catalog; study-level installation CapEx anchor applies.',
        },
        provenanceNote,
    }
}

/** Manufacturer-calibrated EOB MBq production crosswalk (value lives in backend record). */
function eobProduction(catalogModelId: string): CrosswalkPointer {
    return {
        authorityRef: `cyclotron_equipment_catalog.json#${catalogModelId}.production_performance_records[].normalized_eob_activity_mbq`,
        calibration: 'MANUFACTURER_CALIBRATED',
        note: 'Calibration input only; not an unconditional facility MBq/day capacity.',
    }
}

/** No calibrated production record in the backend → NOT_CALIBRATED (never borrowed). */
function noProduction(catalogModelId: string): CrosswalkPointer {
    return {
        authorityRef: `cyclotron_equipment_catalog.json#${catalogModelId}.production_performance_records`,
        calibration: 'NOT_CALIBRATED',
        note: 'Supported radionuclides may exist, but no calibrated production record; capacity NOT_CALIBRATED.',
    }
}

export const CANONICAL_CYCLOTRON_MODELS: readonly CanonicalEquipmentModel[] = [
    cyclotron('GE_PETTRACE_840', 'GE HealthCare', 'PETtrace 840', placeholderEnvelope('GE PETtrace catalog carries no physical envelope.'), eobProduction('GE_PETTRACE_840')),
    cyclotron('GE_PETTRACE_860', 'GE HealthCare', 'PETtrace 860', placeholderEnvelope('GE PETtrace catalog carries no physical envelope.'), eobProduction('GE_PETTRACE_860')),
    cyclotron('GE_PETTRACE_880', 'GE HealthCare', 'PETtrace 880', placeholderEnvelope('GE PETtrace catalog carries no physical envelope.'), eobProduction('GE_PETTRACE_880')),
    cyclotron('GE_PETTRACE_890', 'GE HealthCare', 'PETtrace 890', placeholderEnvelope('GE PETtrace catalog carries no physical envelope.'), eobProduction('GE_PETTRACE_890')),
    cyclotron('GE_PETTRACE_800', 'GE HealthCare', 'PETtrace 800', placeholderEnvelope('GE PETtrace (legacy) catalog carries no physical envelope.'), noProduction('GE_PETTRACE_800'), 'commercial_status: legacy'),
    cyclotron(
        'IBA_CYCLONE_KEY', 'IBA', 'Cyclone KEY',
        calibratedEnvelope(1.5, 1.4, 1.35, 'MANUFACTURER_CALIBRATED', 'length_m/width_m/height_m manufacturer_calibrated in backend catalog.'),
        eobProduction('IBA_CYCLONE_KEY'),
    ),
    cyclotron(
        'IBA_CYCLONE_KIUBE', 'IBA', 'Cyclone KIUBE',
        calibratedEnvelope(1.9, 1.9, 1.8, 'MANUFACTURER_CALIBRATED', 'length_m/width_m/height_m manufacturer_calibrated in backend catalog.'),
        eobProduction('IBA_CYCLONE_KIUBE'),
    ),
    cyclotron('IBA_CYCLONE_IKON', 'IBA', 'Cyclone IKON', placeholderEnvelope('IBA Cyclone IKON catalog carries no physical envelope.'), noProduction('IBA_CYCLONE_IKON')),
    cyclotron('IBA_CYCLONE_30XP', 'IBA', 'Cyclone 30XP', placeholderEnvelope('IBA Cyclone 30XP catalog carries no physical envelope.'), noProduction('IBA_CYCLONE_30XP')),
    cyclotron('SUMITOMO_CYPRIS_HM_12', 'Sumitomo Heavy Industries', 'CYPRIS HM-12', placeholderEnvelope('Sumitomo CYPRIS catalog carries no physical envelope.'), noProduction('SUMITOMO_CYPRIS_HM_12')),
    cyclotron('SUMITOMO_CYPRIS_HM_20', 'Sumitomo Heavy Industries', 'CYPRIS HM-20', placeholderEnvelope('Sumitomo CYPRIS catalog carries no physical envelope.'), noProduction('SUMITOMO_CYPRIS_HM_20')),
    cyclotron('SUMITOMO_CYPRIS_MP_30', 'Sumitomo Heavy Industries', 'CYPRIS MP-30', placeholderEnvelope('Sumitomo CYPRIS catalog carries no physical envelope.'), noProduction('SUMITOMO_CYPRIS_MP_30'), 'F-18 SUPPORTED but production NOT_CALIBRATED (no records).'),
    cyclotron('SIEMENS_CTI_ECLIPSE_HP', 'Siemens/CTI', 'Eclipse HP', placeholderEnvelope('Siemens/CTI (legacy) catalog carries no physical envelope.'), noProduction('SIEMENS_CTI_ECLIPSE_HP'), 'commercial_status: legacy'),
    cyclotron('SIEMENS_CTI_RDS_111', 'Siemens/CTI', 'RDS-111', placeholderEnvelope('Siemens/CTI (legacy) catalog carries no physical envelope.'), noProduction('SIEMENS_CTI_RDS_111'), 'commercial_status: legacy'),
    cyclotron('ACSI_TR_19', 'ACSI', 'TR-19', placeholderEnvelope('ACSI TR-19 catalog carries no physical envelope.'), noProduction('ACSI_TR_19')),
    cyclotron(
        'ACSI_TR_24', 'ACSI', 'TR-24',
        calibratedEnvelope(1.8, 1.8, 2.5, 'SITE_CALIBRATED', 'length_m/width_m/height_m site_calibrated (installation-specific, not universal manufacturer value).'),
        noProduction('ACSI_TR_24'),
    ),
    cyclotron('BEST_14P', 'Best Cyclotron Systems', 'Best 14p', placeholderEnvelope('Best compact catalog carries no physical envelope.'), noProduction('BEST_14P')),
]

// ---------------------------------------------------------------------------
// GENERATOR models (generator_equipment_catalog.json, schema 1.0) — 4 models
// ---------------------------------------------------------------------------

function generator(
    catalogModelId: string,
    manufacturer: string,
    model: string,
    parentDaughter: string,
    referenceActivityCalibrated: boolean,
    provenanceNote?: string,
): CanonicalEquipmentModel {
    return {
        catalogModelId,
        canonicalClass: 'GENERATOR',
        catalogSource: 'generator_equipment_catalog.json',
        manufacturer,
        model,
        // The backend generator catalog has NO physical dimensions (dimensions_cm=null)
        // and there is NO spatial AssetFamily for a generator → no geometry family.
        assetFamily: undefined,
        eligibleClinicalFunctions: GENERATOR_FUNCTIONS,
        envelope: placeholderEnvelope(`Generator ${parentDaughter}: dimensions_cm and mass_kg are null in the backend catalog (NOT_CALIBRATED).`),
        capacityCrosswalk: {
            authorityRef: `generator_equipment_catalog.json#${catalogModelId}.nominal_reference_activity_options_mbq`,
            calibration: referenceActivityCalibrated ? 'LITERATURE_CALIBRATED' : 'NOT_CALIBRATED',
            note: referenceActivityCalibrated
                ? 'Reference activity is the parent activity at the calibration date/time, NOT the daughter activity at any later elution.'
                : 'Per-model reference-activity options were not independently sourced (empty) → NOT_CALIBRATED, never fabricated.',
        },
        productionCrosswalk: {
            authorityRef: `generator_equipment_catalog.json#${catalogModelId} (${parentDaughter})`,
            calibration: 'LITERATURE_CALIBRATED',
            note: `Parent→daughter pathway ${parentDaughter}; daughter yield governed by elution efficiency + decay, not a fixed capacity.`,
        },
        costCrosswalk: {
            authorityRef: `generator_equipment_catalog.json#${catalogModelId}.economics`,
            calibration: 'NOT_CALIBRATED',
            note: 'purchase_capex / replacement_cost_per_cycle / annual_maintenance_opex all NOT_CALIBRATED in the backend catalog.',
        },
        provenanceNote,
    }
}

export const CANONICAL_GENERATOR_MODELS: readonly CanonicalEquipmentModel[] = [
    generator('CURIUM_TECHNELITE', 'Curium Pharma', 'TechneLite (Tc-99m Generator)', 'Mo-99 → Tc-99m', true),
    generator('CURIUM_ULTRA_TECHNEKOW_FM', 'Curium Pharma', 'Ultra-TechneKow FM (Tc-99m Generator)', 'Mo-99 → Tc-99m', true),
    generator('GE_HEALTHCARE_DRYTEC', 'GE Healthcare', 'Drytec (Tc-99m Generator)', 'Mo-99 → Tc-99m', true),
    generator('ECKERT_ZIEGLER_GALLIAPHARM', 'Eckert & Ziegler', 'GalliaPharm (Ge-68/Ga-68 Generator)', 'Ge-68 → Ga-68', false, 'reference-activity options empty (NOT_CALIBRATED); parent Ge-68 half-life 390441.6 min.'),
]

// ---------------------------------------------------------------------------
// SCANNER models (scanner_equipment_catalog.json, schema 1.0) — 6 models
// ---------------------------------------------------------------------------

function scanner(
    catalogModelId: string,
    manufacturer: string,
    model: string,
    modality: 'PET' | 'SPECT',
    provenanceNote?: string,
): CanonicalEquipmentModel {
    const isPet = modality === 'PET'
    return {
        catalogModelId,
        canonicalClass: 'SCANNER',
        catalogSource: 'scanner_equipment_catalog.json',
        manufacturer,
        model,
        // Scanner catalog footprint is NOT_CALIBRATED for every model, but the
        // spatial layer does have PET/CT + SPECT/CT AssetFamilies for rendering.
        assetFamily: isPet ? 'PET_CT_SCANNER' : 'SPECT_CT_SCANNER',
        eligibleClinicalFunctions: isPet ? PET_SCANNER_FUNCTIONS : SPECT_SCANNER_FUNCTIONS,
        envelope: placeholderEnvelope(`Scanner ${modality}: dimensions_footprint_notes = NOT_CALIBRATED in the backend catalog.`),
        capacityCrosswalk: {
            authorityRef: `scanner_equipment_catalog.json#${catalogModelId}.typical_acquisition_minutes_per_protocol`,
            calibration: 'LITERATURE_CALIBRATED',
            note: 'Typical per-protocol acquisition minutes (throughput proxy); not a site-calibrated capacity.',
        },
        productionCrosswalk: {
            authorityRef: `scanner_equipment_catalog.json#${catalogModelId}.protocol_families`,
            calibration: 'LITERATURE_CALIBRATED',
            note: 'Imaging modality is a study endpoint, not radionuclide production.',
        },
        costCrosswalk: {
            authorityRef: SCANNER_CAPEX_REF,
            calibration: 'STUDY_LEVEL_ANCHOR',
            note: 'scanner catalog purchase_capex NOT_CALIBRATED; generic study-level scanner CapEx anchor applies.',
        },
        provenanceNote,
    }
}

export const CANONICAL_SCANNER_MODELS: readonly CanonicalEquipmentModel[] = [
    scanner('SIEMENS_SYMBIA_PRO_SPECTA', 'Siemens Healthineers', 'Symbia Pro.specta', 'SPECT'),
    scanner('GE_NM_CT_870_DR', 'GE HealthCare', 'NM/CT 870 DR', 'SPECT'),
    scanner('GE_NM_CT_860', 'GE HealthCare', 'NM/CT 860', 'SPECT'),
    scanner('PHILIPS_BRIGHTVIEW_XCT', 'Philips', 'BrightView XCT', 'SPECT', 'commercial_status: LEGACY_INSTALLED_BASE'),
    scanner('GE_DISCOVERY_MI', 'GE HealthCare', 'Discovery MI', 'PET'),
    scanner('SIEMENS_BIOGRAPH_VISION', 'Siemens Healthineers', 'Biograph Vision', 'PET'),
]

// ---------------------------------------------------------------------------
// Canonical MRT facility spatial classes (distinct cost authorities, §37)
// ---------------------------------------------------------------------------

export const CANONICAL_MRT_FACILITY_MODELS: readonly CanonicalMrtFacilityModel[] = [
    {
        canonicalClass: 'MRT_RADIOPHARMACY_VESTIBULE',
        catalogSource: 'canonical_spatial_authority.py',
        assetFamily: 'MRT_RADIOPHARMACY_VESTIBULE',
        displayName: 'MRT Radiopharmacy Vestibule',
        costCrosswalk: {
            authorityRef: 'canonical_spatial_authority.MRT_VESTIBULE_CAPEX_USD',
            calibration: 'STUDY_LEVEL_ANCHOR',
            note: '$30,000/vestibule, charged one per cyclotron interface requiring MRT transfer — never per radiopharmacy/floor/room/endpoint count.',
        },
        provenanceNote: 'Distinct from the room/service endpoint panel; no double-count (§37).',
    },
    {
        canonicalClass: 'MRT_ENDPOINT',
        catalogSource: 'shared_mrt_multistream_authority.py',
        assetFamily: 'MRT_ENDPOINT',
        displayName: 'MRT Endpoint (light-MRT panel)',
        costCrosswalk: {
            authorityRef: 'shared_mrt_multistream_authority.LIGHT_MRT_ENDPOINT_CAPEX_PER_UNIT',
            calibration: 'STUDY_LEVEL_ANCHOR',
            note: '$1,000/endpoint (light-MRT panel), distinct from mainstream PlannerAssumptions.endpoint_capex ($10,000); no double-count (§37).',
        },
        provenanceNote: 'Light-MRT room/service endpoint panel.',
    },
]

// ---------------------------------------------------------------------------
// Aggregate + lookup
// ---------------------------------------------------------------------------

/** Every canonical equipment model across the three backend catalogs. */
export const CANONICAL_EQUIPMENT_MODELS: readonly CanonicalEquipmentModel[] = [
    ...CANONICAL_CYCLOTRON_MODELS,
    ...CANONICAL_GENERATOR_MODELS,
    ...CANONICAL_SCANNER_MODELS,
]

const BY_ID: ReadonlyMap<string, CanonicalEquipmentModel> = new Map(
    CANONICAL_EQUIPMENT_MODELS.map((m) => [m.catalogModelId, m]),
)

/** Look up a canonical equipment model by its backend catalog_model_id. */
export function canonicalEquipmentById(catalogModelId: string): CanonicalEquipmentModel | undefined {
    return BY_ID.get(catalogModelId)
}

/** All canonical models of a given class. */
export function canonicalEquipmentByClass(cls: CanonicalEquipmentClass): readonly CanonicalEquipmentModel[] {
    return CANONICAL_EQUIPMENT_MODELS.filter((m) => m.canonicalClass === cls)
}

/** Look up a canonical MRT facility model by class. */
export function canonicalMrtFacility(cls: CanonicalMrtFacilityClass): CanonicalMrtFacilityModel | undefined {
    return CANONICAL_MRT_FACILITY_MODELS.find((m) => m.canonicalClass === cls)
}

/**
 * Whether a spatial AssetFamily is one this Build-1B binding layer supports.
 * Only the canonical catalog-backed families + the two MRT facility classes are
 * bindable. Families like SYNTHESIS_MODULE / HOT_CELL / DOSE_CALIBRATOR are
 * NOT_IN_CURRENT_PROJECT_SCOPE (enum-only, no backend catalog).
 */
export function isBindableEquipmentFamily(family: AssetFamily): boolean {
    return (
        family === 'CYCLOTRON' ||
        family === 'PET_CT_SCANNER' ||
        family === 'SPECT_CT_SCANNER' ||
        family === 'MRT_RADIOPHARMACY_VESTIBULE' ||
        family === 'MRT_ENDPOINT'
    )
}

/** Counts for the report/audit (source-first, no invention). */
export interface CanonicalCatalogAudit {
    cyclotronModelCount: number
    generatorModelCount: number
    scannerModelCount: number
    totalEquipmentModelCount: number
    mrtFacilityClassCount: number
    calibratedEnvelopeModelIds: readonly string[]
    newUnauthorizedEquipmentClasses: 0
}

export function summarizeCanonicalCatalog(): CanonicalCatalogAudit {
    const calibrated = CANONICAL_EQUIPMENT_MODELS.filter((m) => m.envelope.provenance === 'CALIBRATED' || m.envelope.calibration === 'SITE_CALIBRATED').map((m) => m.catalogModelId)
    return {
        cyclotronModelCount: CANONICAL_CYCLOTRON_MODELS.length,
        generatorModelCount: CANONICAL_GENERATOR_MODELS.length,
        scannerModelCount: CANONICAL_SCANNER_MODELS.length,
        totalEquipmentModelCount: CANONICAL_EQUIPMENT_MODELS.length,
        mrtFacilityClassCount: CANONICAL_MRT_FACILITY_MODELS.length,
        calibratedEnvelopeModelIds: calibrated,
        newUnauthorizedEquipmentClasses: 0,
    }
}

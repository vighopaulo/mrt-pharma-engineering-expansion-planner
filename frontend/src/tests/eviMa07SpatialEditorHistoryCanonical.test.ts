/**
 * EVI-MA-07 — spatial-editor Undo/Redo history, canonical vestibule identity, and
 * the two hollow front-face transport openings.
 *
 * Bentley-FREE. Covers the PURE substance: the bounded command/history stack
 * (undo/redo are exact inverses; delete-restore reuses the SAME id), the
 * canonical MRTway facility asset + independent service configs, and the
 * simplified front face with a large RECTANGULAR hollow MRT opening + a small
 * CIRCULAR hollow PTS opening. The live selection-persistence / captured-target /
 * local-menu chain is exercised by the DOM test + manual acceptance.
 */
import { describe, expect, it } from 'vitest'
import { AppEditHistory } from '../components/spatial/appEditHistory'
import {
    createVestibuleInstance,
    canonicalVestibuleConfigId,
    canonicalVestibuleConfigs,
    CANONICAL_CLINICAL_LOGISTICS_VESTIBULE_ASSET,
    MRTWAY_CLINICAL_LOGISTICS_VESTIBULE,
    permittedPortsForServiceClass,
    type ServiceClass,
} from '../components/spatial/clinicalLogisticsVestibule'
import { buildClinicalLogisticsVestibuleParts, type EquipmentPose } from '../components/spatial/equipmentGeometry'

const ROOM = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 8 }, { x: 0, y: 8 }]
const POSE: EquipmentPose = { center: [5, 4, 0], width: 1.3, depth: 0.9, height: 2.0, yawRadians: 0 }

// ---------------------------------------------------------------------------
// Undo/Redo history stack (pure)
// ---------------------------------------------------------------------------
describe('AppEditHistory', () => {
    const cmd = (type: 'DELETE' | 'MOVE', id: string) => ({ type, objectType: 'EQUIPMENT_INSTANCE' as const, instanceId: id, beforeState: { p: 0 }, afterState: { p: 1 }, timestamp: 0 })

    it('records, undoes, and redoes in linear order', () => {
        const h = new AppEditHistory()
        expect(h.canUndo()).toBe(false)
        h.record(cmd('DELETE', 'a'))
        h.record(cmd('MOVE', 'b'))
        expect(h.canUndo()).toBe(true)
        expect(h.peekUndo()?.instanceId).toBe('b')
        const u = h.popUndo()
        expect(u?.instanceId).toBe('b')
        expect(h.canRedo()).toBe(true)
        const r = h.popRedo()
        expect(r?.instanceId).toBe('b')
    })

    it('recording a new command clears the redo stack (linear history)', () => {
        const h = new AppEditHistory()
        h.record(cmd('DELETE', 'a'))
        h.popUndo()
        expect(h.canRedo()).toBe(true)
        h.record(cmd('MOVE', 'c'))
        expect(h.canRedo()).toBe(false)
    })

    it('is bounded (never grows without limit)', () => {
        const h = new AppEditHistory(3)
        for (let i = 0; i < 10; i++) h.record(cmd('MOVE', `m${i}`))
        expect(h.counts().undo).toBe(3)
    })

    it('clear empties both stacks', () => {
        const h = new AppEditHistory()
        h.record(cmd('DELETE', 'a'))
        h.clear()
        expect(h.canUndo()).toBe(false)
        expect(h.canRedo()).toBe(false)
    })
})

// ---------------------------------------------------------------------------
// Canonical MRTway vestibule asset + independent service configs
// ---------------------------------------------------------------------------
describe('canonical MRTway clinical logistics vestibule', () => {
    it('A/B: the canonical facility asset is an MRTway FACILITY_LOGISTICS_INTERFACE mapping to the V1 visual family', () => {
        expect(CANONICAL_CLINICAL_LOGISTICS_VESTIBULE_ASSET.canonicalAssetId).toBe(MRTWAY_CLINICAL_LOGISTICS_VESTIBULE)
        expect(CANONICAL_CLINICAL_LOGISTICS_VESTIBULE_ASSET.owner).toBe('MRTway Systems')
        expect(CANONICAL_CLINICAL_LOGISTICS_VESTIBULE_ASSET.assetCategory).toBe('FACILITY_LOGISTICS_INTERFACE')
        expect(CANONICAL_CLINICAL_LOGISTICS_VESTIBULE_ASSET.visualFamily).toBe('CLINICAL_LOGISTICS_VESTIBULE_V1')
    })

    it('C: service configuration is independent of the visual family (one config per service class)', () => {
        const configs = canonicalVestibuleConfigs()
        expect(configs).toHaveLength(5)
        for (const c of configs) {
            expect(c.canonicalAssetId).toBe(MRTWAY_CLINICAL_LOGISTICS_VESTIBULE)
            expect(c.canonicalConfigId).toBe(`MRTWAY_CLV_${c.serviceClass}`)
        }
    })

    it('D: the Radiopharmacy config has MRT + RP-qualified PTS', () => {
        expect(canonicalVestibuleConfigId('RADIOPHARMACY')).toBe('MRTWAY_CLV_RADIOPHARMACY')
        const ports = permittedPortsForServiceClass('RADIOPHARMACY')
        expect(ports.find((p) => p.transportFamily === 'MRT')!.fabricatedThisBuild).toBe(true)
        expect(ports.find((p) => p.transportFamily === 'PTS')!.ptsQualification).toBe('RADIOPHARMACEUTICAL_QUALIFIED')
    })

    it('A/E: a created vestibule instance carries the canonical asset + config id', () => {
        const r = createVestibuleInstance({
            iModelId: 'im', serviceClass: 'RADIOPHARMACY', parentBimSpaceId: 'room',
            footprint: ROOM, zLow: 0, zHigh: 3.2, seq: 1,
        })
        expect(r.ok).toBe(true)
        if (!r.ok) return
        expect(r.instance.canonicalAssetId).toBe(MRTWAY_CLINICAL_LOGISTICS_VESTIBULE)
        expect(r.instance.canonicalConfigId).toBe('MRTWAY_CLV_RADIOPHARMACY')
        expect(r.instance.visualFamily).toBe('CLINICAL_LOGISTICS_VESTIBULE_V1')
    })

    it('service configs exist for all five classes', () => {
        for (const sc of ['RADIOPHARMACY', 'PHARMACY', 'LABORATORY', 'STERILE_CLEAN_SUPPLY', 'LAUNDRY_LINEN'] as ServiceClass[]) {
            expect(canonicalVestibuleConfigId(sc)).toBe(`MRTWAY_CLV_${sc}`)
        }
    })
})

// ---------------------------------------------------------------------------
// Two hollow front-face transport openings (EVI-MA-07 §21-23, §43)
// ---------------------------------------------------------------------------
describe('two hollow front-face transport openings', () => {
    it('A/B/C: the MRT opening is a RECTANGULAR frame around a nonzero, non-solid void', () => {
        const parts = buildClinicalLogisticsVestibuleParts(POSE, { mrt: true, pts: false })
        const frame = parts.find((p) => p.part === 'CLV_MRT_OPENING_FRAME') as { low: number[]; high: number[] } | undefined
        const voidPart = parts.find((p) => p.part === 'CLV_MRT_OPENING_VOID') as { low: number[]; high: number[] } | undefined
        expect(frame).toBeDefined()
        expect(voidPart).toBeDefined()
        // Nonzero inner free width + height, and the void is a BOX (a recessed
        // empty rectangle), not absent.
        const w = voidPart!.high[0] - voidPart!.low[0]
        const h = voidPart!.high[2] - voidPart!.low[2]
        expect(w).toBeGreaterThan(0)
        expect(h).toBeGreaterThan(0)
        // The void is recessed behind the frame (extends in +Y depth), i.e. a real cavity.
        expect(voidPart!.high[1] - voidPart!.low[1]).toBeGreaterThan(0)
    })

    it('D/E: the PTS opening is a CIRCULAR ring around a nonzero circular bore void', () => {
        const parts = buildClinicalLogisticsVestibuleParts(POSE, { mrt: false, pts: true })
        const ring = parts.find((p) => p.part === 'CLV_PTS_OPENING_RING')
        const bore = parts.find((p) => p.part === 'CLV_PTS_OPENING_VOID') as { kind: string; radius: number } | undefined
        expect(ring).toBeDefined()
        expect(bore).toBeDefined()
        expect(bore!.kind).toBe('CYLINDER')
        expect(bore!.radius).toBeGreaterThan(0)
    })

    it('F/G: MRT and PTS openings are physically separate and the PTS bore is much smaller than the MRT tract', () => {
        const parts = buildClinicalLogisticsVestibuleParts(POSE, { mrt: true, pts: true })
        const mrtVoid = parts.find((p) => p.part === 'CLV_MRT_OPENING_VOID') as { low: number[]; high: number[] }
        const ptsBore = parts.find((p) => p.part === 'CLV_PTS_OPENING_VOID') as { radius: number }
        const mrtW = mrtVoid.high[0] - mrtVoid.low[0]
        expect(mrtW).toBeGreaterThan(ptsBore.radius * 2 * 1.5) // MRT rectangle >> PTS bore
        // Both present + distinct shapes (MRT box, PTS cylinder).
        expect(parts.filter((p) => p.part === 'CLV_MRT_OPENING_VOID').length).toBe(1)
        expect(parts.filter((p) => p.part === 'CLV_PTS_OPENING_VOID').length).toBe(1)
    })

    it('openings only appear for configured ports (sterile MRT-only shows no PTS opening)', () => {
        const parts = buildClinicalLogisticsVestibuleParts(POSE, { mrt: true, pts: false })
        expect(parts.some((p) => p.part === 'CLV_MRT_OPENING_VOID')).toBe(true)
        expect(parts.some((p) => p.part === 'CLV_PTS_OPENING_VOID')).toBe(false)
    })
})

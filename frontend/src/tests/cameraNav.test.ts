/**
 * Offline tests for the pure camera-mode + walkthrough-traversal policy. No
 * Bentley runtime; view/navigation decisions only.
 */
import { describe, expect, it } from 'vitest'
import {
    CAMERA_MODES,
    classifyOpening,
    resolveCameraModePolicy,
    resolveTraversal,
    type OpeningKind,
} from '../components/spatial/cameraNav'

describe('camera mode policy', () => {
    it('exposes exactly three modes', () => {
        expect(CAMERA_MODES.length).toBe(3)
    })
    it('PLANNING: asset manipulation on, collision + cutaway off', () => {
        const p = resolveCameraModePolicy('PLANNING')
        expect(p.assetManipulation).toBe(true)
        expect(p.collision).toBe(false)
        expect(p.cutaway).toBe(false)
        expect(p.pointerLook).toBe(false)
    })
    it('WALKTHROUGH: movement + collision on, asset manipulation off', () => {
        const p = resolveCameraModePolicy('WALKTHROUGH')
        expect(p.pointerLook).toBe(true)
        expect(p.keyboardMovement).toBe(true)
        expect(p.collision).toBe(true)
        expect(p.assetManipulation).toBe(false)
        expect(p.cutaway).toBe(false)
    })
    it('BIRDS_EYE_CUTAWAY: elevated navigation + cutaway on, no first-person', () => {
        const p = resolveCameraModePolicy('BIRDS_EYE_CUTAWAY')
        expect(p.elevatedNavigation).toBe(true)
        expect(p.cutaway).toBe(true)
        expect(p.pointerLook).toBe(false)
        expect(p.collision).toBe(false)
    })
})

describe('walkthrough traversal policy', () => {
    it('BLOCK_WALL: crosses a wall with no traversable opening', () => {
        expect(resolveTraversal({ crossesWall: true, openingsOnPath: [], hasFloorSupport: true })).toBe('BLOCK_WALL')
    })
    it('ALLOW_DOOR: crosses a wall through a traversable door opening', () => {
        expect(resolveTraversal({ crossesWall: true, openingsOnPath: ['TRAVERSABLE_DOOR_OPENING'], hasFloorSupport: true })).toBe('ALLOW_DOOR')
    })
    it('BLOCK_WALL: crosses a wall but only a window/glazing is on the path (window is not a door)', () => {
        const openings: OpeningKind[] = ['NON_TRAVERSABLE_OPENING']
        expect(resolveTraversal({ crossesWall: true, openingsOnPath: openings, hasFloorSupport: true })).toBe('BLOCK_WALL')
    })
    it('ALLOW: same-room movement with no wall crossing', () => {
        expect(resolveTraversal({ crossesWall: false, openingsOnPath: [], hasFloorSupport: true })).toBe('ALLOW')
    })
    it('BLOCK_NO_FLOOR: candidate has no walking surface', () => {
        expect(resolveTraversal({ crossesWall: false, openingsOnPath: [], hasFloorSupport: false })).toBe('BLOCK_NO_FLOOR')
        // no-floor takes precedence even through a door
        expect(resolveTraversal({ crossesWall: true, openingsOnPath: ['TRAVERSABLE_DOOR_OPENING'], hasFloorSupport: false })).toBe('BLOCK_NO_FLOOR')
    })
})

describe('opening classification (window is not a door)', () => {
    it('doors are traversable', () => {
        expect(classifyOpening('BuildingPhysical:Door')).toBe('TRAVERSABLE_DOOR_OPENING')
        expect(classifyOpening('IfcDoor')).toBe('TRAVERSABLE_DOOR_OPENING')
    })
    it('windows/glazing are non-traversable', () => {
        expect(classifyOpening('IfcWindow')).toBe('NON_TRAVERSABLE_OPENING')
        expect(classifyOpening('CurtainGlazing')).toBe('NON_TRAVERSABLE_OPENING')
    })
    it('a generic opening is NOT auto-walkable', () => {
        expect(classifyOpening('BuildingPhysical:Opening')).toBe('NON_TRAVERSABLE_OPENING')
    })
    it('unknown class is a solid boundary (conservative)', () => {
        expect(classifyOpening('SomeWallThing')).toBe('SOLID_BOUNDARY')
    })
})

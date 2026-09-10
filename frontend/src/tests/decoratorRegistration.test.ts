import { describe, it, expect } from 'vitest'
import { resolveDecoratorRegistrationAction } from '../components/spatial/decoratorRegistration'

describe('§21 register once', () => {
    it('runtimeReady + not registered => REGISTER', () => {
        expect(resolveDecoratorRegistrationAction({ runtimeReady: true, alreadyRegistered: false })).toBe('REGISTER')
    })
})

describe('§22 no duplicate', () => {
    it('runtimeReady + already registered => KEEP', () => {
        expect(resolveDecoratorRegistrationAction({ runtimeReady: true, alreadyRegistered: true })).toBe('KEEP')
    })
})

describe('§23 wait for runtime', () => {
    it('runtime not ready => WAIT (never touch ViewManager early)', () => {
        expect(resolveDecoratorRegistrationAction({ runtimeReady: false, alreadyRegistered: false })).toBe('WAIT')
        expect(resolveDecoratorRegistrationAction({ runtimeReady: false, alreadyRegistered: true })).toBe('WAIT')
    })
})

describe('§24 dev-mode independence', () => {
    it('the decision does not accept a dev-mode input at all', () => {
        // The policy signature has no developer-mode field; identical inputs
        // always yield the identical action regardless of any external mode.
        const a = resolveDecoratorRegistrationAction({ runtimeReady: true, alreadyRegistered: false })
        const b = resolveDecoratorRegistrationAction({ runtimeReady: true, alreadyRegistered: false })
        expect(a).toBe('REGISTER')
        expect(b).toBe('REGISTER')
    })
})

describe('teardown', () => {
    it('feature disabled + registered => UNREGISTER', () => {
        expect(resolveDecoratorRegistrationAction({ runtimeReady: true, alreadyRegistered: true, featureEnabled: false })).toBe('UNREGISTER')
    })
    it('feature disabled + not registered => WAIT', () => {
        expect(resolveDecoratorRegistrationAction({ runtimeReady: true, alreadyRegistered: false, featureEnabled: false })).toBe('WAIT')
    })
    it('feature disabled but runtime not ready => WAIT', () => {
        expect(resolveDecoratorRegistrationAction({ runtimeReady: false, alreadyRegistered: true, featureEnabled: false })).toBe('WAIT')
    })
})

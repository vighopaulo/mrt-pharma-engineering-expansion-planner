/**
 * decoratorRegistration — pure, Bentley-free registration-lifecycle policy.
 *
 * Decides what to do with a decorator given only runtime-readiness and current
 * registration state. Deliberately independent of Developer mode, room selection,
 * and assignment state (those are the decorator's runtime inputs, not gates for
 * whether it should be attached to the ViewManager).
 */

export type DecoratorRegistrationAction = 'REGISTER' | 'KEEP' | 'WAIT' | 'UNREGISTER'

export interface DecoratorRegistrationState {
    /** IModelApp + ViewManager are initialized. */
    runtimeReady: boolean
    /** A live decorator is currently attached to the ViewManager. */
    alreadyRegistered: boolean
    /**
     * Whether the FEATURE should be attached at all. For the clinical-program
     * decorator this is always true (the decorator itself decides per-frame
     * whether to draw, via getEnabled); it exists so a future teardown can pass
     * false. Defaults to true at the call site.
     */
    featureEnabled?: boolean
}

/**
 * Resolve the registration action:
 *   - runtime not ready            => WAIT (never touch the ViewManager early)
 *   - feature disabled + attached  => UNREGISTER
 *   - feature disabled             => WAIT
 *   - ready + not attached         => REGISTER
 *   - ready + already attached     => KEEP (idempotent — no duplicate)
 */
export function resolveDecoratorRegistrationAction(state: DecoratorRegistrationState): DecoratorRegistrationAction {
    const featureEnabled = state.featureEnabled ?? true
    if (!state.runtimeReady) return 'WAIT'
    if (!featureEnabled) return state.alreadyRegistered ? 'UNREGISTER' : 'WAIT'
    if (state.alreadyRegistered) return 'KEEP'
    return 'REGISTER'
}

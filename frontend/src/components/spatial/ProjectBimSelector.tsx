/**
 * ProjectBimSelector — NORMAL-MODE product control for the active project BIM.
 * Shows the active BIM name + role and lets the user switch between registered
 * models. Switching PERSISTS the choice (safe metadata only) and reloads /viewer
 * so the persisted selection resolves on next load (no ?imodel= needed).
 *
 * View-only wrt Bentley: switching writes NOTHING to any iModel; it only changes
 * the app's persisted selection and reloads. No raw UUIDs shown in normal mode.
 */
import { useCallback, useMemo, useState } from 'react'
import {
    buildProjectBimRegistry,
    loadPersistedActiveBim,
    resolveActiveProjectBim,
    resolveBimSelectorRowState,
    savePersistedActiveBim,
    type RegisteredBim,
    type ProjectBimRole,
} from '../../lib/projectBim'
import { getViewerConfig, isViewerConfigured, readImodelOverrideFromUrl } from '../../lib/viewerConfig'

const ROLE_LABEL: Record<ProjectBimRole, string> = {
    PRODUCT_DEMO_BIM: 'Product / Demo BIM',
    ENGINEERING_REGRESSION_FIXTURE: 'Engineering Regression Fixture',
}

export function ProjectBimSelector() {
    const [open, setOpen] = useState(false)
    const [switchPendingId, setSwitchPendingId] = useState<string | null>(null)

    // Resolve the current registry + active selection from config (safe; no
    // secrets). getViewerConfig throws if unconfigured — guard it.
    const state = useMemo(() => {
        if (!isViewerConfigured()) return null
        try {
            const cfg = getViewerConfig()
            // Build the registry from the RAW legacy fixture id — NOT the resolved
            // active id (cfg.iModelId). Using cfg.iModelId made the fixture row
            // adopt the clinic's id, so BOTH rows matched activeId and both showed
            // ACTIVE. (DUAL_ACTIVE_ROOT_CAUSE = REGISTRY_STATE_WRONG.)
            const fixtureIModelId = cfg.legacyFixtureIModelId ?? ''
            const registry = buildProjectBimRegistry({ iTwinId: cfg.iTwinId, fixtureIModelId })
            // Re-run resolution to know which model + source is active NOW.
            const override = readImodelOverrideFromUrl()
            const resolved = resolveActiveProjectBim({
                urlOverrideIModelId: override.iModelId,
                urlOverrideITwinId: override.iTwinId,
                persisted: loadPersistedActiveBim(),
                registry,
                legacyFallback: { iModelId: fixtureIModelId, iTwinId: cfg.iTwinId },
            })
            return { registry, activeId: resolved.iModelId, source: resolved.source }
        } catch {
            return null
        }
    }, [])

    const switchTo = useCallback((bim: RegisteredBim) => {
        // Prevent double activation while a switch is pending.
        if (switchPendingId) return
        setSwitchPendingId(bim.iModelId)
        // Persist the safe selection, then reload /viewer (no ?imodel=) so the
        // persisted choice resolves. No Bentley write occurs.
        savePersistedActiveBim({ iModelId: bim.iModelId, iTwinId: bim.iTwinId, displayName: bim.displayName, role: bim.role })
        if (typeof window !== 'undefined') window.location.assign('/viewer')
    }, [switchPendingId])

    if (!state) return null
    const active = state.registry.find((b) => b.iModelId === state.activeId)
    const activeName = active?.displayName ?? 'Unknown BIM'
    const activeRole = active ? ROLE_LABEL[active.role] : ''

    return (
        <div className="project-bim" aria-label="Project BIM">
            <button type="button" className="project-bim-summary" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
                <span className="project-bim-caption">PROJECT BIM</span>
                <span className="project-bim-name">{activeName}</span>
                <span className="project-bim-role">{activeRole} · Ready</span>
            </button>
            {open && (
                <div className="project-bim-list" role="menu">
                    {state.registry.map((b) => {
                        const rowState = resolveBimSelectorRowState({
                            candidateIModelId: b.iModelId,
                            activeIModelId: state.activeId,
                            switchPendingIModelId: switchPendingId ?? undefined,
                        })
                        const isActive = rowState === 'ACTIVE'
                        const isOpening = rowState === 'OPENING'
                        return (
                            <div key={b.iModelId} className={isActive ? 'project-bim-item active' : 'project-bim-item'}>
                                <div className="project-bim-item-text">
                                    <span className="project-bim-item-name">{isActive ? `\u2713 ${b.displayName}` : b.displayName}</span>
                                    <span className="project-bim-item-role">{ROLE_LABEL[b.role]}</span>
                                </div>
                                <button
                                    type="button"
                                    disabled={isActive || isOpening || switchPendingId !== null}
                                    onClick={() => switchTo(b)}
                                >
                                    {isActive ? 'ACTIVE' : isOpening ? 'OPENING…' : 'OPEN'}
                                </button>
                            </div>
                        )
                    })}
                    {switchPendingId && (
                        <div className="project-bim-pending">
                            Opening {state.registry.find((b) => b.iModelId === switchPendingId)?.displayName ?? 'BIM'}…
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

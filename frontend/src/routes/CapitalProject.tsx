import { useEffect, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import {
    analyzeCapitalProject,
    ApiError,
    createLockdown,
    createWhatIf,
    getHealth,
    getProject,
    listCyclotronModels,
    resetWhatIf,
    type AnalyzeRequestBody,
    type AnalyzeResponseBody,
    type CapitalLockdown,
    type CapitalWhatIf,
    type ConstraintMode,
    type CyclotronModelSummary,
    type PathwayConfiguration,
    type ProjectDescriptor,
    type ProjectType,
} from '../lib/api'
import { formatNumber, formatPercent, formatSignedDelta, formatUsd, formatYears } from '../lib/format'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { MetricValue } from '../components/ui/MetricValue'
import { Panel } from '../components/ui/Panel'
import { SectionHeading } from '../components/ui/SectionHeading'
import { StatusPill, type Status } from '../components/ui/StatusPill'
import type { ProjectOutletContext } from './ProjectLayout'
import './CapitalProject.css'

function toApiProjectType(type: 'Greenfield' | 'Retrofit'): ProjectType {
    return type === 'Greenfield' ? 'GREENFIELD' : 'RETROFIT'
}

type EngineStatus = 'checking' | 'connected' | 'unreachable'
type AnalysisState = 'idle' | 'loading' | 'success' | 'error'

export function CapitalProject() {
    const { project } = useOutletContext<ProjectOutletContext>()
    const projectType = toApiProjectType(project.type)

    const [engineStatus, setEngineStatus] = useState<EngineStatus>('checking')
    const [descriptor, setDescriptor] = useState<ProjectDescriptor | null>(null)
    const [descriptorError, setDescriptorError] = useState<string | null>(null)
    const [cyclotronModels, setCyclotronModels] = useState<CyclotronModelSummary[]>([])

    const [constraintMode, setConstraintMode] = useState<ConstraintMode>('CAPACITY')
    const [currentPatients, setCurrentPatients] = useState(0)
    const [targetPatients, setTargetPatients] = useState(0)
    const [budgetUsd, setBudgetUsd] = useState(0)
    const [cyclotronModelId, setCyclotronModelId] = useState('')

    const [analysisState, setAnalysisState] = useState<AnalysisState>('idle')
    const [analysisError, setAnalysisError] = useState<string | null>(null)
    const [analysisResult, setAnalysisResult] = useState<AnalyzeResponseBody | null>(null)
    const [selectedLabel, setSelectedLabel] = useState<'Conventional' | 'MRT'>('Conventional')
    const [lastRequest, setLastRequest] = useState<AnalyzeRequestBody | null>(null)

    const [lockdown, setLockdown] = useState<CapitalLockdown | null>(null)
    const [lockdownState, setLockdownState] = useState<'idle' | 'loading' | 'error'>('idle')
    const [lockdownError, setLockdownError] = useState<string | null>(null)

    const [whatIfValue, setWhatIfValue] = useState(0)
    const [whatIf, setWhatIf] = useState<CapitalWhatIf | null>(null)
    const [whatIfState, setWhatIfState] = useState<'idle' | 'loading' | 'error'>('idle')
    const [whatIfError, setWhatIfError] = useState<string | null>(null)

    useEffect(() => {
        let cancelled = false
        getHealth()
            .then(() => !cancelled && setEngineStatus('connected'))
            .catch(() => !cancelled && setEngineStatus('unreachable'))
        return () => {
            cancelled = true
        }
    }, [])

    useEffect(() => {
        let cancelled = false
        getProject(project.id)
            .then((result) => {
                if (cancelled) return
                setDescriptor(result)
                setCurrentPatients(result.current_patients_per_day)
                setTargetPatients(result.default_target_patients_per_day)
                setBudgetUsd(result.default_maximum_project_budget_usd)
            })
            .catch((error: unknown) => {
                if (cancelled) return
                setDescriptorError(error instanceof ApiError ? error.message : 'Engine service unreachable')
            })
        listCyclotronModels()
            .then((models) => !cancelled && setCyclotronModels(models))
            .catch(() => {
                /* catalog is optional context -- absence does not block analysis */
            })
        return () => {
            cancelled = true
        }
    }, [project.id])

    const groupedCyclotronModels = useMemo(() => {
        const grouped = new Map<string, CyclotronModelSummary[]>()
        for (const model of cyclotronModels) {
            const list = grouped.get(model.manufacturer) ?? []
            list.push(model)
            grouped.set(model.manufacturer, list)
        }
        return grouped
    }, [cyclotronModels])

    const canRunAnalysis =
        descriptor !== null &&
        analysisState !== 'loading' &&
        targetPatients > 0 &&
        (constraintMode !== 'BUDGET' || budgetUsd > 0)

    async function handleRunAnalysis() {
        setAnalysisState('loading')
        setAnalysisError(null)
        try {
            const request: AnalyzeRequestBody = {
                project_id: project.id,
                project_type: projectType,
                constraint_mode: constraintMode,
                current_patients_per_day: currentPatients,
                target_patients_per_day: targetPatients,
                maximum_project_budget_usd: constraintMode === 'BUDGET' ? budgetUsd : null,
                cyclotron_catalog_model_id: cyclotronModelId || null,
            }
            const result = await analyzeCapitalProject(request)
            setLastRequest(request)
            setAnalysisResult(result)
            setSelectedLabel(result.configurations[0]?.label ?? 'Conventional')
            setAnalysisState('success')
        } catch (error) {
            setAnalysisError(error instanceof ApiError ? error.message : 'Engine service unreachable')
            setAnalysisState('error')
        }
    }

    const selectedConfiguration: PathwayConfiguration | undefined = analysisResult?.configurations.find(
        (configuration) => configuration.label === selectedLabel,
    )

    async function handleLockBaseline() {
        if (!lastRequest) return
        setLockdownState('loading')
        setLockdownError(null)
        try {
            const result = await createLockdown({ project_id: project.id, candidate_label: selectedLabel, request: lastRequest })
            setLockdown(result)
            setWhatIf(null)
            setWhatIfState('idle')
            setWhatIfError(null)
            setWhatIfValue(result.request.constraint_mode === 'BUDGET' ? (result.request.maximum_project_budget_usd ?? 0) : result.request.target_patients_per_day)
            setLockdownState('idle')
        } catch (error) {
            setLockdownError(error instanceof ApiError ? error.message : 'Engine service unreachable')
            setLockdownState('error')
        }
    }

    async function handleRunWhatIf() {
        if (!lockdown) return
        setWhatIfState('loading')
        setWhatIfError(null)
        try {
            const request: AnalyzeRequestBody = {
                ...lockdown.request,
                maximum_project_budget_usd: lockdown.request.constraint_mode === 'BUDGET' ? whatIfValue : lockdown.request.maximum_project_budget_usd,
                target_patients_per_day: lockdown.request.constraint_mode === 'CAPACITY' ? whatIfValue : lockdown.request.target_patients_per_day,
            }
            const result = await createWhatIf({ project_id: project.id, request })
            setWhatIf(result)
            setWhatIfState('idle')
        } catch (error) {
            setWhatIfError(error instanceof ApiError ? error.message : 'Engine service unreachable')
            setWhatIfState('error')
        }
    }

    async function handleResetWhatIf() {
        if (!lockdown) return
        try {
            const result = await resetWhatIf({ project_id: project.id })
            setWhatIf(null)
            setWhatIfState('idle')
            setWhatIfError(null)
            setWhatIfValue(result.baseline_request.constraint_mode === 'BUDGET' ? (result.baseline_request.maximum_project_budget_usd ?? 0) : result.baseline_request.target_patients_per_day)
        } catch (error) {
            setWhatIfError(error instanceof ApiError ? error.message : 'Engine service unreachable')
        }
    }

    const constraintFieldLabel = lockdown?.request.constraint_mode === 'BUDGET' ? 'Maximum Project Budget (USD)' : 'Target Patient Capacity (patients/day)'

    function formatConstraintValue(request: AnalyzeRequestBody): string {
        return request.constraint_mode === 'BUDGET' ? formatUsd(request.maximum_project_budget_usd ?? 0) : `${formatNumber(request.target_patients_per_day)} /day`
    }

    const deltaRows =
        lockdown && whatIf
            ? [
                {
                    label: 'Primary Constraint',
                    baseline: formatConstraintValue(lockdown.request),
                    whatIf: formatConstraintValue(whatIf.request),
                    delta:
                        lockdown.request.constraint_mode === 'BUDGET'
                            ? formatSignedDelta((whatIf.request.maximum_project_budget_usd ?? 0) - (lockdown.request.maximum_project_budget_usd ?? 0), formatUsd)
                            : formatSignedDelta(whatIf.request.target_patients_per_day - lockdown.request.target_patients_per_day, (v) => `${formatNumber(v)} /day`),
                },
                {
                    label: 'Patient Capacity',
                    baseline: `${formatNumber(lockdown.result.patient_capacity_per_day, 1)} /day`,
                    whatIf: `${formatNumber(whatIf.result.patient_capacity_per_day, 1)} /day`,
                    delta: formatSignedDelta(whatIf.result.patient_capacity_per_day - lockdown.result.patient_capacity_per_day, (v) => `${formatNumber(v, 1)} /day`),
                },
                {
                    label: 'Project CapEx',
                    baseline: formatUsd(lockdown.result.project_capex_usd),
                    whatIf: formatUsd(whatIf.result.project_capex_usd),
                    delta: formatSignedDelta(whatIf.result.project_capex_usd - lockdown.result.project_capex_usd, formatUsd),
                },
                {
                    label: 'Annual OPEX',
                    baseline: formatUsd(lockdown.result.annual_opex_usd),
                    whatIf: formatUsd(whatIf.result.annual_opex_usd),
                    delta: formatSignedDelta(whatIf.result.annual_opex_usd - lockdown.result.annual_opex_usd, formatUsd),
                },
                {
                    label: 'NPV',
                    baseline: formatUsd(lockdown.result.npv_usd),
                    whatIf: formatUsd(whatIf.result.npv_usd),
                    delta: formatSignedDelta(whatIf.result.npv_usd - lockdown.result.npv_usd, formatUsd),
                },
                {
                    label: 'Budget Headroom',
                    baseline: formatUsd(lockdown.result.budget_headroom_usd),
                    whatIf: formatUsd(whatIf.result.budget_headroom_usd),
                    delta: formatSignedDelta(whatIf.result.budget_headroom_usd - lockdown.result.budget_headroom_usd, formatUsd),
                },
            ]
            : []

    const whatIfConstraintExceeded = whatIf !== null && whatIf.result.project_capex_usd > whatIf.result.budget_usd

    const analysisStatusPill = analysisStatus(analysisState, selectedConfiguration)

    return (
        <main className="app-container capital">
            <div className="capital__header">
                <SectionHeading
                    eyebrow="Capital Project"
                    title="What can be built, expanded or modified — and what it costs."
                />
                <div className="capital__header-status">
                    <StatusPill status={engineStatusPill(engineStatus)} label={engineStatusLabel(engineStatus)} />
                    <StatusPill status={analysisStatusPill.status} label={analysisStatusPill.label} />
                </div>
            </div>

            {descriptorError && (
                <div className="capital__banner capital__banner--error" role="alert">
                    {descriptorError}
                </div>
            )}

            <section className="capital__summary" aria-label="Project status summary">
                <MetricValue label="Project Type" value={project.type} />
                <MetricValue label="Primary Constraint" value={constraintMode === 'BUDGET' ? 'Budget' : 'Capacity'} />
                <MetricValue label="Current Patient Capacity" value={project.type === 'Retrofit' ? `${formatNumber(currentPatients)} /day` : undefined} />
                <MetricValue
                    label="Target / Resulting Capacity"
                    value={
                        selectedConfiguration
                            ? `${formatNumber(selectedConfiguration.patient_capacity_per_day, 1)} /day`
                            : targetPatients > 0
                                ? `${formatNumber(targetPatients)} /day (target)`
                                : undefined
                    }
                />
                <MetricValue label="Project Budget" value={analysisResult ? formatUsd(analysisResult.common_budget_usd) : undefined} />
                <MetricValue
                    label="Cyclotron Fleet"
                    value={cyclotronModelId ? cyclotronModels.find((model) => model.catalog_model_id === cyclotronModelId)?.model : undefined}
                />
                <MetricValue label="Facility / BIM Maturity" value={descriptor?.geometry_basis} />
                <MetricValue label="Analysis Status" value={analysisState === 'success' ? 'Analyzed' : analysisState === 'error' ? 'Failed' : undefined} />
            </section>

            <Panel eyebrow="Define" title="Project Basis &amp; Constraint">
                <div className="capital__basis-grid">
                    <div className="field">
                        <span className="field__label">Primary Constraint</span>
                        <div className="segmented" role="radiogroup" aria-label="Primary constraint">
                            <button
                                type="button"
                                role="radio"
                                aria-checked={constraintMode === 'BUDGET'}
                                className={`segmented__item ${constraintMode === 'BUDGET' ? 'segmented__item--active' : ''}`}
                                onClick={() => setConstraintMode('BUDGET')}
                            >
                                Budget
                            </button>
                            <button
                                type="button"
                                role="radio"
                                aria-checked={constraintMode === 'CAPACITY'}
                                className={`segmented__item ${constraintMode === 'CAPACITY' ? 'segmented__item--active' : ''}`}
                                onClick={() => setConstraintMode('CAPACITY')}
                            >
                                Capacity
                            </button>
                        </div>
                    </div>

                    {project.type === 'Retrofit' && (
                        <label className="field">
                            <span className="field__label">Current Patient Capacity (patients/day)</span>
                            <input
                                className="field__control"
                                type="number"
                                min={0}
                                value={currentPatients}
                                onChange={(event) => setCurrentPatients(Number(event.target.value))}
                            />
                        </label>
                    )}

                    <label className="field">
                        <span className="field__label">Target Patient Capacity (patients/day)</span>
                        <input
                            className="field__control"
                            type="number"
                            min={0}
                            value={targetPatients}
                            onChange={(event) => setTargetPatients(Number(event.target.value))}
                        />
                    </label>

                    {constraintMode === 'BUDGET' && (
                        <label className="field">
                            <span className="field__label">Maximum Project Budget (USD)</span>
                            <input
                                className="field__control"
                                type="number"
                                min={0}
                                step={50000}
                                value={budgetUsd}
                                onChange={(event) => setBudgetUsd(Number(event.target.value))}
                            />
                            <span className="field__hint">{formatUsd(budgetUsd || 0)}</span>
                        </label>
                    )}

                    <label className="field">
                        <span className="field__label">Cyclotron (optional)</span>
                        <select className="field__control" value={cyclotronModelId} onChange={(event) => setCyclotronModelId(event.target.value)}>
                            <option value="">Not selected</option>
                            {[...groupedCyclotronModels.entries()].map(([manufacturer, models]) => (
                                <optgroup key={manufacturer} label={manufacturer}>
                                    {models.map((model) => (
                                        <option key={model.catalog_model_id} value={model.catalog_model_id}>
                                            {model.model}
                                        </option>
                                    ))}
                                </optgroup>
                            ))}
                        </select>
                    </label>

                    <div className="field capital__run-action">
                        <Button variant="primary" onClick={handleRunAnalysis} disabled={!canRunAnalysis}>
                            {analysisState === 'loading' ? 'Running Analysis…' : 'Run Analysis'}
                        </Button>
                    </div>
                </div>

                {analysisError && (
                    <div className="capital__banner capital__banner--error" role="alert">
                        {analysisError}
                    </div>
                )}
            </Panel>

            <div className="capital__main-grid">
                <Panel
                    variant="dominant"
                    eyebrow="Result"
                    title="Project Configuration"
                    className="capital__workspace"
                    action={
                        analysisResult && (
                            <div className="segmented segmented--compact" role="radiogroup" aria-label="Configuration">
                                {analysisResult.configurations.map((configuration) => (
                                    <button
                                        key={configuration.label}
                                        type="button"
                                        role="radio"
                                        aria-checked={configuration.label === selectedLabel}
                                        className={`segmented__item ${configuration.label === selectedLabel ? 'segmented__item--active' : ''}`}
                                        onClick={() => setSelectedLabel(configuration.label)}
                                    >
                                        {configuration.label}
                                    </button>
                                ))}
                            </div>
                        )
                    }
                >
                    {selectedConfiguration ? (
                        <div className="capital__result-grid">
                            <MetricValue label="Feasibility" value={selectedConfiguration.feasible ? 'Feasible' : 'Not Feasible'} />
                            <MetricValue label="Patient Capacity" value={`${formatNumber(selectedConfiguration.patient_capacity_per_day, 1)} /day`} />
                            <MetricValue label="Project CapEx" value={formatUsd(selectedConfiguration.project_capex_usd)} />
                            <MetricValue label="Budget" value={formatUsd(selectedConfiguration.budget_usd)} />
                            <MetricValue label="Budget Headroom" value={formatUsd(selectedConfiguration.budget_headroom_usd)} />
                            <MetricValue label="Reserve Capacity" value={`${formatNumber(selectedConfiguration.reserve_capacity_per_day, 1)} /day`} />
                            <MetricValue label="Additional Scanners" value={formatNumber(selectedConfiguration.additional_scanners)} />
                            <MetricValue label="Binding Constraint" value={selectedConfiguration.binding_constraint} />
                        </div>
                    ) : (
                        <EmptyState
                            title="Project configuration"
                            description="Set a primary constraint above and run the analysis to see a real, engine-computed project configuration here."
                            footnote="Analysis not yet run"
                        />
                    )}

                    <div className="capital__lock-action">
                        <Button variant="primary" onClick={handleLockBaseline} disabled={!selectedConfiguration || lockdownState === 'loading'}>
                            {lockdownState === 'loading' ? 'Locking…' : lockdown ? 'Re-Lock Baseline' : 'Lock Baseline'}
                        </Button>
                        {lockdown && (
                            <StatusPill status="feasible" label={`LOCKED — ${lockdown.candidate_label}`} />
                        )}
                    </div>
                    {lockdownError && (
                        <div className="capital__banner capital__banner--error" role="alert">
                            {lockdownError}
                        </div>
                    )}
                </Panel>

                <Panel eyebrow="Context" title="Engineering &amp; Economics" className="capital__context">
                    {selectedConfiguration ? (
                        <div className="capital__econ-grid">
                            <MetricValue label="Annual Revenue" value={formatUsd(selectedConfiguration.annual_revenue_usd)} />
                            <MetricValue label="Annual OPEX" value={formatUsd(selectedConfiguration.annual_opex_usd)} />
                            <MetricValue label="NPV" value={formatUsd(selectedConfiguration.npv_usd)} />
                            <MetricValue label="ROI" value={formatPercent(selectedConfiguration.roi_pct)} />
                            <MetricValue
                                label="Payback"
                                value={selectedConfiguration.payback_years === null ? 'Not calibrated' : formatYears(selectedConfiguration.payback_years)}
                            />
                            <MetricValue
                                label="Cyclotron Utilization"
                                value={
                                    selectedConfiguration.cyclotron_capacity_status === 'not_calibrated'
                                        ? 'Not calibrated'
                                        : formatPercent(selectedConfiguration.cyclotron_utilization_pct)
                                }
                            />
                        </div>
                    ) : (
                        <EmptyState
                            title="Selected object &amp; consequence panel"
                            description="CapEx, OPEX, NPV, budget headroom and Before / What-If / Delta comparisons for the current selection will appear here once an analysis has run."
                            footnote="Awaiting analysis"
                        />
                    )}
                </Panel>
            </div>

            <div className="capital__lower-grid">
                <Panel eyebrow="Step" title="Analysis">
                    {analysisResult ? (
                        <div className="capital__analysis-detail">
                            <p>
                                Budget source: <strong>{analysisResult.budget_source === 'explicit_budget' ? 'Specified by user' : 'Derived from capacity target'}</strong>
                            </p>
                            {analysisResult.cyclotron_warnings.length > 0 && (
                                <ul className="capital__warning-list">
                                    {analysisResult.cyclotron_warnings.map((warning) => (
                                        <li key={warning}>{warning}</li>
                                    ))}
                                </ul>
                            )}
                            <p className="capital__provenance">{analysisResult.provenance}</p>
                        </div>
                    ) : (
                        <EmptyState
                            title="Analysis"
                            description="Runs the project's governing constraint (budget or capacity) against the engineering engine and returns feasible configurations."
                            footnote="Analysis not yet run"
                        />
                    )}
                </Panel>
                <Panel eyebrow="Step" title="What-If" className="capital__whatif-panel">
                    {!lockdown ? (
                        <EmptyState
                            title="What-If"
                            description="Explore alternatives to the locked configuration and see their engineering and economic consequences."
                            footnote="Lock this configuration to begin What-If"
                        />
                    ) : (
                        <div className="capital__whatif">
                            <div className="capital__whatif-controls">
                                <label className="field">
                                    <span className="field__label">{constraintFieldLabel}</span>
                                    <input
                                        className="field__control"
                                        type="number"
                                        min={0}
                                        value={whatIfValue}
                                        onChange={(event) => setWhatIfValue(Number(event.target.value))}
                                    />
                                </label>
                                <div className="capital__whatif-actions">
                                    <Button variant="primary" onClick={handleRunWhatIf} disabled={whatIfState === 'loading' || whatIfValue <= 0}>
                                        {whatIfState === 'loading' ? 'Running What-If…' : 'Run What-If'}
                                    </Button>
                                    <Button variant="secondary" onClick={handleResetWhatIf} disabled={whatIfState === 'loading'}>
                                        Reset to Baseline
                                    </Button>
                                </div>
                            </div>

                            {whatIfError && (
                                <div className="capital__banner capital__banner--error" role="alert">
                                    {whatIfError}
                                </div>
                            )}

                            {whatIfConstraintExceeded && (
                                <div className="capital__banner capital__banner--warning" role="status">
                                    CONSTRAINT EXCEEDED — Project CapEx ({formatUsd(whatIf!.result.project_capex_usd)}) exceeds the What-If budget (
                                    {formatUsd(whatIf!.result.budget_usd)}), amount over budget{' '}
                                    {formatUsd(whatIf!.result.project_capex_usd - whatIf!.result.budget_usd)}.
                                </div>
                            )}

                            {whatIf ? (
                                <table className="delta-table">
                                    <thead>
                                        <tr>
                                            <th>Metric</th>
                                            <th>Baseline</th>
                                            <th>What-If</th>
                                            <th>Delta</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {deltaRows.map((row) => (
                                            <tr key={row.label}>
                                                <td>{row.label}</td>
                                                <td className="tabular-nums">{row.baseline}</td>
                                                <td className="tabular-nums">{row.whatIf}</td>
                                                <td className="tabular-nums">{row.delta}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            ) : (
                                <p className="capital__whatif-hint">
                                    Baseline locked at {formatConstraintValue(lockdown.request)}. Change the value above and run What-If to compare.
                                </p>
                            )}
                        </div>
                    )}
                </Panel>
                <Panel eyebrow="Step" title="Report">
                    <EmptyState
                        title="Report"
                        description="A detailed engineering and economic report for the current locked configuration."
                        footnote="Awaiting locked configuration"
                    />
                </Panel>
            </div>
        </main>
    )
}

function engineStatusPill(status: EngineStatus): Status {
    if (status === 'connected') return 'feasible'
    if (status === 'unreachable') return 'violated'
    return 'neutral'
}

function engineStatusLabel(status: EngineStatus): string {
    if (status === 'connected') return 'Engine connected'
    if (status === 'unreachable') return 'Engine unreachable'
    return 'Checking engine…'
}

function analysisStatus(state: AnalysisState, configuration: PathwayConfiguration | undefined): { status: Status; label: string } {
    if (state === 'loading') return { status: 'neutral', label: 'Running analysis…' }
    if (state === 'error') return { status: 'violated', label: 'Analysis failed' }
    if (state === 'success' && configuration) {
        return configuration.feasible ? { status: 'feasible', label: 'Feasible' } : { status: 'warning', label: 'Not feasible within constraint' }
    }
    return { status: 'not-connected', label: 'Analysis not yet run' }
}


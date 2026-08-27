import { useOutletContext } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { MetricValue } from '../components/ui/MetricValue'
import { Panel } from '../components/ui/Panel'
import { SectionHeading } from '../components/ui/SectionHeading'
import { StatusPill } from '../components/ui/StatusPill'
import type { ProjectOutletContext } from './ProjectLayout'
import './Operations.css'

export function Operations() {
    const { project } = useOutletContext<ProjectOutletContext>()

    return (
        <main className="app-container operations">
            <div className="operations__header">
                <SectionHeading eyebrow="Operations" title={`How ${project.name} operates through time.`} />
                <div className="operations__header-status">
                    <StatusPill status="not-connected" label="Operational day: not configured" />
                    <StatusPill status="not-connected" label="Clock: awaiting connection" />
                </div>
            </div>

            <div className="operations__main-grid">
                <div className="operations__viewport-column">
                    <Panel variant="dominant" eyebrow="Digital Twin" title="Operational Digital Twin viewport" className="operations__viewport">
                        <EmptyState
                            title="Operational Digital Twin viewport"
                            description="The synchronized OpenUSD scene connection will be established in a subsequent build."
                            footnote="Connect operational scene"
                        />
                    </Panel>

                    <Panel eyebrow="Playback" title="Playback">
                        <div className="operations__playback">
                            <div className="operations__playback-controls">
                                <Button variant="secondary" disabled aria-disabled="true">
                                    Play
                                </Button>
                                <Button variant="secondary" disabled aria-disabled="true">
                                    Pause
                                </Button>
                                <label className="operations__playback-speed">
                                    Speed
                                    <select disabled aria-disabled="true" defaultValue="1x">
                                        <option value="1x">1x</option>
                                    </select>
                                </label>
                            </div>
                            <input
                                type="range"
                                className="operations__timeline"
                                disabled
                                aria-disabled="true"
                                aria-label="Operational timeline (not connected)"
                                min={0}
                                max={100}
                                defaultValue={0}
                            />
                            <StatusPill status="not-connected" label="Awaiting operational scene" />
                        </div>
                    </Panel>
                </div>

                <div className="operations__side-column">
                    <Panel eyebrow="Context" title="Operational Context">
                        <div className="operations__context-metrics">
                            <MetricValue label="Active Patients" />
                            <MetricValue label="Active Missions" />
                            <MetricValue label="Active Batches" />
                            <MetricValue label="Scanners In Use" />
                        </div>
                    </Panel>

                    <Panel eyebrow="Inspector" title="Selected Entity">
                        <EmptyState
                            title="No entity selected"
                            description="Select an entity in the viewport to inspect its mission, state and history once the operational engine is connected."
                            footnote="Awaiting selection"
                        />
                    </Panel>

                    <Panel eyebrow="Events" title="Event Journal">
                        <EmptyState
                            title="Event journal"
                            description="Operational alerts and events will appear here in chronological order."
                            footnote="Awaiting operational scene"
                        />
                    </Panel>
                </div>
            </div>
        </main>
    )
}

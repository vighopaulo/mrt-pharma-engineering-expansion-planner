import { Link, useOutletContext } from 'react-router-dom'
import { SectionHeading } from '../components/ui/SectionHeading'
import type { ProjectOutletContext } from './ProjectLayout'
import './ProjectOverview.css'

export function ProjectOverview() {
    const { project } = useOutletContext<ProjectOutletContext>()

    return (
        <main className="app-container project-overview">
            <SectionHeading eyebrow={project.type} title={project.name} description={project.dataStatus} />

            <div className="project-overview__entries">
                <Link to={`/projects/${project.id}/capital`} className="project-overview__entry">
                    <p className="project-overview__entry-title">Capital Project</p>
                    <p className="project-overview__entry-description">
                        Define, generate and explore a facility design and its engineering/economic consequences.
                    </p>
                </Link>
                <Link to={`/projects/${project.id}/operations`} className="project-overview__entry">
                    <p className="project-overview__entry-title">Operations</p>
                    <p className="project-overview__entry-description">
                        Observe how this facility operates through an operational day.
                    </p>
                </Link>
            </div>
        </main>
    )
}

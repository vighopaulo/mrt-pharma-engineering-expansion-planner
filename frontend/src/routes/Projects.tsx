import { Link } from 'react-router-dom'
import { GlobalNav } from '../components/shell/GlobalNav'
import { SectionHeading } from '../components/ui/SectionHeading'
import { listProjects } from '../lib/demoProject'
import './Projects.css'

export function Projects() {
    const projects = listProjects()

    return (
        <div className="page">
            <GlobalNav />
            <main className="app-container projects">
                <SectionHeading eyebrow="MRT Pharma" title="Projects" description="Open a project to enter Capital Project or Operations." />

                <div className="projects__banner" role="note">
                    Demo project context — this list is a synthetic descriptor for proving navigation, not a connected
                    project database. No engineering results are calculated or stored here.
                </div>

                <ul className="projects__list">
                    {projects.map((project) => (
                        <li key={project.id}>
                            <Link to={`/projects/${project.id}`} className="projects__row">
                                <div>
                                    <p className="projects__row-name">{project.name}</p>
                                    <p className="projects__row-meta">{project.type}</p>
                                </div>
                                <span className="projects__row-status">{project.dataStatus}</span>
                            </Link>
                        </li>
                    ))}
                </ul>
            </main>
        </div>
    )
}

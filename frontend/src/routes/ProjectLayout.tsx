import { Link, Outlet, useParams } from 'react-router-dom'
import { GlobalNav } from '../components/shell/GlobalNav'
import { ProductSwitcher } from '../components/shell/ProductSwitcher'
import { findProject, type Project } from '../lib/demoProject'
import './ProjectLayout.css'

export interface ProjectOutletContext {
    project: Project
}

export function ProjectLayout() {
    const { projectId } = useParams<{ projectId: string }>()
    const project = projectId ? findProject(projectId) : undefined

    if (!project) {
        return (
            <div className="page">
                <GlobalNav />
                <main className="app-container project-layout__not-found">
                    <p>Project not found.</p>
                    <Link to="/projects">Back to Projects</Link>
                </main>
            </div>
        )
    }

    return (
        <div className="page">
            <GlobalNav projectName={project.name} />
            <div className="project-layout__product-bar">
                <div className="app-container project-layout__product-bar-inner">
                    <ProductSwitcher projectId={project.id} />
                </div>
            </div>
            <Outlet context={{ project } satisfies ProjectOutletContext} />
        </div>
    )
}

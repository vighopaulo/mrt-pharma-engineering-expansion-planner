import { Link } from 'react-router-dom'
import './GlobalNav.css'

interface GlobalNavProps {
    projectName?: string
}

/** Top-level application shell navigation — MRT Pharma identity + current project context. */
export function GlobalNav({ projectName }: GlobalNavProps) {
    return (
        <header className="global-nav">
            <div className="app-container global-nav__inner">
                <Link to="/" className="global-nav__brand">
                    <span className="global-nav__brand-mark" aria-hidden="true" />
                    <span className="global-nav__brand-name">MRT&nbsp;Pharma</span>
                    <span className="global-nav__brand-version">2.0</span>
                </Link>
                <nav className="global-nav__links">
                    <Link to="/projects" className="global-nav__link">
                        Projects
                    </Link>
                </nav>
                {projectName && (
                    <div className="global-nav__project" title={projectName}>
                        <span className="global-nav__project-label">Project</span>
                        <span className="global-nav__project-name">{projectName}</span>
                    </div>
                )}
                <div className="global-nav__account" aria-label="Account (placeholder)">
                    <span className="global-nav__account-avatar">MP</span>
                </div>
            </div>
        </header>
    )
}

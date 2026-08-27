import type { ReactNode } from 'react'
import './Panel.css'

interface PanelProps {
    title?: string
    eyebrow?: string
    action?: ReactNode
    children: ReactNode
    /** Panel dominates the layout (main workspace) vs. a supporting/context panel. */
    variant?: 'default' | 'dominant'
    className?: string
}

export function Panel({ title, eyebrow, action, children, variant = 'default', className }: PanelProps) {
    return (
        <section className={`panel panel--${variant} ${className ?? ''}`}>
            {(title || action) && (
                <header className="panel__header">
                    <div>
                        {eyebrow && <p className="panel__eyebrow">{eyebrow}</p>}
                        {title && <h3 className="panel__title">{title}</h3>}
                    </div>
                    {action && <div className="panel__action">{action}</div>}
                </header>
            )}
            <div className="panel__body">{children}</div>
        </section>
    )
}

import type { ReactNode } from 'react'
import './EmptyState.css'

interface EmptyStateProps {
    title: string
    description: string
    footnote?: string
    action?: ReactNode
}

/** Truthful structural placeholder — never substitutes fabricated data. */
export function EmptyState({ title, description, footnote, action }: EmptyStateProps) {
    return (
        <div className="empty-state">
            <p className="empty-state__title">{title}</p>
            <p className="empty-state__description">{description}</p>
            {footnote && <p className="empty-state__footnote">{footnote}</p>}
            {action}
        </div>
    )
}

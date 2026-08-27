import './StatusPill.css'

export type Status = 'feasible' | 'warning' | 'violated' | 'neutral' | 'not-connected'

interface StatusPillProps {
    status: Status
    label: string
}

export function StatusPill({ status, label }: StatusPillProps) {
    return (
        <span className={`status-pill status-pill--${status}`}>
            <span className="status-pill__dot" aria-hidden="true" />
            {label}
        </span>
    )
}

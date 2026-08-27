import './MetricValue.css'

interface MetricValueProps {
    label: string
    /** Omit (or pass undefined) when the backend value is not yet connected — never fabricate a number. */
    value?: string | number
    unit?: string
}

const NOT_CONNECTED = 'Not yet connected'

export function MetricValue({ label, value, unit }: MetricValueProps) {
    const isConnected = value !== undefined && value !== null && value !== ''
    return (
        <div className="metric-value">
            <p className="metric-value__label">{label}</p>
            <p className={`metric-value__value tabular-nums ${isConnected ? '' : 'metric-value__value--not-connected'}`}>
                {isConnected ? value : NOT_CONNECTED}
                {isConnected && unit && <span className="metric-value__unit"> {unit}</span>}
            </p>
        </div>
    )
}

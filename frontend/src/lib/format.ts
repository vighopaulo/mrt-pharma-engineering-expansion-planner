/** Presentation-only number formatting -- never performs engineering calculation. */

export function formatUsd(value: number): string {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
}

export function formatNumber(value: number, fractionDigits = 0): string {
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: fractionDigits }).format(value)
}

export function formatPercent(value: number, fractionDigits = 1): string {
    return `${value.toFixed(fractionDigits)}%`
}

export function formatYears(value: number, fractionDigits = 1): string {
    return `${value.toFixed(fractionDigits)} yr`
}

/**
 * Presentation-only signed delta between two already-authoritative engine
 * values (never a second engineering computation -- see capital_project_api.py
 * section 13/43 for the corresponding backend documentation of this same
 * distinction).
 */
export function formatSignedDelta(value: number, formatFn: (value: number) => string): string {
    if (value === 0) return formatFn(0)
    const sign = value > 0 ? '+' : '\u2212'
    return `${sign}${formatFn(Math.abs(value))}`
}

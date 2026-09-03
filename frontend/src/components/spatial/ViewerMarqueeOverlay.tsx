/**
 * ViewerMarqueeOverlay — restrained selection rectangle drawn during an active
 * marquee (bounding-box) multi-select gesture. UI-only overlay driven by the
 * manipulation tool's marquee state in the overlay module; no engineering state.
 * View-pixel coordinates are positioned relative to the viewport stage.
 */
import { useSyncExternalStore } from 'react'
import { getMarqueeRect, subscribeMarquee } from './spatialAssetOverlay'

export function ViewerMarqueeOverlay() {
    const rect = useSyncExternalStore(subscribeMarquee, getMarqueeRect)
    if (!rect) return null
    const left = Math.min(rect.startX, rect.currentX)
    const top = Math.min(rect.startY, rect.currentY)
    const width = Math.abs(rect.currentX - rect.startX)
    const height = Math.abs(rect.currentY - rect.startY)
    return (
        <div
            className="mrt-marquee-rect"
            style={{ left, top, width, height }}
            aria-hidden="true"
        />
    )
}

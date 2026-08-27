/**
 * Synthetic demo project descriptor.
 *
 * There is no backend project API connected yet (Build 1 is shell-only —
 * see the architecture audit). This module stands in for that future API
 * so routing/navigation can be proven end-to-end. Every value here is a
 * project DESCRIPTOR (name/type/status), never a calculated engineering
 * result — no CapEx/OPEX/NPV/capacity numbers are invented here.
 *
 * Replace this module's data source with a real backend call in the next
 * build; the shape (`Project`) is intentionally small so that swap is
 * mechanical.
 */

export type ProjectType = 'Greenfield' | 'Retrofit'

export interface Project {
    id: string
    name: string
    type: ProjectType
    /** Always true for this module's data — flags synthetic descriptors to the UI. */
    isDemo: boolean
    dataStatus: string
}

export const DEMO_PROJECT: Project = {
    id: 'oncology-expansion-demo',
    name: 'Oncology Expansion',
    type: 'Retrofit',
    isDemo: true,
    dataStatus: 'Demo project context — not calculated engineering output',
}

const PROJECTS: Project[] = [DEMO_PROJECT]

export function listProjects(): Project[] {
    return PROJECTS
}

export function findProject(projectId: string): Project | undefined {
    return PROJECTS.find((project) => project.id === projectId)
}

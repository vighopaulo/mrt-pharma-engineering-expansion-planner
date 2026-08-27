import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from '../App'
import { DEMO_PROJECT } from '../lib/demoProject'

function renderAt(path: string) {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <App />
        </MemoryRouter>,
    )
}

describe('application shell', () => {
    it('1. renders the application shell (brand + navigation) on Home', () => {
        renderAt('/')
        expect(screen.getAllByText('MRT Pharma').length).toBeGreaterThan(0)
        expect(screen.getByRole('link', { name: 'Projects' })).toBeInTheDocument()
    })

    it('renders the MRT Pharma 2.0 version mark in the application shell', () => {
        renderAt('/')
        expect(screen.getByText('2.0')).toBeInTheDocument()
    })

    it('2. renders the Projects route with the demo project listed', () => {
        renderAt('/projects')
        expect(screen.getByRole('heading', { name: 'Projects' })).toBeInTheDocument()
        expect(screen.getByText(DEMO_PROJECT.name)).toBeInTheDocument()
    })

    it('3. project route preserves project identity', () => {
        renderAt(`/projects/${DEMO_PROJECT.id}`)
        expect(screen.getAllByText(DEMO_PROJECT.name).length).toBeGreaterThan(0)
    })

    it('4. Capital Project route renders', () => {
        renderAt(`/projects/${DEMO_PROJECT.id}/capital`)
        expect(screen.getAllByText('Capital Project').length).toBeGreaterThan(0)
        expect(screen.getByRole('heading', { name: /can be built, expanded or modified/i })).toBeInTheDocument()
    })

    it('5. Operations route renders', () => {
        renderAt(`/projects/${DEMO_PROJECT.id}/operations`)
        expect(screen.getAllByText('Operations').length).toBeGreaterThan(0)
        expect(screen.getAllByText('Operational Digital Twin viewport').length).toBeGreaterThan(0)
    })

    it('6. switching Capital/Operations preserves the same project ID in the URL', async () => {
        const user = userEvent.setup()
        renderAt(`/projects/${DEMO_PROJECT.id}/capital`)

        const operationsLink = screen.getByRole('link', { name: 'Operations' })
        expect(operationsLink).toHaveAttribute('href', `/projects/${DEMO_PROJECT.id}/operations`)
        await user.click(operationsLink)

        const capitalLink = screen.getByRole('link', { name: 'Capital Project' })
        expect(capitalLink).toHaveAttribute('href', `/projects/${DEMO_PROJECT.id}/capital`)
        expect(screen.getAllByText(DEMO_PROJECT.name).length).toBeGreaterThan(0)
    })

    it('7. synthetic demo project is clearly identified', () => {
        renderAt('/projects')
        expect(screen.getAllByText(/Demo project context/i).length).toBeGreaterThan(0)
    })

    it('8. no fake engineering metric values are hardcoded on Capital Project', () => {
        renderAt(`/projects/${DEMO_PROJECT.id}/capital`)
        const notConnected = screen.getAllByText('Not yet connected')
        expect(notConnected.length).toBeGreaterThanOrEqual(5)
        expect(screen.queryByText(/\$\d/)).not.toBeInTheDocument()
    })

    it('9. Operations playback controls are disabled', () => {
        renderAt(`/projects/${DEMO_PROJECT.id}/operations`)
        expect(screen.getByRole('button', { name: 'Play' })).toBeDisabled()
        expect(screen.getByRole('button', { name: 'Pause' })).toBeDisabled()
        expect(screen.getByLabelText(/Operational timeline/i)).toBeDisabled()
    })

    it('unknown project id shows a truthful not-found state, never fabricated data', () => {
        renderAt('/projects/does-not-exist')
        expect(screen.getByText('Project not found.')).toBeInTheDocument()
    })
})

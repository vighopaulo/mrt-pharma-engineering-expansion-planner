import { NavLink } from 'react-router-dom'
import './ProductSwitcher.css'

interface ProductSwitcherProps {
    projectId: string
}

/** The two-product distinction is the primary navigation decision inside a project. */
export function ProductSwitcher({ projectId }: ProductSwitcherProps) {
    return (
        <nav className="product-switcher" aria-label="Product">
            <NavLink
                to={`/projects/${projectId}/capital`}
                className={({ isActive }) => `product-switcher__item ${isActive ? 'product-switcher__item--active' : ''}`}
            >
                Capital Project
            </NavLink>
            <NavLink
                to={`/projects/${projectId}/operations`}
                className={({ isActive }) => `product-switcher__item ${isActive ? 'product-switcher__item--active' : ''}`}
            >
                Operations
            </NavLink>
        </nav>
    )
}

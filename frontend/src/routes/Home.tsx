import { Link } from 'react-router-dom'
import { GlobalNav } from '../components/shell/GlobalNav'
import { Button } from '../components/ui/Button'
import './Home.css'

export function Home() {
    return (
        <div className="page">
            <GlobalNav />
            <main className="app-container home">
                <p className="home__eyebrow">MRT Pharma</p>
                <h1 className="home__title">Oncology facility engineering, from capital design to daily operation.</h1>
                <p className="home__description">
                    One engineering core. Two ways to use it: plan and evaluate a capital project, or watch a facility
                    operate through an operational day.
                </p>
                <div className="home__actions">
                    <Link to="/projects">
                        <Button variant="primary">View Projects</Button>
                    </Link>
                </div>
            </main>
        </div>
    )
}

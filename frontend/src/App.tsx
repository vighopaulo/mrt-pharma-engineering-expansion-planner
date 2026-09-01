import { Route, Routes } from 'react-router-dom'
import { BentleyViewer } from './routes/BentleyViewer'
import { CapitalProject } from './routes/CapitalProject'
import { Home } from './routes/Home'
import { Operations } from './routes/Operations'
import { ProjectLayout } from './routes/ProjectLayout'
import { ProjectOverview } from './routes/ProjectOverview'
import { Projects } from './routes/Projects'
import { SigninCallback } from './routes/SigninCallback'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/projects" element={<Projects />} />
      <Route path="/projects/:projectId" element={<ProjectLayout />}>
        <Route index element={<ProjectOverview />} />
        <Route path="capital" element={<CapitalProject />} />
        <Route path="operations" element={<Operations />} />
      </Route>
      <Route path="/viewer" element={<BentleyViewer />} />
      <Route path="/signin-callback" element={<SigninCallback />} />
    </Routes>
  )
}

export default App

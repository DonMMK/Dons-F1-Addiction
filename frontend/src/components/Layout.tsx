import { Outlet, NavLink } from 'react-router-dom'

export default function Layout() {
  return (
    <>
      <nav className="navbar">
        <div className="container">
          <NavLink to="/" className="navbar__brand">
            <span className="navbar__brand-icon">🏎️</span>
            Don's F1 Addiction
          </NavLink>
          <ul className="navbar__links">
            <li>
              <NavLink to="/" end className={({ isActive }) => `navbar__link${isActive ? ' navbar__link--active' : ''}`}>
                Home
              </NavLink>
            </li>
            <li>
              <NavLink to="/prediction" className={({ isActive }) => `navbar__link${isActive ? ' navbar__link--active' : ''}`}>
                Prediction
              </NavLink>
            </li>
            <li>
              <NavLink to="/ghost-car" className={({ isActive }) => `navbar__link${isActive ? ' navbar__link--active' : ''}`}>
                Ghost Car
              </NavLink>
            </li>
            <li>
              <NavLink to="/best-car" className={({ isActive }) => `navbar__link${isActive ? ' navbar__link--active' : ''}`}>
                Best Car
              </NavLink>
            </li>
          </ul>
        </div>
      </nav>

      <main className="page">
        <div className="container">
          <Outlet />
        </div>
      </main>

      <footer className="footer">
        <div className="container">
          Powered by FastF1 &middot; Built by Don &middot; Not affiliated with Formula 1
        </div>
      </footer>
    </>
  )
}

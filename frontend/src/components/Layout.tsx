import { Outlet, NavLink } from "react-router-dom";
import { Suspense } from "react";
const links = [
  ["/", "Overview"],
  ["/weekend", "Weekend by Weekend"],
  ["/prediction", "Race Predictor"],
  ["/ghost-car", "Ghost Car"],
  ["/looking-back", "Looking Back"],
];
export default function Layout() {
  return (
    <>
      <nav className="navbar" aria-label="Main navigation">
        <div className="container">
          <NavLink className="navbar__brand" to="/">
            <span className="navbar__brand-icon">🏎</span>Don's F1 Addiction
          </NavLink>
          <ul className="navbar__links">
            {links.map(([to, label]) => (
              <li key={to}>
                <NavLink
                  end={to === "/"}
                  to={to}
                  className={({ isActive }) =>
                    `navbar__link${isActive ? " navbar__link--active" : ""}`
                  }
                >
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      </nav>
      <main className="page">
        <div className="container">
          <Suspense
            fallback={
              <p role="status" className="notice">
                Loading analysis…
              </p>
            }
          >
            <Outlet />
          </Suspense>
        </div>
      </main>
      <footer className="footer">
        <div className="container">
          OpenF1 · FastF1 · Jolpica-F1 · FIA documents · Linked calendar
          publishers · Free to explore · Built by Don · Not affiliated with
          Formula 1
        </div>
      </footer>
    </>
  );
}

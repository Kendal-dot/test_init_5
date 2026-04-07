import { NavLink } from 'react-router-dom'

export default function Navbar() {
  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <span className="brand-icon">🎙</span>
        <span className="brand-name">MötesTranskriberaren</span>
      </div>
      <ul className="navbar-links">
        <li>
          <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>
            Ladda upp
          </NavLink>
        </li>
        <li>
          <NavLink to="/jobs" className={({ isActive }) => isActive ? 'active' : ''}>
            Jobb
          </NavLink>
        </li>
        <li>
          <NavLink to="/search" className={({ isActive }) => isActive ? 'active' : ''}>
            Sök
          </NavLink>
        </li>
        <li>
          <NavLink to="/live" className={({ isActive }) => isActive ? 'active' : ''}>
            Live
          </NavLink>
        </li>
        <li>
          <NavLink to="/speakers" className={({ isActive }) => isActive ? 'active' : ''}>
            Röstprofiler
          </NavLink>
        </li>
      </ul>
    </nav>
  )
}

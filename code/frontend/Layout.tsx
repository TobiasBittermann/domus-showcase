import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router'

import { HouseholdGate } from './HouseholdGate'

const navItems = [
  { to: '/', label: 'Start', icon: '🏠', end: true },
  { to: '/expenses', label: 'Ausgaben', icon: '💶' },
  { to: '/fixed-costs', label: 'Fixkosten', icon: '📅' },
  { to: '/stores', label: 'Geschäfte', icon: '🏪' },
  { to: '/shopping', label: 'Einkaufsliste', icon: '🛒' },
  { to: '/chores', label: 'Putzplan', icon: '🧹' },
  { to: '/household', label: 'Haushalt', icon: '👥' },
]

/**
 * Base layout with a sidebar. From tablet width up it is always visible; on
 * phones it slides in from the left as a drawer via the menu button.
 */
export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)
  useEffect(() => {
    if (!menuOpen) return
    const onKeyDown = (e: KeyboardEvent) => e.key === 'Escape' && setMenuOpen(false)
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [menuOpen])

  return (
    <div className="app">
      <button
        type="button"
        className="menu-button"
        aria-label="Menü öffnen"
        aria-controls="sidebar"
        aria-expanded={menuOpen}
        onClick={() => setMenuOpen(true)}
      >
        ☰
      </button>

      {menuOpen && <div className="sidebar-backdrop" onClick={() => setMenuOpen(false)} />}

      <aside id="sidebar" className={`sidebar${menuOpen ? ' open' : ''}`}>
        <div className="sidebar-brand">
          <img src="/favicon.svg" alt="" width={28} height={28} />
          <span>Domus</span>
        </div>
        <nav aria-label="Hauptnavigation">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className="nav-link"
              // Close the drawer after navigating
              onClick={() => setMenuOpen(false)}
            >
              <span className="nav-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="app-main">
        <HouseholdGate>
          <Outlet />
        </HouseholdGate>
      </main>
    </div>
  )
}

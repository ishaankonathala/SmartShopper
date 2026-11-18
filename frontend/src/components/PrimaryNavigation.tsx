import { NavLink } from 'react-router-dom'
import { APP_NAV_ITEMS } from './navigationItems'

type PrimaryNavigationProps = {
  onNavigate?: () => void
}

export function PrimaryNavigation({ onNavigate }: PrimaryNavigationProps) {
  return (
    <nav aria-label="Primary navigation">
      <p className="mb-3 px-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-navy-muted/75">
        Your space
      </p>
      <ul className="space-y-1">
        {APP_NAV_ITEMS.map(({ icon: Icon, label, to }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={to === '/'}
              onClick={onNavigate}
              className={({ isActive }) =>
                [
                  'group flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition',
                  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage',
                  isActive
                    ? 'bg-sage-soft text-sage-strong'
                    : 'text-navy-muted hover:bg-ivory hover:text-navy',
                ].join(' ')
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    aria-hidden
                    className={`h-[18px] w-[18px] shrink-0 ${
                      isActive ? 'text-sage-strong' : 'text-navy-muted'
                    }`}
                  />
                  <span>{label}</span>
                  {isActive && (
                    <span
                      aria-hidden
                      className="ml-auto h-1.5 w-1.5 rounded-full bg-sage-strong"
                    />
                  )}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

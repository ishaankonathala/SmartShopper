import { useEffect, useState } from 'react'
import { Bell, CircleUserRound, Menu, X } from 'lucide-react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { BrandLockup } from '../components/BrandLockup'
import { PrimaryNavigation } from '../components/PrimaryNavigation'
import { APP_NAV_ITEMS } from '../components/navigationItems'
import { ShoppingProfilePanel } from '../components/ShoppingProfilePanel'

export function AppShell() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const location = useLocation()
  const currentPage = APP_NAV_ITEMS.find(
    (item) => item.to === location.pathname,
  )
  const pageTitle =
    location.pathname === '/'
      ? 'Find the right products, with AI.'
      : currentPage?.label ?? 'Shop with AI'
  const showShoppingProfile =
    location.pathname === '/' || location.pathname === '/discover'

  useEffect(() => {
    if (!mobileNavOpen) return

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setMobileNavOpen(false)
    }

    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [mobileNavOpen])

  return (
    <div className="min-h-screen bg-ivory">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-56 flex-col border-r border-border bg-surface px-5 py-7 lg:flex">
        <BrandLockup />
        <div className="mt-10">
          <PrimaryNavigation />
        </div>
      </aside>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="absolute inset-0 h-full w-full bg-navy/35"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside
            id="mobile-navigation"
            aria-label="Mobile navigation"
            aria-modal="true"
            className="relative flex h-full w-[min(20rem,85vw)] flex-col border-r border-border bg-surface px-6 py-6 shadow-soft"
            role="dialog"
          >
            <div className="flex items-center justify-between">
              <BrandLockup onNavigate={() => setMobileNavOpen(false)} />
              <button
                type="button"
                aria-label="Close navigation"
                onClick={() => setMobileNavOpen(false)}
                className="rounded-xl p-2 text-navy-muted transition hover:bg-ivory hover:text-navy focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
              >
                <X aria-hidden className="h-5 w-5" />
              </button>
            </div>
            <div className="mt-10">
              <PrimaryNavigation onNavigate={() => setMobileNavOpen(false)} />
            </div>
          </aside>
        </div>
      )}

      <div className="min-h-screen lg:pl-56">
        <div className="mx-auto max-w-[1600px] px-4 sm:px-8 lg:px-7">
          <header className="sticky top-0 z-20 -mx-4 border-b border-border/80 bg-ivory/90 px-4 py-3 backdrop-blur-md sm:-mx-8 sm:px-8 lg:-mx-7 lg:px-7">
            <div className="flex min-h-12 items-center gap-3">
              <button
                type="button"
                aria-label="Open navigation"
                aria-expanded={mobileNavOpen}
                aria-controls={mobileNavOpen ? 'mobile-navigation' : undefined}
                onClick={() => setMobileNavOpen(true)}
                className="rounded-xl border border-border bg-surface p-2.5 text-navy transition hover:bg-ivory lg:hidden"
              >
                <Menu aria-hidden className="h-5 w-5" />
              </button>
              <div className="lg:hidden">
                <BrandLockup />
              </div>
              <div className="hidden min-w-0 lg:block">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sage">
                  SmartShopper AI
                </p>
                <h1 className="mt-1 font-display text-3xl font-semibold text-navy">
                  {pageTitle}
                </h1>
              </div>
              <span
                aria-hidden
                className="hidden h-9 w-9 items-center justify-center rounded-full text-navy-muted sm:flex"
              >
                <Bell className="h-5 w-5" />
              </span>
              <Link
                to="/preferences"
                className="ml-auto flex min-w-0 items-center gap-3 rounded-full border border-border bg-surface py-1.5 pl-1.5 pr-3 transition hover:border-border-strong hover:shadow-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sage-soft text-sage-strong">
                  <CircleUserRound aria-hidden className="h-5 w-5" />
                </span>
                <span className="hidden text-left sm:block">
                  <span className="block text-xs font-medium text-navy-muted">
                    Your account
                  </span>
                  <span className="block text-sm font-semibold text-navy">
                    Shopper profile
                  </span>
                </span>
                <span className="sr-only sm:hidden">Open your profile</span>
              </Link>
            </div>
            <div className="mt-3 lg:hidden">
              <h1 className="font-display text-2xl font-semibold text-navy">
                {pageTitle}
              </h1>
            </div>
          </header>

          <main className="py-5 sm:py-6">
            <div
              className={
                showShoppingProfile
                  ? 'grid gap-6 lg:grid-cols-[minmax(0,1fr)_15rem] 2xl:gap-8'
                  : ''
              }
            >
              <div className="min-w-0">
                <Outlet />
              </div>
              {showShoppingProfile && (
                <aside className="hidden lg:block">
                  <ShoppingProfilePanel />
                </aside>
              )}
            </div>
            {showShoppingProfile && (
              <div className="mt-8 lg:hidden">
                <ShoppingProfilePanel />
              </div>
            )}
            <footer className="mt-12 border-t border-border pt-5 text-xs text-navy-muted">
              A more considered way to shop.
            </footer>
          </main>
        </div>
      </div>

    </div>
  )
}

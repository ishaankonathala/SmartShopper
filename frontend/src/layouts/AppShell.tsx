import type { ReactNode } from 'react'

type AppShellProps = {
  children: ReactNode
}

/**
 * Minimal Phase 1 shell — brand + content only.
 * Full navigation arrives when feature screens are real (Phase 7).
 */
export function AppShell({ children }: AppShellProps) {
  return (
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-6 py-10 sm:px-10">
      <header className="mb-14 flex items-baseline justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sage">
            SmartShopper
          </p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-navy sm:text-4xl">
            Shopping intelligence
          </h1>
        </div>
        <p className="hidden text-sm text-navy-muted sm:block">Phase 1 · Foundation</p>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="mt-16 border-t border-border pt-6 text-sm text-navy-muted">
        Preferences · Catalogue · Recommendations · Decision Lab — coming next.
      </footer>
    </div>
  )
}

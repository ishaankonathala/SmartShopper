import { Activity, Database, Server } from 'lucide-react'
import type { ReactNode } from 'react'
import { StatusPill } from '../components/StatusPill'
import { useHealth } from '../hooks/useHealth'

export function FoundationPage() {
  const health = useHealth()

  return (
    <section className="space-y-10">
      <div className="max-w-2xl">
        <h2 className="font-display text-2xl font-semibold text-navy sm:text-3xl">
          Service status
        </h2>
        <p className="mt-3 text-base leading-relaxed text-navy-muted">
          A quick check that SmartShopper can reach the API and its database.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <CheckCard
          icon={<Server className="h-5 w-5 text-sage" aria-hidden />}
          title="API"
          description="FastAPI process"
        >
          {health.status === 'loading' && <StatusPill tone="neutral" label="Checking…" />}
          {health.status === 'ready' && (
            <StatusPill
              tone={health.data.status === 'ok' ? 'success' : 'warning'}
              label={health.data.status.toUpperCase()}
            />
          )}
          {health.status === 'error' && <StatusPill tone="danger" label="Unreachable" />}
        </CheckCard>

        <CheckCard
          icon={<Database className="h-5 w-5 text-sage" aria-hidden />}
          title="Database"
          description="SQLite connectivity"
        >
          {health.status === 'loading' && <StatusPill tone="neutral" label="Checking…" />}
          {health.status === 'ready' && (
            <StatusPill
              tone={health.data.database === 'connected' ? 'success' : 'danger'}
              label={health.data.database}
            />
          )}
          {health.status === 'error' && <StatusPill tone="danger" label="Unknown" />}
        </CheckCard>

        <CheckCard
          icon={<Activity className="h-5 w-5 text-sage" aria-hidden />}
          title="Environment"
          description="Runtime label"
        >
          {health.status === 'ready' ? (
            <StatusPill tone="neutral" label={health.data.environment} />
          ) : (
            <StatusPill tone="neutral" label="—" />
          )}
        </CheckCard>
      </div>

      {health.status === 'ready' && (
        <div className="rounded-xl border border-border bg-surface p-6 shadow-soft">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sage">
            Live health payload
          </p>
          <pre className="mt-4 overflow-x-auto text-sm leading-relaxed text-navy-muted">
            {JSON.stringify(health.data, null, 2)}
          </pre>
        </div>
      )}

      {health.status === 'error' && (
        <div className="rounded-xl border border-border bg-surface p-6 shadow-soft">
          <p className="font-medium text-danger">Could not reach the backend</p>
          <p className="mt-2 text-sm leading-relaxed text-navy-muted">
            {health.message}. Start the API with{' '}
            <code className="rounded bg-ivory-deep px-1.5 py-0.5 text-navy">
              uvicorn app.main:app --reload
            </code>{' '}
            from the <code className="rounded bg-ivory-deep px-1.5 py-0.5">backend</code>{' '}
            folder, then refresh.
          </p>
        </div>
      )}
    </section>
  )
}

type CheckCardProps = {
  icon: ReactNode
  title: string
  description: string
  children: ReactNode
}

function CheckCard({ icon, title, description, children }: CheckCardProps) {
  return (
    <article className="rounded-xl border border-border bg-surface p-5 shadow-soft">
      <div className="flex items-center gap-3">
        {icon}
        <div>
          <h3 className="text-sm font-semibold text-navy">{title}</h3>
          <p className="text-xs text-navy-muted">{description}</p>
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </article>
  )
}

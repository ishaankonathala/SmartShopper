import { useEffect, useState } from 'react'
import {
  Activity,
  CalendarClock,
  CircleX,
  Eye,
  Heart,
  LoaderCircle,
  RefreshCw,
  ShoppingBag,
  ThumbsDown,
} from 'lucide-react'
import { ApiRequestError, getHistory } from '../services/api'
import {
  AMAZON_RECENTLY_VIEWED_STORAGE_KEY,
  readAmazonRecentlyViewed,
} from '../services/amazonRecentlyViewed'
import type { AmazonRecentlyViewedItem } from '../services/amazonRecentlyViewed'
import type { HistoryAction, ShoppingHistory } from '../types/history'
import { DEMO_USER_ID } from '../config'
import { AmazonCatalogueImage } from '../components/AmazonCatalogueCard'

const historyActions: {
  value: HistoryAction
  label: string
}[] = [
  { value: 'viewed', label: 'Viewed' },
  { value: 'liked', label: 'Liked' },
  { value: 'purchased', label: 'Purchased' },
  { value: 'dismissed', label: 'Dismissed' },
  { value: 'not_interested', label: 'Not Interested' },
]

const actionLabels: Record<HistoryAction, string> = {
  viewed: 'Viewed',
  liked: 'Liked',
  purchased: 'Purchased',
  dismissed: 'Dismissed',
  not_interested: 'Not Interested',
}

const dateTimeFormatter = new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

const priceFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

function getActionIcon(action: HistoryAction) {
  switch (action) {
    case 'viewed':
      return Eye
    case 'liked':
      return Heart
    case 'purchased':
      return ShoppingBag
    case 'dismissed':
      return CircleX
    case 'not_interested':
      return ThumbsDown
  }
}

function isHistoryAction(value: string): value is HistoryAction {
  return historyActions.some((action) => action.value === value)
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError && error.status >= 500) {
    return 'Your shopping history is temporarily unavailable. Please try again.'
  }
  if (error instanceof TypeError) {
    return 'We could not connect to your shopping history. Check your connection and try again.'
  }
  return 'We could not load your shopping history. Please try again.'
}

function formatDateTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Date unavailable'
    : dateTimeFormatter.format(date)
}

export function ShoppingHistoryPage() {
  const [actionFilter, setActionFilter] = useState<HistoryAction | ''>('')
  const [history, setHistory] = useState<ShoppingHistory[]>([])
  const [amazonRecentlyViewed, setAmazonRecentlyViewed] = useState<
    AmazonRecentlyViewedItem[]
  >([])
  const [amazonHistoryError, setAmazonHistoryError] = useState<string | null>(
    null,
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    function refreshAmazonHistory() {
      const result = readAmazonRecentlyViewed()
      setAmazonRecentlyViewed(result.items)
      setAmazonHistoryError(result.error)
    }

    refreshAmazonHistory()
    function handleStorageChange(event: StorageEvent) {
      if (
        event.key === null ||
        event.key === AMAZON_RECENTLY_VIEWED_STORAGE_KEY
      ) {
        refreshAmazonHistory()
      }
    }
    window.addEventListener('storage', handleStorageChange)
    return () => window.removeEventListener('storage', handleStorageChange)
  }, [])

  useEffect(() => {
    let active = true

    getHistory(DEMO_USER_ID, actionFilter || undefined)
      .then((events) => {
        if (active) setHistory(events)
      })
      .catch((requestError: unknown) => {
        if (active) setError(getErrorMessage(requestError))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [actionFilter, retryCount])

  function updateFilter(value: string) {
    setLoading(true)
    setError(null)
    setActionFilter(isHistoryAction(value) ? value : '')
  }

  function retry() {
    setLoading(true)
    setError(null)
    setRetryCount((count) => count + 1)
  }

  const filteredLabel = actionFilter ? actionLabels[actionFilter].toLowerCase() : null
  const showAmazonHistory = !actionFilter || actionFilter === 'viewed'

  return (
    <section className="space-y-6">
      <header className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sage">
          Your shopping journey
        </p>
        <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-navy sm:text-4xl">
          Shopping history
        </h2>
        <p className="mt-3 text-sm leading-6 text-navy-muted sm:text-base">
          Revisit the products and activities that are part of your shopping journey.
          Activities are shown newest first.
        </p>
      </header>

        {showAmazonHistory && (
          <section
            aria-labelledby="amazon-recently-viewed-title"
            className="rounded-3xl border border-border bg-surface p-5 shadow-soft sm:p-7"
          >
            <div className="flex items-start gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sage-soft text-sage-strong">
                <Eye aria-hidden className="h-5 w-5" />
              </span>
              <div>
                <h3
                  id="amazon-recently-viewed-title"
                  className="font-display text-xl font-semibold text-navy"
                >
                  Recently viewed · Amazon catalogue
                </h3>
                <p className="mt-1 text-xs leading-5 text-navy-muted">
                  Stored locally in this browser, separately from curated product
                  activity. Saved snapshots remain useful if a catalogue listing
                  changes or is removed.
                </p>
              </div>
            </div>

            {amazonHistoryError && (
              <p role="status" className="mt-4 rounded-xl bg-ivory p-3 text-sm text-navy-muted">
                {amazonHistoryError}
              </p>
            )}

            {amazonRecentlyViewed.length > 0 ? (
              <ol className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {amazonRecentlyViewed.map((item) => (
                  <li
                    key={item.asin}
                    className="flex min-w-0 gap-3 rounded-2xl border border-border bg-white p-3"
                  >
                    <AmazonCatalogueImage
                      src={item.image_url || null}
                      alt={item.title}
                      wrapperClassName="h-24 w-24 shrink-0 bg-ivory-deep"
                      imageClassName="object-contain p-2"
                    />
                    <div className="min-w-0 flex-1">
                      <h4 className="line-clamp-2 font-semibold leading-5 text-navy">
                        {item.title || 'Product no longer available'}
                      </h4>
                      <p className="mt-1 truncate text-xs text-navy-muted">
                        {item.store || 'Brand not listed'} · {item.category}
                      </p>
                      <p className="mt-2 text-sm font-semibold text-navy">
                        {priceFormatter.format(item.price_inr)}
                      </p>
                      <p className="mt-1 text-[11px] leading-4 text-navy-muted">
                        Amazon catalogue · Availability unverified
                      </p>
                      <p className="mt-2 text-xs text-navy-muted">
                        Viewed {formatDateTime(item.viewed_at)}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            ) : !amazonHistoryError ? (
              <p className="mt-5 rounded-2xl bg-ivory px-5 py-7 text-center text-sm text-navy-muted">
                Amazon products you view in Discover will appear here.
              </p>
            ) : null}
          </section>
        )}

      <section className="rounded-3xl border border-border bg-surface p-5 shadow-soft sm:p-7">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sage-soft text-sage-strong">
              <Activity aria-hidden className="h-5 w-5" />
            </span>
            <div>
              <h3 className="font-display text-xl font-semibold text-navy">
                Recent activities
              </h3>
              {!loading && !error && (
                <p className="mt-1 text-xs text-navy-muted">
                  {history.length} {history.length === 1 ? 'activity' : 'activities'}
                </p>
              )}
            </div>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <label
              htmlFor="history-action-filter"
              className="text-xs font-semibold text-navy"
            >
              Filter by activity
              <select
                id="history-action-filter"
                value={actionFilter}
                onChange={(event) => updateFilter(event.target.value)}
                className="mt-1.5 block min-w-48 rounded-xl border border-border bg-white px-3 py-2.5 text-sm font-medium text-navy outline-none transition focus:border-sage focus:ring-2 focus:ring-sage/15"
              >
                <option value="">All activities</option>
                {historyActions.map(({ value, label }) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => updateFilter('')}
              disabled={!actionFilter || loading}
              className="inline-flex items-center justify-center gap-2 rounded-full border border-border px-4 py-2.5 text-sm font-semibold text-navy-muted transition hover:border-border-strong hover:bg-ivory disabled:cursor-not-allowed disabled:opacity-50"
            >
              Clear filters
            </button>
          </div>
        </div>

        <div className="mt-6 border-t border-border pt-5">
          {loading ? (
            <div
              role="status"
              aria-live="polite"
              className="flex min-h-40 items-center justify-center gap-3 text-sm font-medium text-navy-muted"
            >
              <LoaderCircle
                aria-hidden
                className="h-5 w-5 animate-spin text-sage-strong"
              />
              Loading your shopping history…
            </div>
          ) : error ? (
            <div className="rounded-2xl bg-ivory px-5 py-8 text-center">
              <p role="alert" className="text-sm leading-6 text-danger">
                {error}
              </p>
              <button
                type="button"
                onClick={retry}
                className="mt-4 inline-flex items-center gap-2 rounded-full bg-sage-strong px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-sage focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
              >
                <RefreshCw aria-hidden className="h-4 w-4" />
                Try again
              </button>
            </div>
          ) : history.length === 0 ? (
            <div className="rounded-2xl bg-ivory px-5 py-10 text-center">
              <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-surface text-sage-strong shadow-soft">
                <CalendarClock aria-hidden className="h-6 w-6" />
              </span>
              <h4 className="mt-4 font-display text-xl font-semibold text-navy">
                {filteredLabel
                  ? `No ${filteredLabel} activities yet`
                  : 'Your history is ready when you are'}
              </h4>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-navy-muted">
                {filteredLabel
                  ? 'Try another activity filter or clear filters to see your full history.'
                  : 'Products and activities you explore will appear here.'}
              </p>
              {actionFilter && (
                <button
                  type="button"
                  onClick={() => updateFilter('')}
                  className="mt-4 rounded-full border border-sage/50 px-4 py-2 text-sm font-semibold text-sage-strong transition hover:bg-sage-soft/50"
                >
                  Clear filters
                </button>
              )}
            </div>
          ) : (
            <ol className="divide-y divide-border" aria-label="Shopping activities">
              {history.map((event) => {
                const ActionIcon = getActionIcon(event.action)
                return (
                  <li
                    key={event.id}
                    className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-sage-soft text-sage-strong">
                        <ActionIcon aria-hidden className="h-4 w-4" />
                      </span>
                      <div className="min-w-0">
                        <h4 className="truncate font-semibold text-navy">
                          {event.product_name}
                        </h4>
                        <p className="mt-1 text-xs text-navy-muted">
                          SKU{' '}
                          <span className="font-medium text-navy-muted">
                            {event.product_id}
                          </span>
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pl-12 sm:shrink-0 sm:pl-0">
                      <span className="inline-flex items-center rounded-full bg-ivory px-3 py-1.5 text-xs font-semibold text-navy">
                        {actionLabels[event.action]}
                      </span>
                      <time
                        dateTime={event.created_at}
                        className="text-xs text-navy-muted"
                      >
                        {formatDateTime(event.created_at)}
                      </time>
                    </div>
                  </li>
                )
              })}
            </ol>
          )}
        </div>
      </section>
    </section>
  )
}

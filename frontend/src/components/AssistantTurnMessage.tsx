import {
  AlertCircle,
  ChevronDown,
  LoaderCircle,
  RotateCcw,
  ShoppingBag,
} from 'lucide-react'
import { MAX_ASSISTANT_RECOMMENDATION_LIMIT } from '../config'
import type { ConversationTurn } from '../hooks/useAssistantChat'
import type {
  AgentActivityEvent,
  AssistantRecommendation,
} from '../types/assistant'
import type { AmazonCatalogueProduct } from '../types/amazonCatalogue'
import type { Product } from '../types/product'
import { getDisplayedActivityCount } from '../utils/agentActivity'
import { StatusPill } from './StatusPill'
import { RecommendationCard } from './RecommendationCard'

type AssistantTurnMessageProps = {
  turn: ConversationTurn
  busy: boolean
  isLoadingMore: boolean
  canRequestMore: boolean
  selectedProductId: string | null
  productDetails: Record<string, Product | AmazonCatalogueProduct>
  loadingProductId: string | null
  errorProductId: string | null
  historyErrorProductId: string | null
  onShowMore: (turnId: string) => void
  onRetry: (turnId: string) => void
  onToggleProductDetails: (product: AssistantRecommendation) => void
}

export function AssistantTurnMessage({
  turn,
  busy,
  isLoadingMore,
  canRequestMore,
  selectedProductId,
  productDetails,
  loadingProductId,
  errorProductId,
  historyErrorProductId,
  onShowMore,
  onRetry,
  onToggleProductDetails,
}: AssistantTurnMessageProps) {
  if (!turn.response) {
    if (turn.error) {
      return (
        <div className="flex items-start gap-3" role="alert">
          <AssistantAvatar />
          <div className="max-w-xl rounded-2xl rounded-tl-md border border-danger/20 bg-surface px-5 py-4 shadow-soft">
            <div className="flex items-start gap-2 text-sm leading-6 text-navy">
              <AlertCircle
                aria-hidden
                className="mt-0.5 h-4 w-4 shrink-0 text-danger"
              />
              <p>{turn.error}</p>
            </div>
            <button
              type="button"
              onClick={() => onRetry(turn.id)}
              className="mt-3 inline-flex items-center gap-2 rounded-full border border-border px-3 py-1.5 text-xs font-semibold text-sage-strong transition hover:bg-sage-soft/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
            >
              <RotateCcw aria-hidden className="h-3.5 w-3.5" />
              Retry
            </button>
          </div>
        </div>
      )
    }

    return (
      <div
        className="flex items-start gap-3"
        role="status"
        aria-live="polite"
      >
        <AssistantAvatar />
        <div className="inline-flex items-center gap-2 rounded-2xl rounded-tl-md border border-border bg-surface px-5 py-4 text-sm text-navy-muted shadow-soft">
          <LoaderCircle
            aria-hidden
            className="h-4 w-4 animate-spin text-sage-strong"
          />
          Planning and checking your request…
        </div>
      </div>
    )
  }

  const { response } = turn
  const visibleNotes = [
    ...new Set(
      response.notes
        .map(toUserFacingNote)
        .filter((note): note is string => note !== null),
    ),
  ]
  const hasUnappliedConstraint = response.notes.some(isUnappliedConstraintNote)
  const canShowMore =
    response.has_more &&
    canRequestMore &&
    response.recommendations.length < MAX_ASSISTANT_RECOMMENDATION_LIMIT

  return (
    <div className="flex items-start gap-3">
      <AssistantAvatar />
      <div className="min-w-0 flex-1 space-y-4">
        <div className="max-w-2xl rounded-2xl rounded-tl-md border border-border bg-surface px-5 py-4 text-sm leading-6 text-navy shadow-soft sm:text-base">
          <p className="whitespace-pre-line">{response.answer}</p>
          {hasUnappliedConstraint && (
            <div className="mt-3">
              <StatusPill
                tone="warning"
                label="Some details used a careful fallback"
              />
            </div>
          )}
          {visibleNotes.length > 0 && (
            <ul className="mt-3 space-y-1.5 border-t border-border pt-3 text-xs leading-5 text-navy-muted">
              {visibleNotes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          )}
          {response.agent_metadata &&
          ((response.agent_metadata.events?.length ?? 0) > 0 ||
            response.agent_metadata.activity.length > 0) ? (
            <AgentActivityPanel
              events={response.agent_metadata.events ?? []}
              legacyActivity={response.agent_metadata.activity}
            />
          ) : null}
        </div>

        {response.kind === 'shopping' && response.recommendations.length > 0 ? (
          <div className="space-y-4">
            {response.recommendations.map((product) => (
              <RecommendationCard
                key={`${turn.id}-${product.product_id}`}
                product={product}
                details={productDetails[product.product_id]}
                detailsLoading={loadingProductId === product.product_id}
                detailsError={errorProductId === product.product_id}
                historyError={historyErrorProductId === product.product_id}
                detailsExpanded={selectedProductId === product.product_id}
                onToggleDetails={onToggleProductDetails}
              />
            ))}

            {turn.moreOptionsError && (
              <p role="status" className="text-sm text-danger">
                {turn.moreOptionsError}
              </p>
            )}

            {canShowMore && (
              <button
                type="button"
                disabled={busy}
                onClick={() => onShowMore(turn.id)}
                className="inline-flex items-center gap-2 rounded-full bg-sage px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-sage-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage disabled:cursor-wait disabled:opacity-60"
              >
                {isLoadingMore && (
                  <LoaderCircle
                    aria-hidden
                    className="h-4 w-4 animate-spin"
                  />
                )}
                {isLoadingMore ? 'Finding more options…' : 'Show more options'}
              </button>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function AgentActivityPanel({
  events,
  legacyActivity,
}: {
  events: AgentActivityEvent[]
  legacyActivity: string[]
}) {
  const activityCount = getDisplayedActivityCount(events, legacyActivity)
  const activityLabel =
    events.length > 0
      ? `${events.length} events`
      : `${legacyActivity.length} activity steps`

  return (
    <details className="group mt-4 border-t border-border pt-3">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg text-left text-xs font-semibold text-sage-strong outline-none focus-visible:ring-2 focus-visible:ring-sage">
        <span>
          SmartShopper Agent
          {activityCount > 0 ? ` · ${activityLabel}` : ''}
        </span>
        <ChevronDown
          aria-hidden
          className="h-4 w-4 shrink-0 transition-transform group-open:rotate-180"
        />
      </summary>
      {events.length > 0 ? (
        <ol
          aria-label="Agent execution timeline"
          className="mt-3 space-y-3"
        >
          {events.map((event) => (
            <AgentActivityRow key={event.sequence} event={event} />
          ))}
        </ol>
      ) : (
        <ul className="mt-3 space-y-2 text-xs leading-5 text-navy-muted">
          {legacyActivity.map((activity) => (
            <li key={activity} className="flex gap-2">
              <span
                aria-hidden
                className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sage"
              />
              <span>{activity}</span>
            </li>
          ))}
        </ul>
      )}
    </details>
  )
}

function AgentActivityRow({ event }: { event: AgentActivityEvent }) {
  const statusLabel =
    event.status === 'completed'
      ? 'Completed'
      : event.status === 'failed'
        ? 'Failed'
        : 'Incomplete'
  const statusStyle =
    event.status === 'completed'
      ? 'bg-sage-soft text-sage-strong'
      : event.status === 'failed'
        ? 'bg-danger/10 text-danger'
        : 'bg-ivory-deep text-navy-muted'

  return (
    <li className="flex min-w-0 items-start gap-3">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ivory text-[10px] font-semibold text-navy-muted">
        {event.sequence}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-navy">{event.title}</span>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${statusStyle}`}
          >
            {statusLabel}
          </span>
        </div>
        <p className="mt-1 break-words text-xs leading-5 text-navy-muted">
          {event.summary}
        </p>
      </div>
    </li>
  )
}

function AssistantAvatar() {
  return (
    <span className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sage text-white">
      <ShoppingBag aria-hidden className="h-4 w-4" />
    </span>
  )
}

function isUnappliedConstraintNote(note: string): boolean {
  const normalized = note.toLowerCase()
  return (
    normalized.startsWith('unverified request details were not applied:') ||
    normalized.startsWith('unverified request details:') ||
    normalized.includes('invalid numeric value was not applied') ||
    normalized.includes('no supported details could be safely extracted') ||
    normalized.includes('clarify which supported product category')
  )
}

function toUserFacingNote(note: string): string | null {
  const normalized = note.toLowerCase()

  if (
    normalized.startsWith('unverified request details were not applied:') ||
    normalized.startsWith('unverified request details:')
  ) {
    return 'Some details in your request could not be verified and may not have been applied.'
  }
  if (normalized.startsWith('no products qualified.')) {
    return 'No catalogue products met all of your request and profile filters.'
  }
  if (normalized.includes('grounding validation')) {
    return 'We kept the explanation grounded in the catalogue and recommendation reasons.'
  }
  if (normalized.includes('response schema validation')) {
    return 'We used a catalogue-grounded explanation instead.'
  }
  if (normalized.includes('invalid numeric value')) {
    return 'A budget or priority value could not be applied. Try a clear amount or preference.'
  }
  if (normalized.includes('no supported details could be safely extracted')) {
    return 'No shopping preferences could be interpreted. Please clarify your request.'
  }
  if (normalized.includes('clarify which supported product category')) {
    return 'Please specify whether you are shopping for headphones, laptops, smartwatches, or home appliances.'
  }
  if (
    normalized.includes('deterministic intent parsing') ||
    normalized.includes('safely recognized fields') ||
    normalized.includes('deterministic explanation') ||
    normalized.includes('groq') ||
    normalized.includes('ai explanation')
  ) {
    return normalized.includes('deterministic intent parsing') ||
      normalized.includes('safely recognized fields')
      ? null
      : 'We used a catalogue-grounded explanation instead.'
  }

  return null
}

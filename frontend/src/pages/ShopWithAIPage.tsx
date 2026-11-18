import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, Plus, ShoppingBag, UserRound } from 'lucide-react'
import { AssistantTurnMessage } from '../components/AssistantTurnMessage'
import { ChatComposer } from '../components/ChatComposer'
import { useAssistantChat } from '../hooks/useAssistantChat'
import { useProductDetails } from '../hooks/useProductDetails'
import { useWishlist } from '../services/wishlist'
import { FoundationPage } from './FoundationPage'

export function ShopWithAIPage() {
  const [draft, setDraft] = useState('')
  const conversationEndRef = useRef<HTMLDivElement>(null)
  const {
    turns,
    busyAction,
    busyTurnId,
    persistenceNotice,
    sendMessage,
    retryMessage,
    showMoreOptions,
    startNewChat,
  } = useAssistantChat()
  const productDetails = useProductDetails()
  const wishlist = useWishlist()
  const busy = busyAction !== null
  const latestShoppingTurn = [...turns]
    .reverse()
    .find((turn) => turn.response?.kind === 'shopping')
  const latestShoppingTurnId = latestShoppingTurn?.id ?? null

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    })
  }, [turns, busyAction])

  function handleSend() {
    const message = draft.trim()
    if (!message || busy) return
    setDraft('')
    void sendMessage(message)
  }

  return (
    <div className="flex h-[calc(100dvh-14rem)] min-h-[28rem] flex-col">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-2xl text-sm leading-6 text-navy-muted sm:text-base">
          Tell us what you need, your budget and preferences. Get personalised,
          grounded recommendations.
        </p>
        <button
          type="button"
          onClick={() => {
            startNewChat()
            productDetails.reset()
            setDraft('')
          }}
          disabled={busy}
          className="inline-flex shrink-0 items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-semibold text-navy-muted transition hover:border-border-strong hover:bg-ivory focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus aria-hidden className="h-4 w-4" />
          New chat
        </button>
      </div>

      {persistenceNotice && (
        <p role="status" className="mb-4 text-xs leading-5 text-navy-muted">
          {persistenceNotice}
        </p>
      )}
      {wishlist.error && (
        <p role="status" className="mb-4 text-xs leading-5 text-navy-muted">
          {wishlist.error}
        </p>
      )}

      <section
        aria-label="Shopping conversation"
        className="min-h-0 flex-1 space-y-6 overflow-y-auto overscroll-contain pb-10 pr-1"
      >
        {turns.length === 0 && <WelcomeMessage />}
        {turns.map((turn) => (
          <div key={turn.id} className="space-y-5">
            <div className="flex items-start justify-end gap-3">
              <p className="max-w-xl whitespace-pre-wrap rounded-2xl rounded-tr-md border border-sage-soft bg-sage-soft/70 px-5 py-3.5 text-sm leading-6 text-navy sm:text-base">
                {turn.message}
              </p>
              <span className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sage-soft text-sage-strong">
                <UserRound aria-hidden className="h-4 w-4" />
              </span>
            </div>
            <AssistantTurnMessage
              turn={turn}
              busy={busy}
              isLoadingMore={busyAction === 'more' && busyTurnId === turn.id}
              canRequestMore={turn.id === latestShoppingTurnId}
              selectedProductId={productDetails.selectedProductId}
              productDetails={productDetails.products}
              loadingProductId={productDetails.loadingProductId}
              errorProductId={productDetails.errorProductId}
              historyErrorProductId={productDetails.historyErrorProductId}
              onShowMore={(turnId) => void showMoreOptions(turnId)}
              onRetry={(turnId) => void retryMessage(turnId)}
              onToggleProductDetails={(productId) =>
                void productDetails.toggleDetails(productId)
              }
            />
          </div>
        ))}
        <div ref={conversationEndRef} aria-hidden className="scroll-mb-28" />
      </section>

      <ChatComposer
        value={draft}
        disabled={busy}
        onChange={setDraft}
        onSend={handleSend}
      />

      <details className="mt-5 border-t border-border pt-3">
        <summary className="w-fit cursor-pointer text-xs font-medium text-navy-muted hover:text-navy">
          Connection status
        </summary>
        <div className="mt-4">
          <FoundationPage />
        </div>
      </details>
    </div>
  )
}

function WelcomeMessage() {
  return (
    <div className="flex items-start gap-3">
      <span className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sage text-white">
        <ShoppingBag aria-hidden className="h-4 w-4" />
      </span>
      <div className="max-w-2xl rounded-2xl rounded-tl-md border border-border bg-surface px-5 py-4 text-sm leading-6 text-navy shadow-soft sm:text-base">
        <p className="font-medium">Welcome to thoughtful shopping.</p>
        <p className="mt-1 text-navy-muted">
          Tell me what you are looking for, your budget, and the features that
          matter to you.
        </p>
        <p className="mt-3 flex items-center gap-2 text-xs text-sage-strong">
          <CheckCircle2 aria-hidden className="h-4 w-4" />
          Recommendations are grounded in the product catalogue.
        </p>
      </div>
    </div>
  )
}

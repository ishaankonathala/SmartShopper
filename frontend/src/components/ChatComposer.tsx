import { ArrowUp, Plus } from 'lucide-react'
import type { FormEvent, KeyboardEvent } from 'react'

type ChatComposerProps = {
  value: string
  disabled: boolean
  onChange: (value: string) => void
  onSend: () => void
}

export function ChatComposer({
  value,
  disabled,
  onChange,
  onSend,
}: ChatComposerProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSend()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSend()
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-2 flex shrink-0 items-end gap-2 rounded-3xl border border-border bg-surface p-2 shadow-soft"
    >
      <span
        aria-hidden
        className="mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ivory text-navy-muted"
      >
        <Plus className="h-5 w-5" />
      </span>
      <label className="sr-only" htmlFor="shopping-message">
        Your shopping request
      </label>
      <textarea
        id="shopping-message"
        rows={1}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.currentTarget.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about a product, compare options, or refine your needs…"
        className="max-h-32 min-h-11 min-w-0 flex-1 resize-y rounded-xl bg-transparent px-2 py-3 text-sm leading-5 text-navy outline-none placeholder:text-navy-muted/75 focus-visible:ring-2 focus-visible:ring-sage disabled:opacity-60"
      />
      <button
        type="submit"
        aria-label="Send shopping request"
        disabled={disabled || !value.trim()}
        className="mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-sage text-white transition hover:bg-sage-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage disabled:cursor-not-allowed disabled:opacity-45"
      >
        <ArrowUp aria-hidden className="h-5 w-5" />
      </button>
    </form>
  )
}

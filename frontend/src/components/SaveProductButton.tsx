import { Heart } from 'lucide-react'

type SaveProductButtonProps = {
  isSaved: boolean
  onToggle: () => void
  showLabel?: boolean
  className?: string
}

export function SaveProductButton({
  isSaved,
  onToggle,
  showLabel = false,
  className = '',
}: SaveProductButtonProps) {
  return (
    <button
      type="button"
      aria-label={isSaved ? 'Remove from saved products' : 'Save product'}
      aria-pressed={isSaved}
      title={isSaved ? 'Remove from saved products' : 'Save product'}
      onClick={(event) => {
        event.stopPropagation()
        onToggle()
      }}
      className={`inline-flex shrink-0 items-center justify-center gap-2 rounded-full border border-border bg-white text-navy-muted transition hover:border-sage/50 hover:bg-sage-soft/40 hover:text-sage-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage ${
        isSaved ? 'border-sage/50 text-sage-strong' : ''
      } ${className}`}
    >
      <Heart
        aria-hidden
        className={`h-4 w-4 ${isSaved ? 'fill-current text-rose-600' : ''}`}
      />
      {showLabel && (
        <span className="text-sm font-semibold">
          {isSaved ? 'Saved' : 'Save'}
        </span>
      )}
      <span className="sr-only">
        {isSaved ? 'Remove from saved products' : 'Save product'}
      </span>
    </button>
  )
}

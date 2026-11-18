import { ShoppingBag } from 'lucide-react'
import { Link } from 'react-router-dom'

type BrandLockupProps = {
  compact?: boolean
  onNavigate?: () => void
}

export function BrandLockup({
  compact = false,
  onNavigate,
}: BrandLockupProps) {
  return (
    <Link
      to="/"
      aria-label="SmartShopper AI home"
      onClick={onNavigate}
      className="flex w-fit items-center gap-3 rounded-xl focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage"
    >
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sage-soft text-sage-strong">
        <ShoppingBag aria-hidden className="h-5 w-5" />
      </span>
      {!compact && (
        <span>
          <span className="block text-[15px] font-bold tracking-tight text-navy">
            SmartShopper AI
          </span>
        </span>
      )}
    </Link>
  )
}

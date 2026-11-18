import {
  Bookmark,
  Clock3,
  Compass,
  Heart,
  type LucideIcon,
} from 'lucide-react'
import { StatusPill } from '../components/StatusPill'

type PlaceholderPageKey = 'discover' | 'preferences' | 'history' | 'saved'

type PlaceholderContent = {
  icon: LucideIcon
  eyebrow: string
  heading: string
  description: string
}

const placeholderContent: Record<PlaceholderPageKey, PlaceholderContent> = {
  discover: {
    icon: Compass,
    eyebrow: 'Explore with intention',
    heading: 'A better way to discover what’s out there.',
    description:
      'Browse thoughtful product collections and find options that fit the way you shop.',
  },
  preferences: {
    icon: Heart,
    eyebrow: 'Made personal',
    heading: 'Your preferences, at the heart of every choice.',
    description:
      'Set your budget, favorite categories, brands, and shopping priorities in one place.',
  },
  history: {
    icon: Clock3,
    eyebrow: 'Your shopping journey',
    heading: 'Keep your shopping story close.',
    description:
      'Revisit products you explored, saved, or purchased when history is ready.',
  },
  saved: {
    icon: Bookmark,
    eyebrow: 'Worth another look',
    heading: 'A place for the finds you want to remember.',
    description:
      'Save interesting products and compare them when you are ready to decide.',
  },
}

type RoutePlaceholderPageProps = {
  page: PlaceholderPageKey
}

export function RoutePlaceholderPage({ page }: RoutePlaceholderPageProps) {
  const content = placeholderContent[page]
  const Icon = content.icon

  return (
    <section className="rounded-3xl border border-border bg-surface p-7 shadow-soft sm:p-10">
      <StatusPill tone="neutral" label="Coming in a future phase" />
      <div className="mt-7 flex h-12 w-12 items-center justify-center rounded-2xl bg-sage-soft text-sage-strong">
        <Icon aria-hidden className="h-6 w-6" />
      </div>
      <p className="mt-6 text-xs font-semibold uppercase tracking-[0.16em] text-sage">
        {content.eyebrow}
      </p>
      <h2 className="mt-3 max-w-2xl font-display text-3xl font-semibold leading-tight tracking-tight text-navy sm:text-4xl">
        {content.heading}
      </h2>
      <p className="mt-4 max-w-xl text-sm leading-7 text-navy-muted sm:text-base">
        {content.description}
      </p>
    </section>
  )
}

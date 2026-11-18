import { useEffect, useState } from 'react'
import {
  ArrowUpRight,
  BatteryCharging,
  BriefcaseBusiness,
  CircleUserRound,
  Clock3,
  Headphones,
  type LucideIcon,
  Wallet,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { DEMO_USER_ID } from '../config'
import { getProfile, getShopperDNA } from '../services/api'
import type { Profile } from '../types/profile'
import type { PreferenceDimension, ShopperDNA } from '../types/shopperDna'

const currencyFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
})

export function ShoppingProfilePanel() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [dna, setDna] = useState<ShopperDNA | null>(null)
  const [profileLoaded, setProfileLoaded] = useState(false)
  const [dnaLoaded, setDnaLoaded] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let active = true

    Promise.allSettled([
      getProfile(DEMO_USER_ID),
      getShopperDNA(DEMO_USER_ID),
    ]).then(([profileResult, dnaResult]) => {
      if (!active) return

      setProfile(
        profileResult.status === 'fulfilled' ? profileResult.value : null,
      )
      setDna(dnaResult.status === 'fulfilled' ? dnaResult.value : null)
      setProfileLoaded(profileResult.status === 'fulfilled')
      setDnaLoaded(dnaResult.status === 'fulfilled')
      setLoadError(
        profileResult.status === 'rejected' || dnaResult.status === 'rejected',
      )
      setLoading(false)
    })

    return () => {
      active = false
    }
  }, [retryCount])

  const unavailableValue = loading ? 'Loading…' : 'Unavailable'
  const profileValue = profileLoaded ? null : unavailableValue
  const dnaValue = dnaLoaded ? null : unavailableValue

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-border bg-surface p-5 shadow-soft">
        <div className="flex items-center gap-3">
          <CircleUserRound aria-hidden className="h-5 w-5 text-sage-strong" />
          <h2 className="whitespace-nowrap font-display text-base font-semibold text-navy">
            Your shopping profile
          </h2>
        </div>

        <p className="mt-3 text-xs leading-5 text-navy-muted">
          Personalised recommendations based on your preferences.
        </p>

        <dl className="mt-4 divide-y divide-border border-y border-border">
          <ProfileRow
            icon={Headphones}
            label="Preferred categories"
            value={
              profileValue ??
              (profile?.preferred_categories.length
                ? profile.preferred_categories.join(', ')
                : 'Not set')
            }
          />
          <ProfileRow
            icon={Wallet}
            label="Budget range"
            value={
              profileValue ??
              (profile ? formatBudgetRange(profile) : 'Not set')
            }
          />
          <ProfileRow
            icon={BatteryCharging}
            label="Battery-life priority"
            value={
              dnaValue ??
              (dna
                ? formatPriority(dna, 'battery_life_priority')
                : 'Not set')
            }
          />
          <ProfileRow
            icon={BriefcaseBusiness}
            label="Portability priority"
            value={
              dnaValue ??
              (dna
                ? formatPriority(dna, 'portability_preference')
                : 'Not set')
            }
          />
        </dl>

        {loadError && (
          <div className="mt-3 flex items-center justify-between gap-3 text-xs text-navy-muted">
            <p role="status">Some saved preferences could not be loaded.</p>
            <button
              type="button"
              onClick={() => {
                setLoading(true)
                setLoadError(false)
                setRetryCount((count) => count + 1)
              }}
              className="shrink-0 font-semibold text-sage-strong underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
            >
              Retry
            </button>
          </div>
        )}

        <Link
          to="/preferences"
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-full border border-sage/50 px-4 py-2.5 text-sm font-semibold text-sage-strong transition hover:bg-sage-soft/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
        >
          <ArrowUpRight aria-hidden className="h-4 w-4" />
          Edit preferences
        </Link>
      </section>

      <section className="rounded-2xl border border-border bg-surface p-5 shadow-soft">
        <div className="flex items-center gap-3">
          <Clock3 aria-hidden className="h-5 w-5 text-sage-strong" />
          <h2 className="font-display text-lg font-semibold text-navy">
            Recently viewed
          </h2>
        </div>
        <p className="mt-4 rounded-xl bg-ivory px-4 py-3 text-sm leading-6 text-navy-muted">
          Products you explore will appear here.
        </p>
      </section>
    </div>
  )
}

function formatBudgetRange(profile: Profile): string {
  const maximum = currencyFormatter.format(profile.max_budget)
  return profile.min_budget === null
    ? `Up to ${maximum}`
    : `${currencyFormatter.format(profile.min_budget)} – ${maximum}`
}

function formatPriority(
  dna: ShopperDNA,
  dimension: Extract<
    PreferenceDimension,
    'battery_life_priority' | 'portability_preference'
  >,
): string {
  const value = dna.inferred_preferences[dimension]
  const source = dna.preference_sources[dimension]
  return source && source !== 'default' && Number.isFinite(value)
    ? `${value} / 100`
    : 'Not set'
}

type ProfileRowProps = {
  icon: LucideIcon
  label: string
  value: string
}

function ProfileRow({ icon: Icon, label, value }: ProfileRowProps) {
  return (
    <div className="flex items-center gap-3 py-3">
      <Icon aria-hidden className="h-4 w-4 shrink-0 text-sage-strong" />
      <div className="min-w-0">
        <dt className="text-xs font-semibold text-navy">{label}</dt>
        <dd className="mt-0.5 text-xs text-navy-muted">{value}</dd>
      </div>
    </div>
  )
}

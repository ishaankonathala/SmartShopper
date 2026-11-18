import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  CheckCircle2,
  Heart,
  LoaderCircle,
  RefreshCw,
  Save,
  SlidersHorizontal,
  UserRound,
} from 'lucide-react'
import { ApiRequestError, getProfile, getShopperDNA, updateProfile, updateShopperDNA } from '../services/api'
import type { Profile, ProfileUpdate } from '../types/profile'
import type { PreferenceDimension, ShopperDNA } from '../types/shopperDna'
import { DEMO_USER_ID } from '../config'

type ProfileForm = {
  name: string
  email: string
  minBudget: string
  maxBudget: string
  preferredCategories: string
  preferredBrands: string
  dislikedAttributes: string
}

type SaveState = 'idle' | 'saving' | 'success' | 'error'

const preferenceDimensions: {
  key: PreferenceDimension
  label: string
  description: string
}[] = [
  {
    key: 'comfort_priority',
    label: 'Comfort',
    description: 'How much comfort should influence your matches?',
  },
  {
    key: 'brand_loyalty',
    label: 'Brand loyalty',
    description: 'How strongly should preferred brands be considered?',
  },
  {
    key: 'price_sensitivity',
    label: 'Price sensitivity',
    description: 'How important is getting more value for your budget?',
  },
  {
    key: 'quality_preference',
    label: 'Quality',
    description: 'How much should product quality influence your matches?',
  },
  {
    key: 'portability_preference',
    label: 'Portability',
    description: 'How important are lightweight, easy-to-carry products?',
  },
  {
    key: 'battery_life_priority',
    label: 'Battery life',
    description: 'How important is longer battery life?',
  },
]

const inputClassName =
  'mt-2 w-full rounded-xl border border-border bg-white px-4 py-3 text-sm text-navy outline-none transition placeholder:text-navy-muted/60 focus:border-sage focus:ring-2 focus:ring-sage/15'

function profileToForm(profile: Profile): ProfileForm {
  return {
    name: profile.name,
    email: profile.email ?? '',
    minBudget: profile.min_budget === null ? '' : String(profile.min_budget),
    maxBudget: String(profile.max_budget),
    preferredCategories: profile.preferred_categories.join(', '),
    preferredBrands: profile.preferred_brands.join(', '),
    dislikedAttributes: profile.disliked_attributes.join(', '),
  }
}

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function listsEqual(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((item, index) => item === right[index])
}

function getApiErrorMessage(error: unknown, resource: string): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 404) {
      return resource === 'profile'
        ? 'No profile exists for this demo account. Your data has not been changed.'
        : 'Shopper preference data could not be found for this account.'
    }
    if (error.status === 409) {
      return 'That email address is already associated with another profile.'
    }
    if (error.status === 422) {
      return 'Some values were not accepted. Review the fields and try again.'
    }
    if (error.status >= 500) {
      return 'The preferences service is temporarily unavailable. Please try again.'
    }
    return 'We could not complete that request. Please try again.'
  }

  if (error instanceof TypeError) {
    return 'We could not connect to the preferences service. Check your connection and try again.'
  }

  return 'Something went wrong while loading or saving your preferences. Please try again.'
}

function getLoadError(
  profileResult: PromiseSettledResult<Profile>,
  dnaResult: PromiseSettledResult<ShopperDNA>,
): string {
  if (profileResult.status === 'rejected') {
    return getApiErrorMessage(profileResult.reason, 'profile')
  }
  if (dnaResult.status === 'rejected') {
    return getApiErrorMessage(dnaResult.reason, 'Shopper DNA')
  }
  return 'We could not load your preferences. Please try again.'
}

export function PreferencesPage() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [dna, setDna] = useState<ShopperDNA | null>(null)
  const [profileForm, setProfileForm] = useState<ProfileForm | null>(null)
  const [dnaValues, setDnaValues] = useState<ShopperDNA['inferred_preferences'] | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)
  const [budgetError, setBudgetError] = useState<string | null>(null)
  const [profileSaveState, setProfileSaveState] = useState<SaveState>('idle')
  const [profileSaveMessage, setProfileSaveMessage] = useState('')
  const [dnaSaveState, setDnaSaveState] = useState<SaveState>('idle')
  const [dnaSaveMessage, setDnaSaveMessage] = useState('')
  const saveInProgress = useRef(false)

  useEffect(() => {
    let active = true

    Promise.allSettled([getProfile(DEMO_USER_ID), getShopperDNA(DEMO_USER_ID)]).then(
      ([profileResult, dnaResult]) => {
        if (!active) return

        if (profileResult.status === 'fulfilled' && dnaResult.status === 'fulfilled') {
          setProfile(profileResult.value)
          setProfileForm(profileToForm(profileResult.value))
          setDna(dnaResult.value)
          setDnaValues(dnaResult.value.inferred_preferences)
        } else {
          setProfile(null)
          setProfileForm(null)
          setDna(null)
          setDnaValues(null)
          setLoadError(getLoadError(profileResult, dnaResult))
        }
        setLoading(false)
      },
    )

    return () => {
      active = false
    }
  }, [retryCount])

  function getProfileChanges(): ProfileUpdate {
    if (!profile || !profileForm) return {}
    const changes: ProfileUpdate = {}
    const minBudget = profileForm.minBudget.trim()
      ? Number(profileForm.minBudget)
      : null
    const maxBudget = Number(profileForm.maxBudget)
    const email = profileForm.email.trim() || null
    const preferredCategories = splitList(profileForm.preferredCategories)
    const preferredBrands = splitList(profileForm.preferredBrands)
    const dislikedAttributes = splitList(profileForm.dislikedAttributes)

    if (profileForm.name.trim() !== profile.name) changes.name = profileForm.name.trim()
    if (email !== profile.email) changes.email = email
    if (minBudget !== profile.min_budget) changes.min_budget = minBudget
    if (maxBudget !== profile.max_budget) changes.max_budget = maxBudget
    if (!listsEqual(preferredCategories, profile.preferred_categories)) {
      changes.preferred_categories = preferredCategories
    }
    if (!listsEqual(preferredBrands, profile.preferred_brands)) {
      changes.preferred_brands = preferredBrands
    }
    if (!listsEqual(dislikedAttributes, profile.disliked_attributes)) {
      changes.disliked_attributes = dislikedAttributes
    }
    return changes
  }

  function getChangedDnaValues(): Partial<
    Record<PreferenceDimension, number>
  > {
    if (!dna || !dnaValues) return {}
    const changes: Partial<Record<PreferenceDimension, number>> = {}
    for (const { key } of preferenceDimensions) {
      if (dnaValues[key] !== dna.inferred_preferences[key]) {
        changes[key] = dnaValues[key]
      }
    }
    return changes
  }

  const profileChanges = getProfileChanges()
  const hasProfileChanges = Object.keys(profileChanges).length > 0
  const changedDnaValues = getChangedDnaValues()
  const hasDnaChanges = Object.keys(changedDnaValues).length > 0
  const saving = profileSaveState === 'saving' || dnaSaveState === 'saving'

  async function handleProfileSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!profile || !profileForm || saveInProgress.current) return
    setBudgetError(null)
    setProfileSaveState('idle')
    setProfileSaveMessage('')

    const name = profileForm.name.trim()
    if (!name) {
      setProfileSaveState('error')
      setProfileSaveMessage('Enter your name before saving.')
      return
    }
    const email = profileForm.email.trim()
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setProfileSaveState('error')
      setProfileSaveMessage('Enter a valid email address or leave it blank.')
      return
    }
    if (!profileForm.maxBudget.trim() || !Number.isFinite(Number(profileForm.maxBudget))) {
      setBudgetError('Enter a valid maximum budget.')
      return
    }
    const maxBudget = Number(profileForm.maxBudget)
    if (maxBudget < 0) {
      setBudgetError('Maximum budget cannot be negative.')
      return
    }
    const minBudget = profileForm.minBudget.trim()
      ? Number(profileForm.minBudget)
      : null
    if (minBudget !== null && (!Number.isFinite(minBudget) || minBudget < 0)) {
      setBudgetError('Minimum budget must be a non-negative number.')
      return
    }
    if (minBudget !== null && minBudget > maxBudget) {
      setBudgetError('Minimum budget cannot exceed maximum budget.')
      return
    }

    const changes = getProfileChanges()
    if (Object.keys(changes).length === 0) {
      setProfileSaveMessage('There are no profile changes to save.')
      return
    }

    saveInProgress.current = true
    setProfileSaveState('saving')
    try {
      const updatedProfile = await updateProfile(DEMO_USER_ID, changes)
      setProfile(updatedProfile)
      setProfileForm(profileToForm(updatedProfile))
      setProfileSaveState('success')
      setProfileSaveMessage('Your profile preferences have been saved.')
    } catch (error) {
      setProfileSaveState('error')
      setProfileSaveMessage(getApiErrorMessage(error, 'profile'))
    } finally {
      saveInProgress.current = false
    }
  }

  async function handleDnaSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!dna || saveInProgress.current) return
    setDnaSaveState('idle')
    setDnaSaveMessage('')
    const changes = getChangedDnaValues()
    if (Object.keys(changes).length === 0) {
      setDnaSaveMessage('There are no preference-priority changes to save.')
      return
    }

    saveInProgress.current = true
    setDnaSaveState('saving')
    try {
      const updatedDna = await updateShopperDNA(DEMO_USER_ID, {
        inferred_preferences: changes,
        preference_sources: Object.fromEntries(
          preferenceDimensions
            .filter(({ key }) => changes[key] !== undefined)
            .map(({ key }) => [key, 'manual']),
        ),
      })
      setDna(updatedDna)
      setDnaValues(updatedDna.inferred_preferences)
      setDnaSaveState('success')
      setDnaSaveMessage('Your preference priorities have been saved.')
    } catch (error) {
      setDnaSaveState('error')
      setDnaSaveMessage(getApiErrorMessage(error, 'Shopper DNA'))
    } finally {
      saveInProgress.current = false
    }
  }

  if (loading) {
    return (
      <section
        aria-busy="true"
        aria-live="polite"
        className="rounded-3xl border border-border bg-surface p-8 shadow-soft sm:p-10"
      >
        <div className="flex items-center gap-3 text-sm font-medium text-navy-muted">
          <LoaderCircle aria-hidden className="h-5 w-5 animate-spin text-sage-strong" />
          Loading your preferences…
        </div>
        <div className="mt-7 space-y-3">
          <div className="h-5 w-1/3 animate-pulse rounded bg-ivory-deep" />
          <div className="h-20 animate-pulse rounded-xl bg-ivory" />
          <div className="h-20 animate-pulse rounded-xl bg-ivory" />
        </div>
      </section>
    )
  }

  if (loadError || !profileForm || !dnaValues) {
    return (
      <section className="rounded-3xl border border-border bg-surface p-7 shadow-soft sm:p-10">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sage">
          My preferences
        </p>
        <h2 className="mt-3 font-display text-3xl font-semibold text-navy">
          Your profile could not be loaded
        </h2>
        <p role="alert" className="mt-3 max-w-xl text-sm leading-6 text-navy-muted">
          {loadError ?? 'Your profile data is unavailable right now.'}
        </p>
        <button
          type="button"
          onClick={() => {
            setLoading(true)
            setLoadError(null)
            setRetryCount((count) => count + 1)
          }}
          className="mt-6 inline-flex items-center gap-2 rounded-full bg-sage-strong px-5 py-3 text-sm font-semibold text-white transition hover:bg-sage focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
        >
          <RefreshCw aria-hidden className="h-4 w-4" />
          Try again
        </button>
      </section>
    )
  }

  return (
    <section className="space-y-6">
      <header className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sage">
          A more personal way to shop
        </p>
        <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-navy sm:text-4xl">
          My preferences
        </h2>
        <p className="mt-3 text-sm leading-6 text-navy-muted sm:text-base">
          Update the details and priorities used to tailor your shopping experience.
          Your stated preferences and preference-priority signals are saved separately.
        </p>
      </header>

      <form
        onSubmit={handleProfileSave}
        className="rounded-3xl border border-border bg-surface p-5 shadow-soft sm:p-8"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sage-soft text-sage-strong">
              <UserRound aria-hidden className="h-5 w-5" />
            </span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-sage">
                Explicit profile
              </p>
              <h3 className="mt-1 font-display text-2xl font-semibold text-navy">
                Your shopping details
              </h3>
              <p className="mt-1 text-sm text-navy-muted">
                These are preferences you choose to share.
              </p>
            </div>
          </div>
          <SaveButton
            saving={profileSaveState === 'saving'}
            disabled={!hasProfileChanges || saving}
            label="Save profile"
          />
        </div>

        <fieldset
          disabled={saving}
          className="mt-7 grid w-full gap-x-5 gap-y-5 sm:grid-cols-2"
        >
          <legend className="sr-only">Explicit shopping preferences</legend>
          <TextField
            id="profile-name"
            label="Name"
            value={profileForm.name}
            onChange={(value) => {
              setProfileForm({ ...profileForm, name: value })
              setProfileSaveState('idle')
              setProfileSaveMessage('')
            }}
            autoComplete="name"
          />
          <TextField
            id="profile-email"
            label="Email"
            type="email"
            value={profileForm.email}
            onChange={(value) => {
              setProfileForm({ ...profileForm, email: value })
              setProfileSaveState('idle')
              setProfileSaveMessage('')
            }}
            autoComplete="email"
          />
          <TextField
            id="profile-min-budget"
            label="Minimum budget (₹)"
            type="number"
            min="0"
            step="0.01"
            value={profileForm.minBudget}
            onChange={(value) => {
              setProfileForm({ ...profileForm, minBudget: value })
              setBudgetError(null)
              setProfileSaveState('idle')
              setProfileSaveMessage('')
            }}
            hint="Optional"
          />
          <TextField
            id="profile-max-budget"
            label="Maximum budget (₹)"
            type="number"
            min="0"
            step="0.01"
            value={profileForm.maxBudget}
            onChange={(value) => {
              setProfileForm({ ...profileForm, maxBudget: value })
              setBudgetError(null)
              setProfileSaveState('idle')
              setProfileSaveMessage('')
            }}
          />
          <ListField
            id="profile-categories"
            label="Preferred categories"
            value={profileForm.preferredCategories}
            onChange={(value) => {
              setProfileForm({ ...profileForm, preferredCategories: value })
              setProfileSaveState('idle')
              setProfileSaveMessage('')
            }}
            hint="Separate entries with commas."
          />
          <ListField
            id="profile-brands"
            label="Preferred brands"
            value={profileForm.preferredBrands}
            onChange={(value) => {
              setProfileForm({ ...profileForm, preferredBrands: value })
              setProfileSaveState('idle')
              setProfileSaveMessage('')
            }}
            hint="Separate entries with commas."
          />
          <ListField
            id="profile-dislikes"
            label="Disliked attributes"
            value={profileForm.dislikedAttributes}
            onChange={(value) => {
              setProfileForm({ ...profileForm, dislikedAttributes: value })
              setProfileSaveState('idle')
              setProfileSaveMessage('')
            }}
            hint="Separate entries with commas."
            className="sm:col-span-2"
          />
        </fieldset>

        {budgetError && (
          <p role="alert" className="mt-4 text-sm text-danger">
            {budgetError}
          </p>
        )}
        {profileSaveMessage && (
          <Feedback state={profileSaveState} message={profileSaveMessage} />
        )}
      </form>

      <form
        onSubmit={handleDnaSave}
        className="rounded-3xl border border-border bg-surface p-5 shadow-soft sm:p-8"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sage-soft text-sage-strong">
              <SlidersHorizontal aria-hidden className="h-5 w-5" />
            </span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-sage">
                Preference priorities
              </p>
              <h3 className="mt-1 font-display text-2xl font-semibold text-navy">
                What matters most to you?
              </h3>
              <p className="mt-1 text-sm text-navy-muted">
                Adjust each signal from 0 (less important) to 100 (more important).
              </p>
            </div>
          </div>
          <SaveButton
            saving={dnaSaveState === 'saving'}
            disabled={!hasDnaChanges || saving}
            label="Save priorities"
          />
        </div>

        <fieldset disabled={saving} className="mt-7 grid gap-4 md:grid-cols-2">
          <legend className="sr-only">Preference priorities</legend>
          {preferenceDimensions.map(({ key, label, description }) => (
            <label
              key={key}
              htmlFor={`priority-${key}`}
              className="rounded-2xl border border-border bg-ivory/70 p-4 sm:p-5"
            >
              <span className="flex items-center justify-between gap-3">
                <span className="font-semibold text-navy">{label}</span>
                <span className="min-w-12 rounded-full bg-sage-soft px-3 py-1 text-center text-sm font-bold tabular-nums text-sage-strong">
                  {dnaValues[key]}
                </span>
              </span>
              <span className="mt-1 block text-xs leading-5 text-navy-muted">
                {description}
              </span>
              <input
                id={`priority-${key}`}
                type="range"
                min="0"
                max="100"
                step="1"
                value={dnaValues[key]}
                onChange={(event) => {
                  setDnaValues({
                    ...dnaValues,
                    [key]: Number(event.target.value),
                  })
                  setDnaSaveState('idle')
                  setDnaSaveMessage('')
                }}
                className="mt-4 h-2 w-full cursor-pointer accent-sage-strong"
                aria-label={`${label} priority`}
              />
              <span className="mt-1 flex justify-between text-[11px] text-navy-muted">
                <span>Less important</span>
                <span>More important</span>
              </span>
            </label>
          ))}
        </fieldset>

        {dnaSaveMessage && (
          <Feedback state={dnaSaveState} message={dnaSaveMessage} />
        )}
        <p className="mt-5 flex items-start gap-2 text-xs leading-5 text-navy-muted">
          <Heart aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-sage-strong" />
          These priority values are stored separately from your explicit profile details.
        </p>
      </form>
    </section>
  )
}

type TextFieldProps = {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  type?: 'text' | 'email' | 'number'
  min?: string
  step?: string
  hint?: string
  autoComplete?: string
}

function TextField({
  id,
  label,
  value,
  onChange,
  type = 'text',
  min,
  step,
  hint,
  autoComplete,
}: TextFieldProps) {
  return (
    <label htmlFor={id} className="block text-sm font-semibold text-navy">
      {label}
      {hint && <span className="ml-2 text-xs font-normal text-navy-muted">{hint}</span>}
      <input
        id={id}
        type={type}
        min={min}
        step={step}
        value={value}
        autoComplete={autoComplete}
        onChange={(event) => onChange(event.target.value)}
        className={inputClassName}
      />
    </label>
  )
}

type ListFieldProps = {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  hint: string
  className?: string
}

function ListField({
  id,
  label,
  value,
  onChange,
  hint,
  className = '',
}: ListFieldProps) {
  return (
    <label htmlFor={id} className={`block text-sm font-semibold text-navy ${className}`}>
      {label}
      <span className="ml-2 text-xs font-normal text-navy-muted">{hint}</span>
      <input
        id={id}
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={inputClassName}
      />
    </label>
  )
}

function SaveButton({
  saving,
  disabled,
  label,
}: {
  saving: boolean
  disabled: boolean
  label: string
}) {
  return (
    <button
      type="submit"
      disabled={disabled}
      className="inline-flex items-center justify-center gap-2 rounded-full bg-sage-strong px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-sage focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage disabled:cursor-not-allowed disabled:bg-ivory-deep disabled:text-navy-muted"
    >
      {saving ? (
        <LoaderCircle aria-hidden className="h-4 w-4 animate-spin" />
      ) : (
        <Save aria-hidden className="h-4 w-4" />
      )}
      {saving ? 'Saving…' : label}
    </button>
  )
}

function Feedback({ state, message }: { state: SaveState; message: string }) {
  const isError = state === 'error'
  const tone =
    state === 'error'
      ? 'text-danger'
      : state === 'success'
        ? 'text-success'
        : 'text-navy-muted'
  return (
    <p
      role={isError ? 'alert' : 'status'}
      className={`mt-4 flex items-center gap-2 text-sm ${tone}`}
    >
      {state === 'success' && <CheckCircle2 aria-hidden className="h-4 w-4" />}
      {message}
    </p>
  )
}

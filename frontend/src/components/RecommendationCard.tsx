import { useState } from 'react'
import {
  BatteryCharging,
  Cable,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ImageOff,
  LoaderCircle,
  PackageOpen,
  Star,
  type LucideIcon,
  Wifi,
} from 'lucide-react'
import type { AssistantRecommendation } from '../types/assistant'
import type { AmazonCatalogueProduct } from '../types/amazonCatalogue'
import type { Product } from '../types/product'
import { useWishlist } from '../services/wishlist'
import { SaveProductButton } from './SaveProductButton'
import { StatusPill } from './StatusPill'

const priceFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

type RecommendationCardProps = {
  product: AssistantRecommendation
  details?: Product | AmazonCatalogueProduct
  detailsLoading: boolean
  detailsError: boolean
  historyError: boolean
  detailsExpanded: boolean
  onToggleDetails: (product: AssistantRecommendation) => void
}

export function RecommendationCard({
  product,
  details,
  detailsLoading,
  detailsError,
  historyError,
  detailsExpanded,
  onToggleDetails,
}: RecommendationCardProps) {
  const [imageFailed, setImageFailed] = useState(false)
  const wishlist = useWishlist()
  const isSaved = wishlist.isSaved(product)
  const imageUrl = product.image_url
  const amazonDetails = details && 'asin' in details ? details : undefined
  const curatedDetails = details && 'product_id' in details ? details : undefined

  return (
    <article className="rounded-2xl border border-border bg-surface p-3 shadow-soft sm:p-4">
      <div className="flex flex-col gap-4 sm:flex-row">
        <div className="relative flex aspect-[4/3] shrink-0 items-center justify-center overflow-hidden rounded-xl bg-ivory-deep text-sage-strong sm:aspect-square sm:w-40">
          {imageUrl && !imageFailed ? (
            <img
              src={imageUrl}
              alt={product.name}
              loading="lazy"
              onError={() => setImageFailed(true)}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex flex-col items-center gap-2 text-navy-muted/65">
              {imageUrl ? (
                <ImageOff aria-hidden className="h-7 w-7" />
              ) : (
                <PackageOpen aria-hidden className="h-8 w-8" />
              )}
              <span className="text-xs">Image unavailable</span>
            </div>
          )}
        </div>

        <div className="flex min-w-0 flex-1 flex-col justify-center py-1">
          <div className="flex items-start justify-between gap-3">
            <span className="inline-flex items-center gap-1.5 self-start rounded-full bg-sage-soft px-3 py-1 text-xs font-semibold text-sage-strong">
              <CheckCircle2 aria-hidden className="h-3.5 w-3.5" />
              Recommended for you
            </span>
            <SaveProductButton
              isSaved={isSaved}
              onToggle={() => wishlist.toggle(product)}
              className="h-9 w-9"
            />
          </div>
          {product.catalogue_source === 'amazon' && (
            <div className="mt-2 flex flex-wrap gap-2">
              <StatusPill tone="warning" label="Amazon historical catalogue" />
              <StatusPill
                tone="warning"
                label="Availability unverified"
              />
            </div>
          )}

          <h3 className="mt-3 font-display text-xl font-semibold text-navy sm:text-2xl">
            {product.name}
          </h3>
          <p className="mt-1 text-sm text-navy-muted">
            {product.brand} <span aria-hidden>·</span> {product.category}
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="font-display text-2xl font-semibold text-navy">
              {priceFormatter.format(product.price)}
            </span>
            <span className="inline-flex items-center gap-1 text-sm text-navy-muted">
              <Star
                aria-hidden
                className="h-4 w-4 fill-amber-400 text-amber-500"
              />
              {product.rating.toFixed(1)} / 5
              {product.rating_count != null && (
                <span className="text-xs">
                  ({product.rating_count.toLocaleString('en-IN')} reviews)
                </span>
              )}
            </span>
          </div>
          {product.price_is_historical && (
            <p className="mt-2 text-xs leading-5 text-navy-muted">
              Historical USD price converted to INR; not a current Indian retail price.
            </p>
          )}

          <ProductAttributeChips product={curatedDetails} />
        </div>
      </div>

      <section className="mt-4 rounded-xl bg-ivory px-4 py-3.5">
        <h4 className="font-display text-base font-semibold text-navy">
          Why this is a good match
        </h4>
        <ul className="mt-2 space-y-2">
          {product.reasons.map((reason, index) => (
            <li
              key={`${product.product_id}-reason-${index}`}
              className="flex items-start gap-2 text-sm leading-5 text-navy-muted"
            >
              <CheckCircle2
                aria-hidden
                className="mt-0.5 h-4 w-4 shrink-0 text-success"
              />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-3">
        <button
          type="button"
          aria-expanded={detailsExpanded}
          onClick={() => onToggleDetails(product)}
          disabled={detailsLoading}
          className="inline-flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-semibold text-sage-strong transition hover:bg-sage-soft/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage disabled:cursor-wait disabled:opacity-70"
        >
          {detailsLoading ? (
            <>
              <LoaderCircle aria-hidden className="h-4 w-4 animate-spin" />
              Loading product details
            </>
          ) : (
            <>
              {detailsExpanded ? 'Hide product details' : 'Product details'}
              {detailsExpanded ? (
                <ChevronUp aria-hidden className="h-4 w-4" />
              ) : (
                <ChevronDown aria-hidden className="h-4 w-4" />
              )}
            </>
          )}
        </button>
      </div>

      {detailsExpanded && (
        <div className="mt-2 border-t border-border pt-3">
          {historyError && (
            <p role="status" className="mb-2 text-sm text-navy-muted">
              This view could not be added to Shopping History.
            </p>
          )}
          {detailsError ? (
            <p role="status" className="text-sm text-navy-muted">
              Product details are unavailable right now.
            </p>
          ) : amazonDetails ? (
            <div className="space-y-3">
              <StatusPill tone="warning" label="Availability unverified" />
              <p className="text-xs leading-5 text-navy-muted">
                Historical Amazon metadata. Its converted price is illustrative,
                not a current Indian retail price.
              </p>
              {amazonDetails.description.length > 0 && (
                <div>
                  <h4 className="font-semibold text-navy">Description</h4>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6 text-navy-muted">
                    {amazonDetails.description.map((text, index) => (
                      <li key={`${amazonDetails.asin}-description-${index}`}>
                        {text}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {amazonDetails.features.length > 0 && (
                <div>
                  <h4 className="font-semibold text-navy">Listed details</h4>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6 text-navy-muted">
                    {amazonDetails.features.map((feature, index) => (
                      <li key={`${amazonDetails.asin}-feature-${index}`}>
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <p className="border-t border-border pt-2 text-xs text-navy-muted">
                Source ASIN: {amazonDetails.asin} · Amazon Reviews 2023 metadata
              </p>
            </div>
          ) : curatedDetails ? (
            <div>
              <StatusPill
                tone={curatedDetails.is_available ? 'success' : 'warning'}
                label={
                  curatedDetails.is_available
                    ? 'Available'
                    : 'Currently unavailable'
                }
              />
              <p className="text-sm leading-6 text-navy-muted">
                {curatedDetails.description}
              </p>
            </div>
          ) : (
            <p className="text-sm text-navy-muted">
              Loading catalogue details…
            </p>
          )}
        </div>
      )}
    </article>
  )
}

function ProductAttributeChips({ product }: { product?: Product }) {
  if (!product) return null
  const attributes = product.attributes
  const chips: { label: string; icon: LucideIcon }[] = []

  if (attributes.connectivity === 'wireless') {
    chips.push({ label: 'Wireless', icon: Wifi })
  } else if (attributes.connectivity === 'wired') {
    chips.push({ label: 'Wired', icon: Cable })
  }

  const batteryLife = attributes.battery_life_hours
  if (
    typeof batteryLife === 'number' &&
    Number.isFinite(batteryLife) &&
    batteryLife > 0
  ) {
    chips.push({
      label: `${batteryLife} h battery life`,
      icon: BatteryCharging,
    })
  }

  const portability = attributes.portability
  if (typeof portability === 'number' && Number.isFinite(portability)) {
    chips.push({ label: `Portability ${portability}/100`, icon: PackageOpen })
  }

  if (!chips.length) return null

  return (
    <ul className="mt-3 flex flex-wrap gap-2">
      {chips.map(({ icon: Icon, label }) => (
        <li
          key={label}
          className="inline-flex items-center gap-1.5 rounded-full bg-ivory px-3 py-1.5 text-xs font-medium text-navy-muted"
        >
          <Icon aria-hidden className="h-3.5 w-3.5 text-sage-strong" />
          {label}
        </li>
      ))}
    </ul>
  )
}

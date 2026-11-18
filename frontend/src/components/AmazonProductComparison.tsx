import { X } from 'lucide-react'
import { useEffect } from 'react'
import type { AmazonComparisonProduct } from '../services/amazonComparison'
import { AmazonCatalogueImage } from './AmazonCatalogueCard'

const priceFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

const countFormatter = new Intl.NumberFormat('en-IN')

type AmazonProductComparisonProps = {
  products: AmazonComparisonProduct[]
  onRemove: (asin: string) => void
  onClose: () => void
}

export function AmazonProductComparison({
  products,
  onRemove,
  onClose,
}: AmazonProductComparisonProps) {
  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
      <button
        type="button"
        aria-label="Close product comparison"
        onClick={onClose}
        className="absolute inset-0 bg-navy/50"
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="amazon-comparison-title"
        className="relative z-10 max-h-[92dvh] w-full max-w-6xl overflow-y-auto rounded-3xl border border-border bg-surface p-4 shadow-soft sm:p-7"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-sage-strong">
              Discover collection
            </p>
            <h2
              id="amazon-comparison-title"
              className="mt-1 font-display text-2xl font-semibold text-navy sm:text-3xl"
            >
              Compare products
            </h2>
            <p className="mt-2 text-sm text-navy-muted">
              Historical prices are illustrative; availability is unverified.
              Only listed catalogue data is compared.
            </p>
          </div>
          <button
            type="button"
            autoFocus
            aria-label="Return to Discover"
            onClick={onClose}
            className="inline-flex shrink-0 items-center gap-2 rounded-full border border-border px-3 py-2 text-xs font-semibold text-navy-muted hover:bg-ivory focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
          >
            <X aria-hidden className="h-4 w-4" />
            <span className="hidden sm:inline">Back to Discover</span>
          </button>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {products.map((product) => (
            <article
              key={product.asin}
              className="min-w-0 overflow-hidden rounded-2xl border border-border bg-white"
            >
              <AmazonCatalogueImage
                src={product.image_url}
                alt={product.title}
                wrapperClassName="aspect-[4/3] rounded-none bg-ivory-deep"
                imageClassName="object-contain p-4"
              />
              <div className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-display text-lg font-semibold leading-6 text-navy">
                      {product.title}
                    </h3>
                    <p className="mt-1 text-sm text-navy-muted">
                      {product.store || 'Brand not listed'} · {product.category}
                    </p>
                  </div>
                  <button
                    type="button"
                    aria-label={`Remove ${product.title} from comparison`}
                    onClick={() => onRemove(product.asin)}
                    className="shrink-0 rounded-full p-2 text-navy-muted hover:bg-ivory hover:text-navy focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
                  >
                    <X aria-hidden className="h-4 w-4" />
                  </button>
                </div>

                <dl className="mt-4 divide-y divide-border">
                  <ComparisonField label="Price">
                    <span>{priceFormatter.format(product.price_inr)}</span>
                    <span className="mt-0.5 block text-xs text-navy-muted">
                      Illustrative historical conversion
                    </span>
                  </ComparisonField>
                  <ComparisonField label="Rating">
                    {product.rating === null
                      ? 'Not listed'
                      : `${product.rating.toFixed(1)} / 5`}
                  </ComparisonField>
                  <ComparisonField label="Review count">
                    {product.rating_count === null
                      ? 'Not listed'
                      : countFormatter.format(product.rating_count)}
                  </ComparisonField>
                  <ComparisonField label="Category">
                    {product.category || 'Not listed'}
                  </ComparisonField>
                  <ComparisonField label="Store / brand">
                    {product.store || 'Not listed'}
                  </ComparisonField>
                  <ComparisonField label="Features">
                    {product.features.length > 0 ? (
                      <ul className="list-disc space-y-1 pl-5">
                        {product.features.map((feature, index) => (
                          <li key={`${product.asin}-comparison-feature-${index}`}>
                            {feature}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      'Not listed'
                    )}
                  </ComparisonField>
                  <ComparisonField label="Structured specifications">
                    Not provided in this catalogue.
                  </ComparisonField>
                </dl>
                <p className="mt-4 border-t border-border pt-3 text-xs text-navy-muted">
                  ASIN: {product.asin} · Availability unverified
                </p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}

function ComparisonField({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-3 py-3 text-sm first:pt-0 last:pb-0">
      <dt className="font-semibold text-navy-muted">{label}</dt>
      <dd className="min-w-0 break-words leading-5 text-navy">{children}</dd>
    </div>
  )
}

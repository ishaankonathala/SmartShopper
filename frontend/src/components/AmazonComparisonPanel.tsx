import { useState } from 'react'
import { AmazonProductComparison } from './AmazonProductComparison'
import { useAmazonComparison } from '../services/amazonComparison'

export function AmazonComparisonPanel() {
  const comparison = useAmazonComparison()
  const [dialogOpen, setDialogOpen] = useState(false)

  if (comparison.products.length === 0) return null

  function removeProduct(asin: string) {
    comparison.remove(asin)
    if (comparison.products.length <= 2) setDialogOpen(false)
  }

  return (
    <>
      <aside
        aria-label="Products selected for comparison"
        className="fixed inset-x-3 bottom-3 z-40 mx-auto max-w-5xl rounded-2xl border border-border bg-surface p-3 shadow-soft sm:inset-x-6 sm:p-4"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-navy">
              Compare products · {comparison.products.length}/3 selected
            </p>
            <p className="mt-1 text-xs text-navy-muted">
              {comparison.products.length < 2
                ? 'Choose one more product to compare.'
                : 'Prices are illustrative; availability is unverified.'}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {comparison.products.map((product) => (
              <button
                key={product.asin}
                type="button"
                aria-label={`Remove ${product.title} from comparison`}
                onClick={() => removeProduct(product.asin)}
                className="max-w-36 truncate rounded-full border border-border bg-white px-3 py-1.5 text-xs font-medium text-navy-muted hover:bg-ivory"
              >
                {product.title} ×
              </button>
            ))}
            <button
              type="button"
              disabled={comparison.products.length < 2}
              onClick={() => setDialogOpen(true)}
              className="rounded-full bg-sage px-4 py-2 text-sm font-semibold text-white hover:bg-sage-strong disabled:cursor-not-allowed disabled:opacity-45"
            >
              Compare ({comparison.products.length})
            </button>
            <button
              type="button"
              onClick={() => {
                comparison.clear()
                setDialogOpen(false)
              }}
              className="rounded-full px-3 py-2 text-sm font-semibold text-navy-muted hover:bg-ivory"
            >
              Clear
            </button>
          </div>
        </div>
      </aside>

      {dialogOpen && comparison.products.length >= 2 && (
        <AmazonProductComparison
          products={comparison.products}
          onRemove={removeProduct}
          onClose={() => setDialogOpen(false)}
        />
      )}
    </>
  )
}

import { useAmazonComparison } from '../services/amazonComparison'
import type { AmazonComparisonProduct } from '../services/amazonComparison'

export function AmazonComparisonToggleButton({
  product,
}: {
  product: AmazonComparisonProduct
}) {
  const comparison = useAmazonComparison()
  const isSelected = comparison.isSelected(product.asin)
  const isFull = comparison.products.length >= 3

  return (
    <button
      type="button"
      aria-pressed={isSelected}
      disabled={!isSelected && isFull}
      onClick={(event) => {
        event.stopPropagation()
        comparison.toggle(product)
      }}
      className="mt-2 rounded-full border border-border px-4 py-2.5 text-sm font-semibold text-navy-muted transition hover:bg-ivory focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage disabled:cursor-not-allowed disabled:opacity-45"
    >
      {isSelected ? 'Remove from comparison' : 'Add to compare'}
    </button>
  )
}

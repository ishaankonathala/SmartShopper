import { ImageOff, PackageOpen, Star } from 'lucide-react'
import { useState } from 'react'
import { AmazonComparisonToggleButton } from './AmazonComparisonToggleButton'
import { SaveProductButton } from './SaveProductButton'
import { useWishlist } from '../services/wishlist'
import type { AmazonCatalogueProduct } from '../types/amazonCatalogue'

const priceFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

const countFormatter = new Intl.NumberFormat('en-IN')

type AmazonCatalogueCardProps = {
  product: AmazonCatalogueProduct
  onViewDetails: (asin: string) => void
}

export function AmazonCatalogueCard({
  product,
  onViewDetails,
}: AmazonCatalogueCardProps) {
  const wishlist = useWishlist()
  const isSaved = wishlist.isSaved(product)

  return (
    <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-soft">
      <AmazonCatalogueImage
        src={product.image_url}
        alt={product.title}
        wrapperClassName="aspect-[4/3] bg-ivory-deep"
        imageClassName="object-contain p-4"
      />

      <div className="flex flex-1 flex-col p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-sage-strong">
              {product.category}
            </p>
            <h2 className="mt-2 line-clamp-2 min-h-12 font-display text-lg font-semibold leading-6 text-navy">
              {product.title}
            </h2>
            <p className="mt-1 truncate text-sm text-navy-muted">
              {product.store || 'Brand not listed'}
            </p>
          </div>
          <SaveProductButton
            isSaved={isSaved}
            onToggle={() => wishlist.toggle(product)}
            className="h-9 w-9"
          />
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="block font-display text-xl font-semibold text-navy">
              {priceFormatter.format(product.price_inr)}
            </span>
            <span className="text-[11px] text-navy-muted">
              Illustrative historical price
            </span>
          </div>
          <span className="inline-flex items-center gap-1 text-sm text-navy-muted">
            <Star
              aria-hidden
              className="h-4 w-4 fill-amber-400 text-amber-500"
            />
            {product.rating.toFixed(1)}
            <span className="text-xs">
              ({countFormatter.format(product.rating_count)})
            </span>
          </span>
        </div>

        <p className="mt-2 text-xs text-navy-muted">
          Availability not verified
        </p>

        <AmazonComparisonToggleButton product={product} />
        <button
          type="button"
          onClick={() => onViewDetails(product.asin)}
          className="mt-2 rounded-full border border-sage/50 px-4 py-2.5 text-sm font-semibold text-sage-strong transition hover:bg-sage-soft/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
        >
          View product details
        </button>
      </div>
    </article>
  )
}

type AmazonCatalogueImageProps = {
  src: string | null
  alt: string
  wrapperClassName: string
  imageClassName: string
}

export function AmazonCatalogueImage({
  src,
  alt,
  wrapperClassName,
  imageClassName,
}: AmazonCatalogueImageProps) {
  const [imageFailed, setImageFailed] = useState(false)
  const hasImage = Boolean(src?.trim())

  return (
    <div
      className={`flex items-center justify-center overflow-hidden rounded-2xl ${wrapperClassName}`}
    >
      {hasImage && !imageFailed ? (
        <img
          src={src ?? undefined}
          alt={alt}
          loading="lazy"
          onError={() => setImageFailed(true)}
          className={`h-full w-full ${imageClassName}`}
        />
      ) : (
        <div className="flex flex-col items-center gap-2 text-navy-muted/65">
          {hasImage ? (
            <ImageOff aria-hidden className="h-7 w-7" />
          ) : (
            <PackageOpen aria-hidden className="h-7 w-7" />
          )}
          <span className="text-xs">Image unavailable</span>
        </div>
      )}
    </div>
  )
}

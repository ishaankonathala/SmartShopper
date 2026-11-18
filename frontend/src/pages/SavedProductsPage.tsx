import { useState } from 'react'
import { Bookmark, Heart, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { AmazonCatalogueImage } from '../components/AmazonCatalogueCard'
import { AmazonComparisonPanel } from '../components/AmazonComparisonPanel'
import { AmazonComparisonToggleButton } from '../components/AmazonComparisonToggleButton'
import { SaveProductButton } from '../components/SaveProductButton'
import { useAmazonComparison } from '../services/amazonComparison'
import { useWishlist } from '../services/wishlist'
import type { WishlistProduct } from '../services/wishlist'

const priceFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

export function SavedProductsPage() {
  const wishlist = useWishlist()
  const comparison = useAmazonComparison()
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const selectedProduct =
    wishlist.items.find((product) => product.key === selectedKey) ?? null

  return (
    <section
      className={`space-y-6 ${
        wishlist.items.length > 0 || comparison.products.length > 0
          ? 'pb-28'
          : ''
      }`}
    >
      <header className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sage">
          Worth another look
        </p>
        <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-navy sm:text-4xl">
          Saved products
        </h2>
        <p className="mt-3 text-sm leading-6 text-navy-muted sm:text-base">
          Your wishlist is separate from products you have recently viewed.
          Saved product snapshots stay available across visits in this browser.
        </p>
      </header>

      {wishlist.error && (
        <p role="status" className="rounded-2xl bg-surface px-4 py-3 text-sm text-navy-muted">
          {wishlist.error}
        </p>
      )}

      {wishlist.items.length === 0 ? (
        <div className="rounded-3xl border border-border bg-surface px-6 py-12 text-center shadow-soft">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-sage-soft text-sage-strong">
            <Bookmark aria-hidden className="h-6 w-6" />
          </span>
          <h3 className="mt-4 font-display text-xl font-semibold text-navy">
            Your saved products will appear here
          </h3>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-navy-muted">
            Save products from Discover or your AI recommendations to keep a
            personal shortlist.
          </p>
          <Link
            to="/discover"
            className="mt-5 inline-flex items-center gap-2 rounded-full bg-sage px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-sage-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
          >
            <Heart aria-hidden className="h-4 w-4" />
            Browse Discover
          </Link>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-navy-muted">
              {wishlist.items.length}{' '}
              {wishlist.items.length === 1 ? 'saved product' : 'saved products'}
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {wishlist.items.map((product) => (
              <SavedProductCard
                key={product.key}
                product={product}
                onRemove={() => wishlist.remove(product.key)}
                onViewDetails={() => setSelectedKey(product.key)}
              />
            ))}
          </div>
        </>
      )}

      {selectedProduct && (
        <SavedProductDetails
          product={selectedProduct}
          isSaved={wishlist.items.some(
            (product) => product.key === selectedProduct.key,
          )}
          onClose={() => setSelectedKey(null)}
          onRemove={() => wishlist.remove(selectedProduct.key)}
        />
      )}

      <AmazonComparisonPanel />
    </section>
  )
}

function SavedProductCard({
  product,
  onRemove,
  onViewDetails,
}: {
  product: WishlistProduct
  onRemove: () => void
  onViewDetails: () => void
}) {
  const compareProduct =
    product.source === 'amazon' && product.asin
      ? {
          asin: product.asin,
          title: product.name,
          store: product.brand || null,
          category: product.category,
          price_inr: product.price,
          rating: product.rating,
          rating_count: product.rating_count,
          image_url: product.image_url,
          features: product.features,
        }
      : null

  return (
    <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-soft">
      <AmazonCatalogueImage
        src={product.image_url}
        alt={product.name}
        wrapperClassName="aspect-[4/3] bg-ivory-deep"
        imageClassName="object-contain p-4"
      />
      <div className="flex flex-1 flex-col p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-sage-strong">
              {product.source === 'amazon' ? 'Amazon catalogue' : 'Curated catalogue'}
            </p>
            <h3 className="mt-2 line-clamp-2 min-h-12 font-display text-lg font-semibold leading-6 text-navy">
              {product.name}
            </h3>
            <p className="mt-1 truncate text-sm text-navy-muted">
              {product.brand || 'Brand not listed'}
            </p>
          </div>
          <SaveProductButton
            isSaved
            onToggle={onRemove}
            className="h-9 w-9"
          />
        </div>

        <p className="mt-3 text-xs text-navy-muted">{product.category}</p>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <span className="font-display text-xl font-semibold text-navy">
            {priceFormatter.format(product.price)}
          </span>
          {product.rating !== null ? (
            <span className="text-sm text-navy-muted">
              ★ {product.rating.toFixed(1)}
              {product.rating_count !== null &&
                ` · ${product.rating_count.toLocaleString('en-IN')} reviews`}
            </span>
          ) : (
            <span className="text-xs text-navy-muted">Rating not listed</span>
          )}
        </div>
        {product.source === 'amazon' ? (
          <p className="mt-2 text-xs leading-5 text-navy-muted">
            Illustrative historical price; availability unverified.
          </p>
        ) : product.is_available === null ? (
          <p className="mt-2 text-xs leading-5 text-navy-muted">
            Availability not listed in this saved snapshot.
          </p>
        ) : (
          <p className="mt-2 text-xs leading-5 text-navy-muted">
            {product.is_available
              ? 'Available in the saved catalogue snapshot.'
              : 'Unavailable in the saved catalogue snapshot.'}
          </p>
        )}

        <div className="mt-auto flex flex-col pt-4">
          {compareProduct && (
            <AmazonComparisonToggleButton product={compareProduct} />
          )}
          <button
            type="button"
            onClick={onViewDetails}
            className="mt-2 rounded-full border border-sage/50 px-4 py-2.5 text-sm font-semibold text-sage-strong transition hover:bg-sage-soft/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
          >
            Product details
          </button>
        </div>
      </div>
    </article>
  )
}

function SavedProductDetails({
  product,
  isSaved,
  onClose,
  onRemove,
}: {
  product: WishlistProduct
  isSaved: boolean
  onClose: () => void
  onRemove: () => void
}) {
  const listedAttributes = Object.entries(product.attributes).filter(
    ([, value]) =>
      typeof value === 'string' ||
      typeof value === 'number' ||
      typeof value === 'boolean',
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close saved product details"
        onClick={onClose}
        className="absolute inset-0 bg-navy/50"
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="saved-product-title"
        className="relative z-10 max-h-[90dvh] w-full max-w-3xl overflow-y-auto rounded-3xl border border-border bg-surface p-5 shadow-soft sm:p-7"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-sage-strong">
              Saved product snapshot
            </p>
            <h2
              id="saved-product-title"
              className="mt-2 font-display text-2xl font-semibold text-navy"
            >
              {product.name}
            </h2>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <SaveProductButton
              isSaved={isSaved}
              onToggle={onRemove}
              className="h-10 w-10"
            />
            <button
              type="button"
              aria-label="Close saved product details"
              onClick={onClose}
              className="rounded-full border border-border p-2 text-navy-muted hover:bg-ivory"
            >
              <X aria-hidden className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-5 sm:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
          <AmazonCatalogueImage
            src={product.image_url}
            alt={product.name}
            wrapperClassName="aspect-square bg-ivory-deep"
            imageClassName="object-contain p-4"
          />
          <div className="space-y-3">
            <p className="text-sm text-navy-muted">
              {product.brand || 'Brand not listed'} · {product.category}
            </p>
            <p className="font-display text-3xl font-semibold text-navy">
              {priceFormatter.format(product.price)}
            </p>
            <p className="text-sm text-navy-muted">
              {product.rating === null
                ? 'Rating not listed.'
                : `${product.rating.toFixed(1)} / 5${
                    product.rating_count === null
                      ? ''
                      : ` · ${product.rating_count.toLocaleString('en-IN')} reviews`
                  }`}
            </p>
            {product.source === 'amazon' ? (
              <p className="text-xs leading-5 text-navy-muted">
                Historical illustrative INR conversion; not current Indian
                retail pricing. Availability is unverified.
              </p>
            ) : (
              <p className="text-xs leading-5 text-navy-muted">
                Saved from the curated catalogue. Availability may have changed.
              </p>
            )}
            {product.source === 'amazon' && (
              <p className="text-xs text-navy-muted">ASIN: {product.asin}</p>
            )}
            {product.description.length > 0 ? (
              <section>
                <h3 className="text-sm font-semibold text-navy">Description</h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6 text-navy-muted">
                  {product.description.map((text, index) => (
                    <li key={`${product.key}-description-${index}`}>{text}</li>
                  ))}
                </ul>
              </section>
            ) : (
              <p className="text-sm text-navy-muted">
                No description was available when this product was saved.
              </p>
            )}
            {product.features.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-navy">Listed features</h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6 text-navy-muted">
                  {product.features.map((feature, index) => (
                    <li key={`${product.key}-feature-${index}`}>{feature}</li>
                  ))}
                </ul>
              </section>
            )}
            {listedAttributes.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-navy">
                  Listed attributes
                </h3>
                <dl className="mt-1 space-y-1 text-sm text-navy-muted">
                  {listedAttributes.map(([label, value]) => (
                    <div
                      key={label}
                      className="flex flex-wrap gap-x-2"
                    >
                      <dt className="font-medium text-navy">{label}:</dt>
                      <dd>{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}

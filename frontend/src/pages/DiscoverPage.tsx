import { useEffect, useMemo, useState } from 'react'
import { ArrowDownWideNarrow, Search, Star, X } from 'lucide-react'
import {
  ApiRequestError,
  getAmazonCatalogueProduct,
  listAmazonCatalogueProducts,
} from '../services/api'
import { recordAmazonProductViewed } from '../services/amazonRecentlyViewed'
import type { AmazonCatalogueProduct } from '../types/amazonCatalogue'
import {
  AmazonCatalogueCard,
  AmazonCatalogueImage,
} from '../components/AmazonCatalogueCard'
import { AmazonComparisonPanel } from '../components/AmazonComparisonPanel'
import { SaveProductButton } from '../components/SaveProductButton'
import { useAmazonComparison } from '../services/amazonComparison'
import { useWishlist } from '../services/wishlist'

const PAGE_SIZE = 24
const API_PAGE_SIZE = 100
const priceFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})
const countFormatter = new Intl.NumberFormat('en-IN')

type SortOrder = 'relevance' | 'price-asc' | 'price-desc' | 'rating' | 'reviews'

function isSortOrder(value: string): value is SortOrder {
  return (
    value === 'relevance' ||
    value === 'price-asc' ||
    value === 'price-desc' ||
    value === 'rating' ||
    value === 'reviews'
  )
}

async function loadAllCatalogueProducts(): Promise<{
  products: AmazonCatalogueProduct[]
  categories: string[]
  total: number
}> {
  const firstPage = await listAmazonCatalogueProducts({
    limit: API_PAGE_SIZE,
    offset: 0,
  })
  const offsets = Array.from(
    { length: Math.max(0, Math.ceil(firstPage.total / API_PAGE_SIZE) - 1) },
    (_, index) => (index + 1) * API_PAGE_SIZE,
  )
  const remainingPages = await Promise.all(
    offsets.map((offset) =>
      listAmazonCatalogueProducts({ limit: API_PAGE_SIZE, offset }),
    ),
  )

  return {
    products: [
      ...firstPage.products,
      ...remainingPages.flatMap((page) => page.products),
    ],
    categories: firstPage.categories,
    total: firstPage.total,
  }
}

function parsePrice(value: string): number | null {
  if (!value.trim()) return null
  const price = Number(value)
  return Number.isFinite(price) && price >= 0 ? price : Number.NaN
}

function productMatchesSearch(
  product: AmazonCatalogueProduct,
  query: string,
): boolean {
  if (!query) return true
  const searchableText = [
    product.title,
    product.store ?? '',
    product.category,
    ...product.description,
    ...product.features,
  ]
    .join(' ')
    .toLowerCase()
  return searchableText.includes(query)
}

function sortProducts(
  products: AmazonCatalogueProduct[],
  order: SortOrder,
): AmazonCatalogueProduct[] {
  const sorted = [...products]
  sorted.sort((first, second) => {
    if (order === 'price-asc') {
      return first.price_inr - second.price_inr || first.asin.localeCompare(second.asin)
    }
    if (order === 'price-desc') {
      return second.price_inr - first.price_inr || first.asin.localeCompare(second.asin)
    }
    if (order === 'rating') {
      return (
        second.rating - first.rating ||
        second.rating_count - first.rating_count ||
        first.asin.localeCompare(second.asin)
      )
    }
    if (order === 'reviews') {
      return (
        second.rating_count - first.rating_count ||
        second.rating - first.rating ||
        first.asin.localeCompare(second.asin)
      )
    }
    return (
      second.rating_count - first.rating_count ||
      second.rating - first.rating ||
      first.asin.localeCompare(second.asin)
    )
  })
  return sorted
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError && error.status >= 500) {
    return 'The Discover catalogue is temporarily unavailable. Please try again.'
  }
  if (error instanceof TypeError) {
    return 'We could not connect to the Discover catalogue. Check your connection and try again.'
  }
  return 'We could not load the Discover catalogue. Please try again.'
}

export function DiscoverPage() {
  const [categories, setCategories] = useState<string[]>([])
  const [category, setCategory] = useState('')
  const [searchText, setSearchText] = useState('')
  const [search, setSearch] = useState('')
  const [minimumPrice, setMinimumPrice] = useState('')
  const [maximumPrice, setMaximumPrice] = useState('')
  const [minimumRating, setMinimumRating] = useState('')
  const [sortOrder, setSortOrder] = useState<SortOrder>('relevance')
  const [page, setPage] = useState(0)
  const [products, setProducts] = useState<AmazonCatalogueProduct[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)
  const [selectedAsin, setSelectedAsin] = useState<string | null>(null)
  const [selectedProduct, setSelectedProduct] =
    useState<AmazonCatalogueProduct | null>(null)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [detailsError, setDetailsError] = useState<string | null>(null)
  const [detailsRetryCount, setDetailsRetryCount] = useState(0)
  const [recentlyViewedError, setRecentlyViewedError] = useState<string | null>(
    null,
  )
  const [selectedImageIndex, setSelectedImageIndex] = useState(0)
  const wishlist = useWishlist()
  const comparison = useAmazonComparison()

  useEffect(() => {
    let active = true
    async function loadCatalogue() {
      setLoading(true)
      setError(null)
      try {
        const result = await loadAllCatalogueProducts()
        if (!active) return
        setProducts(result.products)
        setCategories(result.categories)
        setTotal(result.total)
      } catch (requestError: unknown) {
        if (active) setError(getErrorMessage(requestError))
      } finally {
        if (active) setLoading(false)
      }
    }

    void loadCatalogue()
    return () => {
      active = false
    }
  }, [retryCount])

  useEffect(() => {
    if (!selectedAsin) return
    let active = true
    getAmazonCatalogueProduct(selectedAsin)
      .then((product) => {
        if (active) setSelectedProduct(product)
      })
      .catch((requestError: unknown) => {
        if (active) setDetailsError(getErrorMessage(requestError))
      })
      .finally(() => {
        if (active) setDetailsLoading(false)
      })
    return () => {
      active = false
    }
  }, [detailsRetryCount, selectedAsin])

  useEffect(() => {
    if (!selectedAsin) return
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setSelectedAsin(null)
        setSelectedProduct(null)
        setDetailsError(null)
        setDetailsLoading(false)
      }
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [selectedAsin])

  function applySearch() {
    const nextSearch = searchText.trim()
    setPage(0)
    setSearch(nextSearch)
  }

  function clearSearch() {
    setSearchText('')
    setSearch('')
    setPage(0)
  }

  function clearFilters() {
    setSearchText('')
    setSearch('')
    setCategory('')
    setMinimumPrice('')
    setMaximumPrice('')
    setMinimumRating('')
    setSortOrder('relevance')
    setPage(0)
  }

  function retry() {
    setLoading(true)
    setError(null)
    setRetryCount((count) => count + 1)
  }

  function openDetails(asin: string) {
    if (selectedAsin === asin) return
    const catalogueProduct = products.find((product) => product.asin === asin)
    if (catalogueProduct) {
      setRecentlyViewedError(
        recordAmazonProductViewed(catalogueProduct).error,
      )
    } else {
      setRecentlyViewedError(null)
    }
    setSelectedProduct(null)
    setDetailsError(null)
    setDetailsLoading(true)
    setDetailsRetryCount(0)
    setSelectedImageIndex(0)
    setSelectedAsin(asin)
  }

  function closeDetails() {
    setSelectedAsin(null)
    setSelectedProduct(null)
    setDetailsError(null)
    setDetailsLoading(false)
  }

  const minimumPriceValue = parsePrice(minimumPrice)
  const maximumPriceValue = parsePrice(maximumPrice)
  const invalidPriceRange =
    Number.isNaN(minimumPriceValue) ||
    Number.isNaN(maximumPriceValue) ||
    (minimumPriceValue !== null &&
      maximumPriceValue !== null &&
      minimumPriceValue > maximumPriceValue)
  const priceFilterError =
    Number.isNaN(minimumPriceValue) || Number.isNaN(maximumPriceValue)
      ? 'Enter a valid non-negative price.'
      : minimumPriceValue !== null &&
          maximumPriceValue !== null &&
          minimumPriceValue > maximumPriceValue
        ? 'Minimum price must not exceed maximum price.'
        : null
  const filteredProducts = useMemo(() => {
    if (invalidPriceRange) return []
    const query = search.trim().toLowerCase()
    const filtered = products.filter(
      (product) =>
        (!category || product.category === category) &&
        productMatchesSearch(product, query) &&
        (minimumPriceValue === null ||
          product.price_inr >= minimumPriceValue) &&
        (maximumPriceValue === null ||
          product.price_inr <= maximumPriceValue) &&
        (!minimumRating || product.rating >= Number(minimumRating)),
    )
    return sortProducts(filtered, sortOrder)
  }, [
    category,
    invalidPriceRange,
    maximumPriceValue,
    minimumPriceValue,
    minimumRating,
    products,
    search,
    sortOrder,
  ])
  const pageCount = Math.ceil(filteredProducts.length / PAGE_SIZE)
  const pageProducts = filteredProducts.slice(
    page * PAGE_SIZE,
    (page + 1) * PAGE_SIZE,
  )
  const hasActiveFilters = Boolean(
    category ||
      search ||
      minimumPrice ||
      maximumPrice ||
      minimumRating ||
      sortOrder !== 'relevance',
  )
  const detailImages = selectedProduct
    ? getProductImageUrls(selectedProduct)
    : []

  return (
    <section
      className={`space-y-6 ${
        comparison.products.length > 0 ? 'pb-28' : ''
      }`}
    >
      {wishlist.error && (
        <p role="status" className="rounded-2xl bg-surface px-4 py-3 text-sm text-navy-muted">
          {wishlist.error}
        </p>
      )}
      <header className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sage">
          The Discover collection
        </p>
        <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-navy sm:text-4xl">
          Browse electronics
        </h2>
        <p className="mt-3 text-sm leading-6 text-navy-muted sm:text-base">
          Explore electronics by category, price, rating, or features. Prices
          are illustrative historical USD conversions at ₹85 per US dollar;
          availability has not been verified.
        </p>
      </header>

      <section
        aria-label="Discover products"
        className="rounded-3xl border border-border bg-surface p-4 shadow-soft sm:p-6"
      >
        <form
          onSubmit={(event) => {
            event.preventDefault()
            applySearch()
          }}
          className="flex flex-col gap-3 sm:flex-row"
        >
          <div className="relative min-w-0 flex-1">
            <label htmlFor="discover-search" className="sr-only">
              Search products
            </label>
            <Search
              aria-hidden
              className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-navy-muted"
            />
            <input
              id="discover-search"
              type="text"
              inputMode="search"
              maxLength={120}
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="Search names, brands or features"
              className="w-full rounded-full border border-border bg-white py-3 pl-11 pr-11 text-sm text-navy outline-none transition placeholder:text-navy-muted/70 focus:border-sage focus:ring-2 focus:ring-sage/15"
            />
            {searchText && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={clearSearch}
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1.5 text-navy-muted hover:bg-ivory hover:text-navy"
              >
                <X aria-hidden className="h-4 w-4" />
              </button>
            )}
          </div>
          <button
            type="submit"
            className="rounded-full bg-sage px-6 py-3 text-sm font-semibold text-white transition hover:bg-sage-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage"
          >
            Search
          </button>
        </form>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            aria-pressed={!category}
            onClick={() => {
              if (!category) return
              setCategory('')
              setPage(0)
            }}
            className={`rounded-full px-4 py-2 text-xs font-semibold transition ${
              !category
                ? 'bg-sage text-white'
                : 'border border-border bg-white text-navy-muted hover:bg-ivory'
            }`}
          >
            All categories
          </button>
          {categories.map((item) => (
            <button
              key={item}
              type="button"
              aria-pressed={category === item}
              onClick={() => {
                if (category === item) return
                setCategory(item)
                setPage(0)
              }}
              className={`rounded-full px-4 py-2 text-xs font-semibold transition ${
                category === item
                  ? 'bg-sage text-white'
                  : 'border border-border bg-white text-navy-muted hover:bg-ivory'
              }`}
            >
              {item}
            </button>
          ))}
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <label className="block text-xs font-semibold text-navy-muted">
            Minimum price
            <span className="relative mt-1.5 block">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-navy-muted">
                ₹
              </span>
              <input
                type="number"
                min="0"
                step="1"
                inputMode="numeric"
                value={minimumPrice}
                onChange={(event) => {
                  setMinimumPrice(event.target.value)
                  setPage(0)
                }}
                placeholder="No minimum"
                className="w-full rounded-xl border border-border bg-white py-2.5 pl-7 pr-3 text-sm font-normal text-navy outline-none focus:border-sage focus:ring-2 focus:ring-sage/15"
              />
            </span>
          </label>
          <label className="block text-xs font-semibold text-navy-muted">
            Maximum price
            <span className="relative mt-1.5 block">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-navy-muted">
                ₹
              </span>
              <input
                type="number"
                min="0"
                step="1"
                inputMode="numeric"
                value={maximumPrice}
                onChange={(event) => {
                  setMaximumPrice(event.target.value)
                  setPage(0)
                }}
                placeholder="No maximum"
                className="w-full rounded-xl border border-border bg-white py-2.5 pl-7 pr-3 text-sm font-normal text-navy outline-none focus:border-sage focus:ring-2 focus:ring-sage/15"
              />
            </span>
          </label>
          <label className="block text-xs font-semibold text-navy-muted">
            Minimum rating
            <select
              value={minimumRating}
              onChange={(event) => {
                setMinimumRating(event.target.value)
                setPage(0)
              }}
              className="mt-1.5 w-full rounded-xl border border-border bg-white px-3 py-2.5 text-sm font-normal text-navy outline-none focus:border-sage focus:ring-2 focus:ring-sage/15"
            >
              <option value="">Any rating</option>
              <option value="3.5">3.5 and above</option>
              <option value="4">4 and above</option>
              <option value="4.5">4.5 and above</option>
            </select>
          </label>
          <label className="block text-xs font-semibold text-navy-muted">
            Sort by
            <span className="relative mt-1.5 block">
              <ArrowDownWideNarrow
                aria-hidden
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-sage-strong"
              />
              <select
                value={sortOrder}
                onChange={(event) => {
                  const value = event.target.value
                  if (isSortOrder(value)) {
                    setSortOrder(value)
                    setPage(0)
                  }
                }}
                className="w-full appearance-none rounded-xl border border-border bg-white py-2.5 pl-9 pr-3 text-sm font-normal text-navy outline-none focus:border-sage focus:ring-2 focus:ring-sage/15"
              >
                <option value="relevance">Relevance</option>
                <option value="price-asc">Price: low to high</option>
                <option value="price-desc">Price: high to low</option>
                <option value="rating">Highest rated</option>
                <option value="reviews">Most reviewed</option>
              </select>
            </span>
          </label>
          <div className="flex items-end">
            <button
              type="button"
              disabled={!hasActiveFilters && !searchText}
              onClick={clearFilters}
              className="w-full rounded-xl border border-sage/40 bg-white px-4 py-2.5 text-sm font-semibold text-sage-strong transition hover:bg-sage-soft/40 disabled:cursor-not-allowed disabled:opacity-45"
            >
              Clear all filters
            </button>
          </div>
        </div>
        {priceFilterError && (
          <p role="alert" className="mt-3 text-xs text-danger">
            {priceFilterError}
          </p>
        )}
        <p className="mt-4 border-t border-border pt-3 text-xs leading-5 text-navy-muted">
          Search includes product names, stores, categories, descriptions and
          listed features. Availability is unverified.
        </p>
      </section>

      {loading ? (
        <CatalogueSkeletonGrid />
      ) : error ? (
        <div className="rounded-3xl border border-border bg-surface px-6 py-10 text-center shadow-soft">
          <p role="alert" className="text-sm leading-6 text-danger">
            {error}
          </p>
          <button
            type="button"
            onClick={retry}
            className="mt-4 rounded-full bg-sage px-5 py-2.5 text-sm font-semibold text-white hover:bg-sage-strong"
          >
            Try again
          </button>
        </div>
      ) : filteredProducts.length === 0 ? (
        <div className="rounded-3xl border border-border bg-surface px-6 py-12 text-center shadow-soft">
          <h3 className="font-display text-xl font-semibold text-navy">
            {priceFilterError
              ? 'Check your price filters'
              : products.length === 0
                ? 'The catalogue is empty'
                : 'No products match these filters'}
          </h3>
          <p className="mt-2 text-sm text-navy-muted">
            {priceFilterError ??
              (products.length === 0
                ? 'There are no products to display right now.'
                : 'Try a different search, broaden your filters, or clear them to see more products.')}
          </p>
          {(hasActiveFilters || searchText) && (
            <button
              type="button"
              onClick={clearFilters}
              className="mt-4 rounded-full border border-sage/50 px-4 py-2 text-sm font-semibold text-sage-strong hover:bg-sage-soft/50"
            >
              Clear all filters
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-navy-muted">
              {countFormatter.format(filteredProducts.length)} matching products
              {category ? ` in ${category}` : ''}
              <span className="ml-1 text-xs">
                · {countFormatter.format(total)} in catalogue
              </span>
            </p>
            {pageCount > 1 && (
              <p className="text-xs text-navy-muted">
                Page {page + 1} of {pageCount}
              </p>
            )}
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {pageProducts.map((product) => (
              <AmazonCatalogueCard
                key={product.asin}
                product={product}
                onViewDetails={openDetails}
              />
            ))}
          </div>
          {pageCount > 1 && (
            <nav
              aria-label="Catalogue pages"
              className="flex items-center justify-center gap-3"
            >
              <button
                type="button"
                disabled={page === 0}
                onClick={() => {
                  setPage((current) => Math.max(0, current - 1))
                }}
                className="rounded-full border border-border bg-surface px-4 py-2 text-sm font-semibold text-navy-muted disabled:opacity-40"
              >
                Previous
              </button>
              <button
                type="button"
                disabled={page + 1 >= pageCount}
                onClick={() => {
                  setPage((current) => current + 1)
                }}
                className="rounded-full border border-border bg-surface px-4 py-2 text-sm font-semibold text-navy-muted disabled:opacity-40"
              >
                Next
              </button>
            </nav>
          )}
        </>
      )}

      {selectedAsin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            aria-label="Close product details"
            onClick={closeDetails}
            className="absolute inset-0 bg-navy/50"
          />
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="amazon-product-title"
            className="relative z-10 max-h-[90dvh] w-full max-w-2xl overflow-y-auto rounded-3xl border border-border bg-surface p-5 shadow-soft sm:p-7"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-sage-strong">
                  Product details
                </p>
                <h2
                  id="amazon-product-title"
                  className="mt-2 font-display text-2xl font-semibold text-navy"
                >
                  {selectedProduct?.title ?? 'Loading product details'}
                </h2>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {selectedProduct && (
                  <SaveProductButton
                    isSaved={wishlist.isSaved(selectedProduct)}
                    onToggle={() => wishlist.toggle(selectedProduct)}
                    showLabel
                    className="px-3 py-2"
                  />
                )}
                <button
                  type="button"
                  aria-label="Back to Discover results"
                  onClick={closeDetails}
                  className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-2 text-xs font-semibold text-navy-muted hover:bg-ivory"
                >
                  <X aria-hidden className="h-4 w-4" />
                  <span className="hidden sm:inline">Back to Discover</span>
                </button>
              </div>
            </div>

            {detailsLoading ? (
              <div role="status" className="mt-6 space-y-4" aria-live="polite">
                <p className="text-sm text-navy-muted">
                  Loading product details…
                </p>
                <div className="grid animate-pulse gap-5 sm:grid-cols-2">
                  <div className="aspect-square rounded-2xl bg-ivory-deep" />
                  <div className="space-y-3">
                    <div className="h-5 w-3/4 rounded bg-ivory-deep" />
                    <div className="h-5 w-1/2 rounded bg-ivory-deep" />
                    <div className="h-24 rounded-2xl bg-ivory-deep" />
                  </div>
                </div>
              </div>
            ) : detailsError ? (
              <div className="mt-6 rounded-2xl border border-danger/20 bg-ivory p-4">
                <p role="alert" className="text-sm text-danger">
                  {detailsError}
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setDetailsError(null)
                    setDetailsLoading(true)
                    setDetailsRetryCount((count) => count + 1)
                  }}
                  className="mt-3 rounded-full bg-sage px-4 py-2 text-sm font-semibold text-white hover:bg-sage-strong"
                >
                  Try again
                </button>
              </div>
            ) : selectedProduct ? (
              <div className="mt-5 space-y-6">
                <div className="grid gap-5 sm:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
                  <div className="space-y-3">
                    <AmazonCatalogueImage
                      key={`${selectedProduct.asin}-${detailImages[selectedImageIndex]}`}
                      src={detailImages[selectedImageIndex] ?? null}
                      alt={selectedProduct.title}
                      wrapperClassName="aspect-square bg-ivory-deep"
                      imageClassName="object-contain p-4"
                    />
                    {detailImages.length > 1 && (
                      <div
                        role="group"
                        aria-label="Product image gallery"
                        className="flex flex-wrap gap-2"
                      >
                        {detailImages.map((imageUrl, index) => (
                          <button
                            key={`${selectedProduct.asin}-image-${index}`}
                            type="button"
                            aria-label={`View product image ${index + 1}`}
                            aria-pressed={selectedImageIndex === index}
                            onClick={() => setSelectedImageIndex(index)}
                            className={`w-16 rounded-xl border p-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sage ${
                              selectedImageIndex === index
                                ? 'border-sage ring-2 ring-sage/20'
                                : 'border-border'
                            }`}
                          >
                            <AmazonCatalogueImage
                              src={imageUrl}
                              alt=""
                              wrapperClassName="aspect-square bg-ivory"
                              imageClassName="object-contain"
                            />
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="space-y-4">
                    <p className="text-sm text-navy-muted">
                      {selectedProduct.store || 'Brand not listed'} ·{' '}
                      {selectedProduct.category}
                    </p>
                    <p className="text-xs text-navy-muted">
                      ASIN: {selectedProduct.asin}
                    </p>
                    <p className="font-display text-3xl font-semibold text-navy">
                      {priceFormatter.format(selectedProduct.price_inr)}
                    </p>
                    <p className="text-xs text-navy-muted">
                      Illustrative historical price; not a current Indian retail price.
                    </p>
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-navy">
                        <Star
                          aria-hidden
                          className="h-4 w-4 fill-amber-400 text-amber-500"
                        />
                        {selectedProduct.rating.toFixed(1)} / 5
                      </span>
                      <span className="text-sm text-navy-muted">
                        {countFormatter.format(selectedProduct.rating_count)} ratings
                      </span>
                      <span className="rounded-full bg-sage-soft px-3 py-1 text-xs font-semibold text-sage-strong">
                        Availability unverified
                      </span>
                    </div>
                    <p className="text-xs leading-5 text-navy-muted">
                      Historical USD price converted at ₹
                      {String(
                        selectedProduct.source_metadata.usd_to_inr_rate ?? '85',
                      )}
                      /USD.
                    </p>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <section className="rounded-2xl border border-border bg-white p-4">
                    <h3 className="text-sm font-semibold text-navy">
                      Description
                    </h3>
                    {selectedProduct.description.length > 0 ? (
                      <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-6 text-navy-muted">
                        {selectedProduct.description.map((text, index) => (
                          <li key={`${selectedProduct.asin}-description-${index}`}>
                            {text}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm leading-6 text-navy-muted">
                        No description was provided in the catalogue record.
                      </p>
                    )}
                  </section>
                  <section className="rounded-2xl border border-border bg-white p-4">
                    <h3 className="text-sm font-semibold text-navy">
                      Features and specifications
                    </h3>
                    {selectedProduct.features.length > 0 ? (
                      <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-6 text-navy-muted">
                        {selectedProduct.features.map((feature, index) => (
                          <li key={`${selectedProduct.asin}-feature-${index}`}>
                            {feature}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm leading-6 text-navy-muted">
                        No feature or structured specification details were
                        provided for this product.
                      </p>
                    )}
                    <p className="mt-3 border-t border-border pt-3 text-xs leading-5 text-navy-muted">
                      Only information present in catalogue metadata is shown;
                      unavailable product facts have not been inferred.
                    </p>
                  </section>
                </div>

                <p className="border-t border-border pt-3 text-xs text-navy-muted">
                  Source ASIN: {selectedProduct.asin} · Amazon Reviews 2023
                  metadata. Availability is unverified.
                </p>
                {recentlyViewedError && (
                  <p role="status" className="text-sm text-navy-muted">
                    {recentlyViewedError}
                  </p>
                )}
                {wishlist.error && (
                  <p role="status" className="text-sm text-navy-muted">
                    {wishlist.error}
                  </p>
                )}
              </div>
            ) : null}
          </section>
        </div>
      )}

      <AmazonComparisonPanel />
    </section>
  )
}

function getProductImageUrls(product: AmazonCatalogueProduct): string[] {
  const metadataImages = product.source_metadata.image_urls
  const extraImages = Array.isArray(metadataImages)
    ? metadataImages.filter(
        (value): value is string =>
          typeof value === 'string' && /^https?:\/\/\S+$/i.test(value),
      )
    : []
  return [...new Set([product.image_url, ...extraImages])]
}

function CatalogueSkeletonGrid() {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">Loading the Discover catalogue…</span>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {Array.from({ length: 8 }, (_, index) => (
          <article
            key={`catalogue-skeleton-${index}`}
            aria-hidden
            className="overflow-hidden rounded-2xl border border-border bg-surface p-4 shadow-soft"
          >
            <div className="aspect-[4/3] animate-pulse rounded-xl bg-ivory-deep" />
            <div className="mt-4 space-y-3">
              <div className="h-3 w-1/3 animate-pulse rounded bg-ivory-deep" />
              <div className="h-5 w-full animate-pulse rounded bg-ivory-deep" />
              <div className="h-5 w-3/4 animate-pulse rounded bg-ivory-deep" />
              <div className="h-8 w-1/2 animate-pulse rounded bg-ivory-deep" />
              <div className="h-10 w-full animate-pulse rounded-full bg-ivory-deep" />
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}

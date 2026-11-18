import type { AmazonCatalogueProduct } from '../types/amazonCatalogue'

export const AMAZON_RECENTLY_VIEWED_STORAGE_KEY =
  'smartshopper.amazonRecentlyViewed.v1'
const MAX_RECENTLY_VIEWED_PRODUCTS = 30

type AmazonRecentlyViewedFields = Pick<
  AmazonCatalogueProduct,
  | 'asin'
  | 'title'
  | 'store'
  | 'category'
  | 'price_inr'
  | 'rating'
  | 'image_url'
> & {
  rating_count: number | null
}

export type AmazonRecentlyViewedItem = AmazonRecentlyViewedFields & {
  viewed_at: string
}

export type AmazonRecentlyViewedResult = {
  items: AmazonRecentlyViewedItem[]
  error: string | null
}

const EMPTY_RESULT: AmazonRecentlyViewedResult = {
  items: [],
  error: null,
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isRecentlyViewedItem(
  value: unknown,
): value is AmazonRecentlyViewedItem {
  if (!isRecord(value)) return false
  const viewedAt =
    typeof value.viewed_at === 'string' ? new Date(value.viewed_at) : null
  return (
    typeof value.asin === 'string' &&
    value.asin.length > 0 &&
    typeof value.title === 'string' &&
    (typeof value.store === 'string' || value.store === null) &&
    typeof value.category === 'string' &&
    typeof value.price_inr === 'number' &&
    Number.isFinite(value.price_inr) &&
    value.price_inr >= 0 &&
    typeof value.rating === 'number' &&
    Number.isFinite(value.rating) &&
    value.rating >= 0 &&
    value.rating <= 5 &&
    (value.rating_count === null ||
      (typeof value.rating_count === 'number' &&
        Number.isFinite(value.rating_count) &&
        value.rating_count >= 0)) &&
    typeof value.image_url === 'string' &&
    viewedAt !== null &&
    Number.isFinite(viewedAt.getTime())
  )
}

export function readAmazonRecentlyViewed(): AmazonRecentlyViewedResult {
  if (typeof window === 'undefined') return EMPTY_RESULT
  try {
    const stored = window.localStorage.getItem(
      AMAZON_RECENTLY_VIEWED_STORAGE_KEY,
    )
    if (!stored) return EMPTY_RESULT

    const parsed: unknown = JSON.parse(stored)
    if (
      !isRecord(parsed) ||
      parsed.version !== 1 ||
      !Array.isArray(parsed.items)
    ) {
      return {
        items: [],
        error: 'Saved Amazon viewing history could not be restored.',
      }
    }

    const items = parsed.items.filter(isRecentlyViewedItem)
    const hasInvalidItems = items.length !== parsed.items.length
    const seenAsins = new Set<string>()
    const uniqueItems = items
      .sort(
        (first, second) =>
          new Date(second.viewed_at).getTime() -
          new Date(first.viewed_at).getTime(),
      )
      .filter((item) => {
        if (seenAsins.has(item.asin)) return false
        seenAsins.add(item.asin)
        return true
      })
    return {
      items: uniqueItems.slice(0, MAX_RECENTLY_VIEWED_PRODUCTS),
      error: hasInvalidItems
        ? 'Some saved Amazon viewing history could not be restored.'
        : null,
    }
  } catch {
    return {
      items: [],
      error: 'Amazon viewing history is unavailable in this browser.',
    }
  }
}

export function recordAmazonProductViewed(
  product: AmazonRecentlyViewedFields,
): AmazonRecentlyViewedResult {
  if (typeof window === 'undefined') {
    return {
      items: [],
      error: 'Amazon viewing history is unavailable in this browser.',
    }
  }

  const item: AmazonRecentlyViewedItem = {
    ...product,
    viewed_at: new Date().toISOString(),
  }
  if (!isRecentlyViewedItem(item)) {
    return {
      items: readAmazonRecentlyViewed().items,
      error: 'This Amazon product could not be saved to viewing history.',
    }
  }

  const current = readAmazonRecentlyViewed()
  const items = [
    {
      asin: item.asin,
      title: item.title,
      store: item.store,
      category: item.category,
      price_inr: item.price_inr,
      rating: item.rating,
      rating_count: item.rating_count,
      image_url: item.image_url,
      viewed_at: item.viewed_at,
    },
    ...current.items.filter((savedItem) => savedItem.asin !== item.asin),
  ].slice(0, MAX_RECENTLY_VIEWED_PRODUCTS)

  try {
    window.localStorage.setItem(
      AMAZON_RECENTLY_VIEWED_STORAGE_KEY,
      JSON.stringify({ version: 1, items }),
    )
    return { items, error: null }
  } catch {
    return {
      items: current.items,
      error: 'Amazon viewing history could not be saved in this browser.',
    }
  }
}

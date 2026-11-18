import { useSyncExternalStore } from 'react'
import type { AssistantRecommendation } from '../types/assistant'
import type { AmazonCatalogueProduct } from '../types/amazonCatalogue'
import type { Product } from '../types/product'

export const WISHLIST_STORAGE_KEY = 'smartshopper.wishlist.v1'

export type WishlistProduct = {
  key: string
  source: 'amazon' | 'curated'
  product_id: string
  asin: string | null
  name: string
  brand: string
  category: string
  price: number
  rating: number | null
  rating_count: number | null
  image_url: string | null
  description: string[]
  features: string[]
  attributes: Record<string, unknown>
  is_available: boolean | null
  price_is_historical: boolean
  saved_at: string
}

export type SaveableProduct =
  | Product
  | AmazonCatalogueProduct
  | AssistantRecommendation

type WishlistSnapshot = {
  items: WishlistProduct[]
  error: string | null
}

const EMPTY_SNAPSHOT: WishlistSnapshot = { items: [], error: null }
const listeners = new Set<() => void>()
let cachedSnapshot: WishlistSnapshot | undefined

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isWishlistProduct(value: unknown): value is WishlistProduct {
  if (!isRecord(value)) return false
  const savedAt =
    typeof value.saved_at === 'string' ? new Date(value.saved_at) : null
  if (
    (value.source !== 'amazon' && value.source !== 'curated') ||
    typeof value.key !== 'string' ||
    typeof value.product_id !== 'string' ||
    (value.asin !== null && typeof value.asin !== 'string') ||
    typeof value.name !== 'string' ||
    typeof value.brand !== 'string' ||
    typeof value.category !== 'string' ||
    typeof value.price !== 'number' ||
    !Number.isFinite(value.price) ||
    value.price < 0 ||
    (value.rating !== null &&
      (typeof value.rating !== 'number' ||
        !Number.isFinite(value.rating) ||
        value.rating < 0 ||
        value.rating > 5)) ||
    (value.rating_count !== null &&
      (typeof value.rating_count !== 'number' ||
        !Number.isFinite(value.rating_count) ||
        value.rating_count < 0)) ||
    (value.image_url !== null && typeof value.image_url !== 'string') ||
    !isStringList(value.description) ||
    !isStringList(value.features) ||
    !isRecord(value.attributes) ||
    (value.is_available !== null && typeof value.is_available !== 'boolean') ||
    typeof value.price_is_historical !== 'boolean' ||
    savedAt === null ||
    !Number.isFinite(savedAt.getTime())
  ) {
    return false
  }

  if (value.source === 'amazon') {
    return (
      typeof value.asin === 'string' &&
      value.asin.length > 0 &&
      value.key === amazonWishlistKey(value.asin) &&
      value.product_id === `amazon:${value.asin}` &&
      value.price_is_historical &&
      value.is_available === null
    )
  }

  return (
    value.asin === null &&
    value.key === curatedWishlistKey(value.product_id) &&
    !value.price_is_historical
  )
}

function amazonWishlistKey(asin: string): string {
  return `amazon:${asin.trim().toUpperCase()}`
}

function curatedWishlistKey(productId: string): string {
  return `curated:${productId.trim()}`
}

function normalizeWishlistItems(items: WishlistProduct[]): WishlistProduct[] {
  const seen = new Set<string>()
  return [...items]
    .sort(
      (first, second) =>
        new Date(second.saved_at).getTime() -
        new Date(first.saved_at).getTime(),
    )
    .filter((item) => {
      if (seen.has(item.key)) return false
      seen.add(item.key)
      return true
    })
}

function readWishlist(): WishlistSnapshot {
  if (typeof window === 'undefined') return EMPTY_SNAPSHOT
  try {
    const stored = window.localStorage.getItem(WISHLIST_STORAGE_KEY)
    if (!stored) return EMPTY_SNAPSHOT

    const parsed: unknown = JSON.parse(stored)
    if (
      !isRecord(parsed) ||
      parsed.version !== 1 ||
      !Array.isArray(parsed.items)
    ) {
      return {
        items: [],
        error: 'Saved products could not be restored from this browser.',
      }
    }

    const validItems = parsed.items.filter(isWishlistProduct)
    return {
      items: normalizeWishlistItems(validItems),
      error:
        validItems.length === parsed.items.length
          ? null
          : 'Some saved products could not be restored from this browser.',
    }
  } catch {
    return {
      items: [],
      error: 'Saved products are unavailable in this browser.',
    }
  }
}

function getSnapshot(): WishlistSnapshot {
  if (!cachedSnapshot) cachedSnapshot = readWishlist()
  return cachedSnapshot
}

function notifyListeners() {
  listeners.forEach((listener) => listener())
}

function handleStorageChange(event: StorageEvent) {
  if (event.key === null || event.key === WISHLIST_STORAGE_KEY) {
    cachedSnapshot = readWishlist()
    notifyListeners()
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  if (listeners.size === 1 && typeof window !== 'undefined') {
    window.addEventListener('storage', handleStorageChange)
  }
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0 && typeof window !== 'undefined') {
      window.removeEventListener('storage', handleStorageChange)
    }
  }
}

function publish(items: WishlistProduct[]): string | null {
  const normalizedItems = normalizeWishlistItems(items)
  let error: string | null = null
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(
        WISHLIST_STORAGE_KEY,
        JSON.stringify({ version: 1, items: normalizedItems }),
      )
    } catch {
      error = 'Saved products could not be stored in this browser.'
    }
  } else {
    error = 'Saved products are unavailable in this browser.'
  }

  cachedSnapshot = { items: normalizedItems, error }
  notifyListeners()
  return error
}

function publishError(error: string): string {
  const current = getSnapshot()
  cachedSnapshot = { ...current, error }
  notifyListeners()
  return error
}

function toAmazonWishlistProduct(
  product: AmazonCatalogueProduct | AssistantRecommendation,
): WishlistProduct | null {
  const asin =
    'asin' in product
      ? product.asin.trim().toUpperCase()
      : product.product_id.replace(/^amazon:/i, '').trim().toUpperCase()
  if (!asin) return null

  const fromCatalogue = 'asin' in product
  return {
    key: amazonWishlistKey(asin),
    source: 'amazon',
    product_id: `amazon:${asin}`,
    asin,
    name: fromCatalogue ? product.title : product.name,
    brand: fromCatalogue ? product.store ?? '' : product.brand,
    category: product.category,
    price: fromCatalogue ? product.price_inr : product.price,
    rating: product.rating,
    rating_count: product.rating_count ?? null,
    image_url: product.image_url,
    description: fromCatalogue ? [...product.description] : [],
    features: fromCatalogue ? [...product.features] : [],
    attributes: {},
    is_available: null,
    price_is_historical: true,
    saved_at: new Date().toISOString(),
  }
}

function toCuratedWishlistProduct(
  product: Product | AssistantRecommendation,
): WishlistProduct {
  const fromCatalogue = 'id' in product
  const productId = product.product_id.trim()
  return {
    key: curatedWishlistKey(productId),
    source: 'curated',
    product_id: productId,
    asin: null,
    name: product.name,
    brand: product.brand,
    category: product.category,
    price: product.price,
    rating: product.rating,
    rating_count: fromCatalogue ? null : product.rating_count ?? null,
    image_url: product.image_url,
    description: fromCatalogue
      ? product.description
        ? [product.description]
        : []
      : [],
    features: [],
    attributes: fromCatalogue ? product.attributes : {},
    is_available: fromCatalogue
      ? product.is_available
      : product.availability_status === 'available'
        ? true
        : product.availability_status === 'unavailable'
          ? false
          : null,
    price_is_historical: false,
    saved_at: new Date().toISOString(),
  }
}

function toWishlistProduct(
  product: SaveableProduct,
): WishlistProduct | null {
  if ('asin' in product) return toAmazonWishlistProduct(product)
  if ('catalogue_source' in product && product.catalogue_source === 'amazon') {
    return toAmazonWishlistProduct(product)
  }
  return toCuratedWishlistProduct(product)
}

export function getWishlistProductKey(product: SaveableProduct): string | null {
  if ('asin' in product) return amazonWishlistKey(product.asin)
  if ('catalogue_source' in product && product.catalogue_source === 'amazon') {
    const asin = product.product_id.replace(/^amazon:/i, '').trim()
    return asin ? amazonWishlistKey(asin) : null
  }
  const productId = product.product_id.trim()
  return productId ? curatedWishlistKey(productId) : null
}

export function saveWishlistProduct(product: SaveableProduct): string | null {
  const item = toWishlistProduct(product)
  if (!item) return publishError('This product could not be saved.')
  const current = getSnapshot().items
  const existing = current.find((saved) => saved.key === item.key)
  if (existing) item.saved_at = existing.saved_at
  return publish([item, ...current.filter((saved) => saved.key !== item.key)])
}

export function removeWishlistProduct(key: string): string | null {
  const current = getSnapshot().items
  return publish(current.filter((item) => item.key !== key))
}

export function toggleWishlistProduct(product: SaveableProduct): string | null {
  const key = getWishlistProductKey(product)
  if (!key) return publishError('This product could not be saved.')
  const current = getSnapshot().items
  if (current.some((item) => item.key === key)) {
    return removeWishlistProduct(key)
  }
  return saveWishlistProduct(product)
}

export function useWishlist() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, () => EMPTY_SNAPSHOT)
  const savedKeys = new Set(snapshot.items.map((item) => item.key))

  return {
    items: snapshot.items,
    error: snapshot.error,
    isSaved: (product: SaveableProduct) => {
      const key = getWishlistProductKey(product)
      return key !== null && savedKeys.has(key)
    },
    save: saveWishlistProduct,
    remove: removeWishlistProduct,
    toggle: toggleWishlistProduct,
  }
}

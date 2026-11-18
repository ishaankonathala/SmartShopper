import { useSyncExternalStore } from 'react'
import type { AmazonCatalogueProduct } from '../types/amazonCatalogue'

export type AmazonComparisonProduct = Pick<
  AmazonCatalogueProduct,
  'asin' | 'title' | 'store' | 'category' | 'price_inr' | 'features'
> & {
  rating: number | null
  rating_count: number | null
  image_url: string | null
}

const MAX_COMPARISON_PRODUCTS = 3
const listeners = new Set<() => void>()
const EMPTY_PRODUCTS: AmazonComparisonProduct[] = []
let selectedProducts: AmazonComparisonProduct[] = []

function notifyListeners() {
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot(): AmazonComparisonProduct[] {
  return selectedProducts
}

export function addAmazonComparisonProduct(
  product: AmazonComparisonProduct,
): void {
  if (
    selectedProducts.some(
      (selected) => selected.asin.toUpperCase() === product.asin.toUpperCase(),
    ) ||
    selectedProducts.length >= MAX_COMPARISON_PRODUCTS
  ) {
    return
  }
  selectedProducts = [
    ...selectedProducts,
    {
      ...product,
      asin: product.asin.toUpperCase(),
      features: [...product.features],
    },
  ]
  notifyListeners()
}

export function toggleAmazonComparisonProduct(
  product: AmazonComparisonProduct,
): void {
  const existing = selectedProducts.find(
    (selected) => selected.asin.toUpperCase() === product.asin.toUpperCase(),
  )
  if (existing) {
    removeAmazonComparisonProduct(existing.asin)
    return
  }
  addAmazonComparisonProduct(product)
}

export function removeAmazonComparisonProduct(asin: string): void {
  const next = selectedProducts.filter(
    (product) => product.asin.toUpperCase() !== asin.toUpperCase(),
  )
  if (next.length === selectedProducts.length) return
  selectedProducts = next
  notifyListeners()
}

export function clearAmazonComparison(): void {
  if (selectedProducts.length === 0) return
  selectedProducts = []
  notifyListeners()
}

export function useAmazonComparison() {
  const products = useSyncExternalStore(
    subscribe,
    getSnapshot,
    () => EMPTY_PRODUCTS,
  )
  const selectedAsins = new Set(
    products.map((product) => product.asin.toUpperCase()),
  )

  return {
    products,
    isSelected: (asin: string) => selectedAsins.has(asin.toUpperCase()),
    add: addAmazonComparisonProduct,
    toggle: toggleAmazonComparisonProduct,
    remove: removeAmazonComparisonProduct,
    clear: clearAmazonComparison,
  }
}

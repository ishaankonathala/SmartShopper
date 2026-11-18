import { useRef, useState } from 'react'
import { DEMO_USER_ID } from '../config'
import {
  getAmazonCatalogueProduct,
  getProduct,
  recordHistory,
} from '../services/api'
import { recordAmazonProductViewed } from '../services/amazonRecentlyViewed'
import type { AssistantRecommendation } from '../types/assistant'
import type { AmazonCatalogueProduct } from '../types/amazonCatalogue'
import type { Product } from '../types/product'

type ProductDetails = Product | AmazonCatalogueProduct

export function useProductDetails() {
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null)
  const [products, setProducts] = useState<Record<string, ProductDetails>>({})
  const [loadingProductId, setLoadingProductId] = useState<string | null>(null)
  const [errorProductId, setErrorProductId] = useState<string | null>(null)
  const [historyErrorProductId, setHistoryErrorProductId] = useState<string | null>(null)
  const selectedProductIdRef = useRef<string | null>(null)

  async function toggleDetails(recommendation: AssistantRecommendation): Promise<void> {
    const { product_id: productId } = recommendation
    if (selectedProductIdRef.current === productId) {
      selectedProductIdRef.current = null
      setSelectedProductId(null)
      return
    }

    selectedProductIdRef.current = productId
    setSelectedProductId(productId)
    setErrorProductId(null)
    setHistoryErrorProductId(null)
    if (recommendation.catalogue_source === 'amazon') {
      const asin = productId.replace(/^amazon:/i, '')
      const viewed = recordAmazonProductViewed({
        asin,
        title: recommendation.name,
        store: recommendation.brand || null,
        category: recommendation.category,
        price_inr: recommendation.price,
        rating: recommendation.rating,
        rating_count: recommendation.rating_count ?? null,
        image_url: recommendation.image_url ?? '',
      })
      if (viewed.error) setHistoryErrorProductId(productId)
      if (products[productId]) return
      setLoadingProductId(productId)
      try {
        const product = await getAmazonCatalogueProduct(asin)
        setProducts((current) => ({ ...current, [productId]: product }))
      } catch {
        setErrorProductId(productId)
      } finally {
        setLoadingProductId((current) =>
          current === productId ? null : current,
        )
      }
      return
    }

    const historyRequest = recordHistory({
      user_id: DEMO_USER_ID,
      product_id: productId,
      action: 'viewed',
    }).catch(() => {
      setHistoryErrorProductId(productId)
    })
    if (products[productId]) {
      await historyRequest
      return
    }

    setLoadingProductId(productId)
    try {
      const product = await getProduct(productId)
      setProducts((current) => ({ ...current, [productId]: product }))
    } catch {
      setErrorProductId(productId)
    } finally {
      setLoadingProductId((current) =>
        current === productId ? null : current,
      )
    }
    await historyRequest
  }

  function reset(): void {
    selectedProductIdRef.current = null
    setSelectedProductId(null)
    setLoadingProductId(null)
    setErrorProductId(null)
    setHistoryErrorProductId(null)
  }

  return {
    selectedProductId,
    products,
    loadingProductId,
    errorProductId,
    historyErrorProductId,
    toggleDetails,
    reset,
  }
}

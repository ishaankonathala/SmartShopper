export type AmazonCatalogueProduct = {
  id: number
  asin: string
  title: string
  store: string | null
  category: string
  price_inr: number
  rating: number
  rating_count: number
  image_url: string
  description: string[]
  features: string[]
  source_metadata: Record<string, unknown>
  created_at: string
}

export type AmazonCataloguePage = {
  products: AmazonCatalogueProduct[]
  categories: string[]
  total: number
  limit: number
  offset: number
}

export type AmazonCatalogueFilters = {
  category?: string
  search?: string
  limit?: number
  offset?: number
}

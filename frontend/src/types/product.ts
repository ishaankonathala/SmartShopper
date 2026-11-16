export type Product = {
  id: number
  product_id: string
  name: string
  brand: string
  category: string
  price: number
  rating: number
  description: string
  attributes: Record<string, unknown>
  stock_quantity: number
  is_active: boolean
  image_url: string | null
  created_at: string
  is_available: boolean
}

export type ProductFilters = {
  category?: string
  brand?: string
  min_price?: number
  max_price?: number
  available?: boolean
  include_inactive?: boolean
}

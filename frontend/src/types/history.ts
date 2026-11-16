export type HistoryAction =
  | 'viewed'
  | 'liked'
  | 'purchased'
  | 'dismissed'
  | 'not_interested'

export type ShoppingHistory = {
  id: number
  user_id: number
  product_id: string
  product_db_id: number
  product_name: string
  action: HistoryAction
  created_at: string
}

export type ShoppingHistoryCreate = {
  user_id: number
  product_id: string
  action: HistoryAction
}

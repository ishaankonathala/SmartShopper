export type Profile = {
  id: number
  name: string
  email: string | null
  max_budget: number
  min_budget: number | null
  preferred_categories: string[]
  preferred_brands: string[]
  disliked_attributes: string[]
  created_at: string
  updated_at: string
}

export type ProfileCreate = {
  name: string
  email?: string | null
  max_budget: number
  min_budget?: number | null
  preferred_categories?: string[]
  preferred_brands?: string[]
  disliked_attributes?: string[]
}

export type ProfileUpdate = Partial<ProfileCreate>

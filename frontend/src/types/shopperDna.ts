export type PreferenceDimension =
  | 'comfort_priority'
  | 'brand_loyalty'
  | 'price_sensitivity'
  | 'quality_preference'
  | 'portability_preference'
  | 'battery_life_priority'

export type ShopperDNA = {
  id: number
  user_id: number
  inferred_preferences: Record<PreferenceDimension, number>
  confidence_scores: Record<PreferenceDimension, number>
  preference_sources: Record<PreferenceDimension, string>
  updated_at: string
}

export type ShopperDNAUpdate = {
  inferred_preferences?: Partial<Record<PreferenceDimension, number>>
  confidence_scores?: Partial<Record<PreferenceDimension, number>>
  preference_sources?: Partial<Record<PreferenceDimension, string>>
}

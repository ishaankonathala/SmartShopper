export function getDisplayedActivityCount(
  events: readonly { sequence: number }[],
  legacyActivity: readonly string[],
): number {
  return events.length > 0 ? events.length : legacyActivity.length
}

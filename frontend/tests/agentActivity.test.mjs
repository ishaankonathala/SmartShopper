import assert from 'node:assert/strict'
import test from 'node:test'
import { getDisplayedActivityCount } from '../src/utils/agentActivity.ts'

test('activity count matches all displayed events across multiple tool calls', () => {
  const events = [
    { sequence: 1 },
    { sequence: 2 },
    { sequence: 3 },
    { sequence: 4 },
    { sequence: 5 },
    { sequence: 6 },
  ]

  assert.equal(getDisplayedActivityCount(events, []), events.length)
})

test('legacy activity count is retained when event metadata is absent', () => {
  assert.equal(getDisplayedActivityCount([], ['Search', 'Evaluate']), 2)
})

// Tests for modulesDefault (2 cases), e.g. modules without an answer from the server (W8-R9); every module is on, in the same order as the module list.
import { describe, it, expect } from 'vitest'
import { MODULE_KEYS } from '../modules'
import { squareProfile } from '../squareConfig'

describe('modules without an answer from the server (W8-R9)', () => {
  it('every module is on, in the same order as the module list', () => {
    expect(squareProfile.modules).toEqual(MODULE_KEYS)
  })
})

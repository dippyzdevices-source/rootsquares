// The QR code of the staff set-up page (run: npm run test:qr): a real SVG made from an otpauth address, the same input gives the same picture, and the secret is not written into it as text.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { qrSvg } from '../admin/src/qr.ts'

const URI = 'otpauth://totp/rootsquares%20admin:ann%40example.com?secret=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ&issuer=rootsquares%20admin&digits=6&period=30'

test('an otpauth address becomes one scalable SVG', () => {
  const svg = qrSvg(URI)
  assert.match(svg, /^<svg[^>]*viewBox=/)
  assert.match(svg, /<\/svg>$/)
  assert.doesNotMatch(svg, /<script|onload|href/i)
  assert.ok(svg.length > 500, 'a QR code of this size has many squares')
})

test('the picture is the same for the same input, different for another, and holds no secret as text', () => {
  assert.equal(qrSvg(URI), qrSvg(URI))
  assert.notEqual(qrSvg(URI), qrSvg(URI.replace('GEZD', 'GEZE')))
  assert.ok(!qrSvg(URI).includes('GEZDGNBV'))
})

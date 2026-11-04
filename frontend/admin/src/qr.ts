import qrcode from 'qrcode-generator'

/** A QR code for `text` as one SVG string (scales to its box; dark squares only, no text of the data inside). Error correction M: a phone reads it from a screen. */
export function qrSvg(text: string): string {
  const qr = qrcode(0, 'M') // 0 = the smallest version that fits
  qr.addData(text)
  qr.make()
  return qr.createSvgTag({ cellSize: 4, margin: 2, scalable: true })
}

// A square's logo (W6-R53): PNG, JPEG or WebP up to 1 MB, the same limits the API enforces (SVG is refused: it can carry script).
export const LOGO_ACCEPT = 'image/png,image/jpeg,image/webp'
export const LOGO_MAX_BYTES = 1_000_000

/** null when the file can be uploaded, else why not. */
export function checkLogo(file: File): 'type' | 'size' | null {
  if (!LOGO_ACCEPT.split(',').includes(file.type)) return 'type'
  return file.size > LOGO_MAX_BYTES ? 'size' : null
}

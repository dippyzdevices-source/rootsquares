// Map links built from a free-text address — no API key, no Google JS loaded.

/** The part of an address a map can find: drops a leading "c/o <person>" line. */
export function mappableAddress(address: string): string {
  return address
    .split(',')
    .map((part) => part.trim())
    .filter((part) => part && !/^c\/o\b/i.test(part))
    .join(', ')
}

export function mapEmbedUrl(address: string): string {
  return `https://maps.google.com/maps?q=${encodeURIComponent(mappableAddress(address))}&output=embed`
}

export function mapOpenUrl(address: string): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(mappableAddress(address))}`
}

export function mapDirectionsUrl(address: string): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(mappableAddress(address))}`
}

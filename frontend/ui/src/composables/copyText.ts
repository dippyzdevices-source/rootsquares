// Copies text to the clipboard and says whether it worked. The clipboard API is only allowed on https and on localhost; a page opened by another address
// (the home network of guide 33, for example) gets the older way: a hidden field and the copy command. A failure is returned, never swallowed.
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch { /* refused: try the older way */ }
  try {
    const field = document.createElement('textarea')
    field.value = text
    field.setAttribute('readonly', '')
    field.style.position = 'fixed'
    field.style.opacity = '0'
    document.body.appendChild(field)
    field.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(field)
    return ok
  } catch {
    return false
  }
}

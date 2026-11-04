// A multi-select filter sends its ticked values comma-separated (`?status=paid,pending`); empty means no filter.
export type FilterValue = string | number | readonly (string | number)[] | undefined | null

export function listParam(value: FilterValue): string | undefined {
  if (value === undefined || value === null || value === '') return undefined
  const text = Array.isArray(value) ? value.join(',') : String(value)
  return text || undefined
}

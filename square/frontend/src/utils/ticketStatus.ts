// Ticket.status is "valid" | "used" | "void" (see backend/app/tickets/models.py — "void" is set
// only when an admin cancels an already-paid order, app/orders/admin_routes.py's
// admin_cancel_order), but this stays a plain string→string/variant mapping rather than a union
// type so an unrecognized future status still renders sensibly (falls through to the status
// string itself, default badge) instead of breaking display.

export function ticketStatusVariant(status: string): 'default' | 'success' | 'error' {
  if (status === 'used') return 'success'
  if (status === 'void') return 'error'
  return 'default'
}

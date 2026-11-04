"""The lists that are driven by `lookup_values`. Adding a list = one entry here (group + title for the
admin page, seed defaults) plus wiring its consumers to `app.lookups.service`. Defaults seed the
migration and act as a fallback while a list has no rows at all (e.g. a fresh test database)."""

# Order of the groups on the admin Lists page (each list names its group).
GROUP_ORDER = ("Content", "Finance", "People", "Ticketing", "System")

LOOKUP_LISTS: dict[str, dict] = {
    "expense_category": {
        "title": "Expense categories",
        "module": "accounting",  # exists only in a square that has the Accounting module (W8-R24)
        "group": "Finance",
        "description": "Categories offered when recording an event expense.",
        "defaults": [
            ("venue", "Venue"),
            ("food", "Food"),
            ("decoration", "Decoration"),
            ("music_entertainment", "Music / Entertainment"),
            ("equipment", "Equipment"),
            ("printing", "Printing"),
            ("transportation", "Transportation"),
            ("marketing", "Marketing"),
            ("gifts", "Gifts"),
            ("supplies", "Supplies"),
            ("other", "Other"),
        ],
    },
    "event_type": {
        "title": "Event types",
        "module": "events",
        "group": "Content",
        "description": "Types offered on events (event form, public filters and badges).",
        "defaults": [
            ("festival", "Festival"),
            ("cultural", "Cultural"),
            ("community", "Community"),
            ("other", "Other"),
        ],
    },
    "album_category": {
        "title": "Album categories",
        "module": "gallery",  # exists only in a square that has the Gallery module (W8-R17)
        "group": "Content",
        "description": "Optional category of a gallery album (admin album form and public gallery filter).",
        "defaults": [
            ("festivals", "Festivals"),
            ("cultural", "Cultural"),
            ("community", "Community"),
            ("archive", "Archive"),
        ],
    },
    "contact_reason": {
        "title": "Contact reasons",
        "group": "Content",
        "description": "What a visitor can say their message is about on the contact page (the label is sent as the email subject).",
        "defaults": [
            ("general", "General enquiry"),
        ],
    },
    "news_category": {
        "title": "News categories",
        "module": "news",  # exists only in a square that has the News module (W8-R16)
        "group": "Content",
        "description": "Optional category of a news article (admin news form and public news filter).",
        "defaults": [
            ("announcement", "Announcement"),
            ("story", "Story"),
            ("blog", "Blog"),
        ],
    },
    "task_category": {
        "title": "Volunteer task categories",
        "module": "volunteering",  # exists only in a square that has the Volunteering module (W8-R23)
        "group": "People",
        "description": "Task categories members can be assigned to on an event (Food, Cultural, ...).",
        "defaults": [
            ("food", "Food"),
            ("cultural", "Cultural"),
            ("decoration", "Decoration"),
            ("logistics", "Logistics"),
            ("registration", "Registration"),
            ("other", "Other"),
        ],
    },
    "relationship_type": {
        "title": "Family relationship types",
        "group": "People",
        "module": "members",  # exists only in a square that has the Members module (W8-R19)
        "description": "Relationship of a family member to the member (member profile and admin member page).",
        # Written by code (child memberships create a "child" family entry), so it cannot be hidden or deleted.
        "protected": ["child"],
        "defaults": [
            ("spouse", "Spouse"),
            ("child", "Child"),
            ("parent", "Parent"),
            ("other", "Other"),
        ],
    },
    "payment_status": {
        "title": "Payment statuses",
        "module": "payments",
        "group": "Finance",
        "description": "Wording of payment and order-payment statuses (the status values themselves are fixed by the system).",
        # Fixed list: the code branches on these values, so admins can only reword and reorder them.
        "fixed": True,
        "defaults": [
            ("pending", "Pending"),
            ("pending_verification", "Pending verification"),
            ("initiated", "At Vipps"),
            ("paid", "Paid"),
            ("failed", "Failed"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
            ("refunded", "Refunded"),
            ("partially_refunded", "Partially refunded"),
        ],
    },
    "payment_provider": {
        "title": "Payment methods",
        "module": "payments",
        "group": "Finance",
        "description": "Names shown for how a payment was made. Cash and Vipps-QR are approved by a person; Vipps-App is approved automatically by Vipps.",
        # Fixed list: the code branches on these values, so admins can only reword and reorder them.
        "fixed": True,
        "defaults": [
            ("cash", "Cash"),
            ("vipps_qr", "Vipps-QR"),
            ("bank_transfer", "Bank transfer"),
            ("vipps_app", "Vipps-App"),
            ("stripe", "Stripe"),
        ],
    },
    "payment_type": {
        "title": "Payment types",
        "value_modules": {"event_ticket": "tickets", "membership": "memberships", "donation": "donations"},
        "module": "payments",
        "group": "Finance",
        "description": "Names shown for what a payment was for.",
        # Fixed list: the code branches on these values, so admins can only reword and reorder them.
        "fixed": True,
        "defaults": [
            ("event_ticket", "Ticket"),
            ("membership", "Membership"),
            ("donation", "Donation"),
            ("vipps_test", "Vipps test"),
        ],
    },
    "ticket_status": {
        "title": "Ticket statuses",
        "module": "tickets",
        "group": "Ticketing",
        "description": "Wording of ticket statuses.",
        # Fixed list: the code branches on these values, so admins can only reword and reorder them.
        "fixed": True,
        "defaults": [
            ("valid", "Not checked in yet"),
            ("used", "Checked in"),
            ("void", "Cancelled"),
        ],
    },
    "membership_status": {
        "title": "Membership statuses",
        "group": "People",
        "module": "memberships",
        "description": "Wording of membership statuses.",
        # Fixed list: the code branches on these values, so admins can only reword and reorder them.
        "fixed": True,
        "defaults": [
            ("pending", "Pending"),
            ("active", "Active"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
            ("suspended", "Suspended"),
        ],
    },
    "news_status": {
        "title": "News statuses",
        "module": "news",
        "group": "Content",
        "description": "Wording of news article statuses.",
        # Fixed list: the code branches on these values, so admins can only reword and reorder them.
        "fixed": True,
        "defaults": [
            ("draft", "Draft"),
            ("published", "Published"),
            ("archived", "Archived"),
        ],
    },
    "newsletter_status": {
        "title": "Newsletter statuses",
        "module": "newsletter",  # exists only in a square that has the Newsletter module (W8-R15)
        "group": "Content",
        "description": "Wording of newsletter subscriber and issue statuses.",
        # Fixed list: the code branches on these values, so admins can only reword and reorder them.
        "fixed": True,
        "defaults": [
            ("pending", "Waiting for confirmation"),
            ("subscribed", "Subscribed"),
            ("unsubscribed", "Unsubscribed"),
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("sending", "Sending"),
            ("sent", "Sent"),
        ],
    },
    "testimonial_status": {
        "title": "Testimonial statuses",
        "group": "Content",
        "module": "testimonials",  # the list exists only in a square that has the Testimonials module (W8-R10)
        "description": "Wording of testimonial review statuses.",
        # Fixed list: the code branches on these values, so admins can only reword and reorder them.
        "fixed": True,
        "defaults": [
            ("pending", "Pending review"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
    },
    "user_role": {
        "title": "User roles",
        "group": "People",
        "value_modules": {"volunteer": "checkin"},  # the volunteer role is the door check-in role
        "description": "Names shown for account roles (what each role can do is fixed by the system).",
        # Fixed list: the code branches on these values, so admins can only reword and reorder them.
        "fixed": True,
        "defaults": [
            ("member", "Member"),
            ("volunteer", "Volunteer"),
            ("admin", "Admin"),
        ],
    },
    "ticket_age_category": {
        "title": "Ticket age categories",
        "module": "tickets",
        "group": "Ticketing",
        "description": "Names of ticket age categories (the adult/child checkout rules are fixed by the system).",
        # Fixed list: the code branches on these values, so admins can only reword and reorder them.
        "fixed": True,
        "defaults": [
            ("adult", "Adult"),
            ("child", "Child"),
            ("other", "Other"),
        ],
    },
    "audit_action": {
        "title": "Audit log actions",
        "group": "System",
        # An action of a module the owner turned off is not offered (W8-R25); old entries stay in the log.
        "value_modules": {
            "membership_status_changed": "memberships",
            "membership_drive_signup": "memberships",
            "membership_reminder_sent": "memberships",
            "membership_request_removed": "memberships",
            "members_merged": "members",
            "order_marked_paid": "tickets",
            "order_rejected": "tickets",
            "order_cancelled": "tickets",
            "ticket_type_deleted": "tickets",
            "event_created": "events",
            "event_updated": "events",
            "event_deleted": "events",
            "coupon_created": "coupons",
            "coupon_updated": "coupons",
            "gallery_album_deleted": "gallery",
            "gallery_media_deleted": "gallery",
            "news_deleted": "news",
            "payment_refunded": "payments",
            "payment_confirmed": "payments",
            "payment_rejected": "payments",
            "committee_member_deleted": "committee",
            "founder_deleted": "founders",
            "sponsor_deleted": "sponsors",
            "magazine_deleted": "magazines",
            "expense_deleted": "accounting",
            "income_deleted": "accounting",
            "newsletter_sent": "newsletter",
            "newsletter_scheduled": "newsletter",
        },
        "description": "Wording of the action types in the audit log and its filter.",
        "fixed": True,
        "defaults": [
            ("user_role_changed", "Role changed"),
            ("membership_status_changed", "Membership status changed"),
            ("order_marked_paid", "Order marked paid"),
            ("order_rejected", "Order rejected"),
            ("order_cancelled", "Order cancelled"),
            ("settings_updated", "Settings updated"),
            ("event_created", "Event created"),
            ("event_updated", "Event updated"),
            ("event_deleted", "Event deleted"),
            ("coupon_created", "Coupon created"),
            ("coupon_updated", "Coupon updated"),
            ("gallery_album_deleted", "Gallery album deleted"),
            ("gallery_media_deleted", "Gallery media deleted"),
            ("news_deleted", "News deleted"),
            ("ticket_type_deleted", "Ticket type deleted"),
            ("payment_refunded", "Payment refunded"),
            ("payment_confirmed", "Payment confirmed"),
            ("payment_rejected", "Payment rejected"),
            ("committee_member_deleted", "Committee member deleted"),
            ("founder_deleted", "Founder deleted"),
            ("sponsor_deleted", "Sponsor deleted"),
            ("magazine_deleted", "Magazine deleted"),
            ("expense_deleted", "Expense deleted"),
            ("income_deleted", "Income deleted"),
            ("lookup_value_changed", "List value changed"),
            ("membership_drive_signup", "Membership drive signup"),
            ("members_merged", "Members merged"),
            ("newsletter_sent", "Newsletter sent"),
            ("newsletter_scheduled", "Newsletter scheduled"),
            ("membership_reminder_sent", "Membership reminder sent"),
            ("membership_request_removed", "Membership request removed"),
        ],
    },
    "committee_role": {
        "title": "Committee roles",
        "module": "committee",  # the list exists only in a square that has the Committee module (W8-R12)
        "group": "People",
        "description": "Positions offered in the committee member form (the label is what is stored and shown publicly).",
        "defaults": [
            ("president", "President"),
            ("vice_president", "Vice President"),
            ("general_secretary", "General Secretary"),
            ("assistant_secretary", "Assistant Secretary"),
            ("cultural_secretary", "Cultural Secretary"),
            ("food_secretary", "Food Secretary"),
            ("food_committee", "Food Committee"),
            ("treasurer", "Treasurer"),
            ("assistant_treasurer", "Assistant Treasurer"),
            ("public_relations_officer", "Public Relations Officer"),
            ("event_coordinator", "Event Coordinator"),
            ("committee_member", "Committee Member"),
            ("media_coordinator", "Media Coordinator"),
            ("advisor", "Advisor"),
        ],
    },
}

<script setup lang="ts">
import LegalNotPublished from '../../components/ui/LegalNotPublished.vue'
// Page title/meta description come from this route's `meta` in router/index.ts. bca-oslo's own policy (its legal entity, address and Norwegian law)
// was removed in the square app (rootsquares W6-R41); the square shows who to ask until it has its own text.
</script>

<template>
  <LegalNotPublished title="Privacy Policy" what="privacy policy" field="privacy_text" />
</template>

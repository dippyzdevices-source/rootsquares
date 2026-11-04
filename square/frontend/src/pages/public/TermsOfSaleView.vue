<script setup lang="ts">
import LegalNotPublished from '../../components/ui/LegalNotPublished.vue'
// Page title/meta description come from this route's `meta` in router/index.ts. bca-oslo's own Terms of Sale (its legal entity, address, NOK and
// Norwegian law) were removed in the square app (rootsquares W6-R41); the square shows who to ask until it has its own text.
</script>

<template>
  <LegalNotPublished title="Terms of Sale" what="terms of sale" field="terms_text" />
</template>

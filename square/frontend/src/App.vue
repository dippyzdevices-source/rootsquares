<script setup lang="ts">
import BaseToastContainer from './components/ui/BaseToastContainer.vue'
import SupportBanner from './components/SupportBanner.vue'
import SleepingView from './pages/public/SleepingView.vue'
import { setBackSoonMeta } from './composables/usePageMeta'
import { squareProfile } from './services/squareConfig'

// A sleeping square (W10-R44, W17-R24) is only the back-soon page, shown in place at the address the visitor typed: no layout, header or footer, because they
// would ask the paused square for data. The router does not move the visitor anywhere (router/index.ts).
const sleeping = squareProfile.sleeping
if (sleeping) setBackSoonMeta()
</script>

<template>
  <SupportBanner />
  <SleepingView v-if="sleeping" />
  <router-view v-else />
  <BaseToastContainer />
</template>

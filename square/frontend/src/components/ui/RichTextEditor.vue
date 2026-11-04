<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { Editor, EditorContent, Node, mergeAttributes } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'

// `imageUpload` turns on the Picture button: it uploads the chosen file and returns the URL to
// embed. Without it the editor behaves exactly as before (no image node, no button).
const props = defineProps<{
  modelValue: string
  label?: string
  imageUpload?: (file: File) => Promise<string>
}>()

// Minimal block image node (src + alt) — avoids adding @tiptap/extension-image for one use.
const ImageNode = Node.create({
  name: 'image',
  group: 'block',
  atom: true,
  draggable: true,
  addAttributes() {
    return { src: { default: null }, alt: { default: null } }
  },
  parseHTML() {
    return [{ tag: 'img[src]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['img', mergeAttributes(HTMLAttributes)]
  },
})
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const editor = shallowRef<Editor>()
const linkPromptOpen = ref(false)
const linkUrl = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const uploadError = ref('')

onMounted(() => {
  editor.value = new Editor({
    content: props.modelValue,
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3] },
        link: { openOnClick: false, autolink: true },
      }),
      ...(props.imageUpload ? [ImageNode] : []),
    ],
    onUpdate: ({ editor: instance }) => {
      emit('update:modelValue', instance.getHTML())
    },
  })
})

watch(
  () => props.modelValue,
  (value) => {
    if (editor.value && value !== editor.value.getHTML()) {
      editor.value.commands.setContent(value, { emitUpdate: false })
    }
  },
)

onBeforeUnmount(() => {
  editor.value?.destroy()
})

async function handlePictureChosen(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !props.imageUpload) return
  uploadError.value = ''
  uploading.value = true
  try {
    const src = await props.imageUpload(file)
    editor.value?.chain().focus().insertContent({ type: 'image', attrs: { src } }).run()
  } catch (err) {
    uploadError.value = err instanceof Error ? err.message : 'Could not upload this picture.'
  } finally {
    uploading.value = false
  }
}

function openLinkPrompt() {
  linkUrl.value = editor.value?.getAttributes('link').href ?? ''
  linkPromptOpen.value = true
}

function applyLink() {
  if (linkUrl.value.trim()) {
    editor.value?.chain().focus().extendMarkRange('link').setLink({ href: linkUrl.value.trim() }).run()
  } else {
    editor.value?.chain().focus().extendMarkRange('link').unsetLink().run()
  }
  linkPromptOpen.value = false
}
</script>

<template>
  <div>
    <span v-if="label" class="ds-field-label">{{ label }}</span>
    <div class="rounded-md border border-border bg-surface">
      <div class="flex flex-wrap items-center gap-1 border-b border-border p-2">
        <button
          type="button"
          class="rounded px-2 py-1 text-sm font-bold text-text hover:bg-primary/10"
          :class="{ 'bg-primary/20 text-primary': editor?.isActive('bold') }"
          @click="editor?.chain().focus().toggleBold().run()"
        >
          B
        </button>
        <button
          type="button"
          class="rounded px-2 py-1 text-sm italic text-text hover:bg-primary/10"
          :class="{ 'bg-primary/20 text-primary': editor?.isActive('italic') }"
          @click="editor?.chain().focus().toggleItalic().run()"
        >
          I
        </button>
        <button
          type="button"
          class="rounded px-2 py-1 text-sm font-semibold text-text hover:bg-primary/10"
          :class="{ 'bg-primary/20 text-primary': editor?.isActive('heading', { level: 2 }) }"
          @click="editor?.chain().focus().toggleHeading({ level: 2 }).run()"
        >
          H2
        </button>
        <button
          type="button"
          class="rounded px-2 py-1 text-sm font-semibold text-text hover:bg-primary/10"
          :class="{ 'bg-primary/20 text-primary': editor?.isActive('heading', { level: 3 }) }"
          @click="editor?.chain().focus().toggleHeading({ level: 3 }).run()"
        >
          H3
        </button>
        <button
          type="button"
          class="rounded px-2 py-1 text-sm text-text hover:bg-primary/10"
          :class="{ 'bg-primary/20 text-primary': editor?.isActive('bulletList') }"
          @click="editor?.chain().focus().toggleBulletList().run()"
        >
          • List
        </button>
        <button
          type="button"
          class="rounded px-2 py-1 text-sm text-text hover:bg-primary/10"
          :class="{ 'bg-primary/20 text-primary': editor?.isActive('orderedList') }"
          @click="editor?.chain().focus().toggleOrderedList().run()"
        >
          1. List
        </button>
        <button
          type="button"
          class="rounded px-2 py-1 text-sm text-text hover:bg-primary/10"
          :class="{ 'bg-primary/20 text-primary': editor?.isActive('link') }"
          @click="openLinkPrompt"
        >
          Link
        </button>
        <template v-if="imageUpload">
          <button
            type="button"
            class="picture-button rounded px-2 py-1 text-sm text-text hover:bg-primary/10"
            :disabled="uploading"
            @click="fileInput?.click()"
          >
            {{ uploading ? 'Uploading…' : 'Picture' }}
          </button>
          <input ref="fileInput" type="file" accept="image/*" class="picture-input hidden" @change="handlePictureChosen" />
        </template>
      </div>
      <p v-if="uploadError" class="border-b border-border px-3 py-1 text-sm text-error">{{ uploadError }}</p>

      <div v-if="linkPromptOpen" class="flex items-center gap-2 border-b border-border p-2">
        <input
          v-model="linkUrl"
          type="text"
          placeholder="https://example.com (blank to remove)"
          class="flex-1 rounded-md border border-border bg-surface px-2 py-1 text-sm text-text focus:border-primary focus:outline-none"
          @keyup.enter="applyLink"
        />
        <button type="button" class="text-sm text-primary hover:underline" @click="applyLink">
          Apply
        </button>
        <button type="button" class="text-sm text-text-secondary hover:underline" @click="linkPromptOpen = false">
          Cancel
        </button>
      </div>

      <EditorContent :editor="editor" class="rich-text-content px-3 py-2 text-sm text-text" />
    </div>
  </div>
</template>

<style scoped>
.rich-text-content :deep(.tiptap) {
  min-height: 8rem;
  outline: none;
}
.rich-text-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 0.375rem;
  margin: 0.5rem 0;
}
.rich-text-content :deep(h2) {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0.75rem 0 0.25rem;
}
.rich-text-content :deep(h3) {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0.75rem 0 0.25rem;
}
.rich-text-content :deep(p) {
  margin: 0.5rem 0;
}
.rich-text-content :deep(ul),
.rich-text-content :deep(ol) {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}
.rich-text-content :deep(ul) {
  list-style: disc;
}
.rich-text-content :deep(ol) {
  list-style: decimal;
}
.rich-text-content :deep(a) {
  color: var(--color-primary);
  text-decoration: underline;
}
</style>

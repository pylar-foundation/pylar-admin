<script setup lang="ts">
import { computed } from 'vue'
import hljs from 'highlight.js/lib/core'
import json from 'highlight.js/lib/languages/json'
import python from 'highlight.js/lib/languages/python'
import plaintext from 'highlight.js/lib/languages/plaintext'
import 'highlight.js/styles/github-dark.css'

// Register only the languages we use. Each call is idempotent.
hljs.registerLanguage('json', json)
hljs.registerLanguage('python', python)
hljs.registerLanguage('plaintext', plaintext)

const props = withDefaults(
  defineProps<{
    content: string
    language?: string
    maxHeight?: string
  }>(),
  {
    language: 'plaintext',
    maxHeight: '50vh',
  },
)

/**
 * Highlight the whole blob, then split the highlighted HTML into
 * visual lines we can number. ``auto-detect`` is deliberately not
 * used — we pass the explicit language or fall back to plaintext
 * so error traces and JSON both render predictably.
 */
const lines = computed<string[]>(() => {
  const lang = hljs.getLanguage(props.language) ? props.language : 'plaintext'
  const highlighted = hljs.highlight(props.content ?? '', { language: lang }).value
  // highlight.js returns a single string; splitting on \n keeps
  // already-balanced <span> tags scoped to each line because the
  // library closes them at the boundary.
  return highlighted.split('\n')
})
</script>

<template>
  <pre class="code-block" :style="{ maxHeight }"><code
  ><span
    v-for="(line, idx) in lines"
    :key="idx"
    class="line"
  ><span class="lineno">{{ idx + 1 }}</span><span class="linetext" v-html="line || ' '" /></span></code></pre>
</template>

<style scoped>
.code-block {
  margin: 0;
  padding: 0;
  border-radius: 8px;
  background: #0d1117;
  color: #c9d1d9;
  overflow: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8rem;
  line-height: 1.5;
  border: 1px solid var(--border);
}

.code-block code {
  display: block;
  padding: 0.75rem 0;
}

.line {
  display: flex;
  white-space: pre;
  padding: 0 1rem 0 0;
}

.line:hover {
  background: rgba(255, 255, 255, 0.03);
}

.lineno {
  flex: 0 0 auto;
  padding: 0 1rem 0 0.75rem;
  text-align: right;
  min-width: 3rem;
  color: #6e7681;
  user-select: none;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  margin-right: 1rem;
}

.linetext {
  flex: 1 1 auto;
  min-width: 0;
}
</style>

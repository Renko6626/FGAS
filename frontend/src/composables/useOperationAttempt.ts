import {computed, onBeforeUnmount, ref, shallowRef} from 'vue'

interface AttemptOptions<Attempt, Current> {
  submit: (attempt: Attempt) => Promise<unknown>
  readCurrent: (attempt: Attempt) => Promise<Current>
  isDefinitiveConflict: (error: unknown) => boolean
  describeError: (error: unknown) => string
  onPendingChange?: (pending: boolean) => void
  onCurrent?: (current: Current) => void
  onResolved: (resolution: 'submitted' | 'acknowledged') => void | Promise<void>
}

// One component owns one JSON request snapshot. No global queue or reload persistence.
export function useOperationAttempt<Attempt, Current>(options: AttemptOptions<Attempt, Current>) {
  const attempt = shallowRef<Attempt | null>(null)
  const busy = ref(false)
  const error = ref('')
  const conflict = ref(false)
  const currentRecord = shallowRef<Current | null>(null)
  const pending = computed(() => attempt.value !== null)
  let disposed = false
  onBeforeUnmount(() => { disposed = true })

  function clear() {
    attempt.value = null
    conflict.value = false
    currentRecord.value = null
    options.onPendingChange?.(false)
  }

  function handleFailure(cause: unknown) {
    conflict.value = options.isDefinitiveConflict(cause)
    error.value = conflict.value
      ? (cause as Error).message + '。这次尝试未提交，请读取当前记录后核对处理。'
      : options.describeError(cause)
    if ([400, 422].includes((cause as {status?: number}).status || 0)) {
      clear()
      error.value = (cause as Error).message + '。请修正输入后提交。'
    }
  }

  async function retry() {
    if (disposed || busy.value || !attempt.value) return
    busy.value = true
    error.value = ''
    conflict.value = false
    currentRecord.value = null
    try {
      try {
        await options.submit(attempt.value)
      } catch (cause) {
        if (!disposed) handleFailure(cause)
        return
      }
      if (disposed) return
      clear()
      // Refresh failure must not be interpreted as failure of the committed write.
      await options.onResolved('submitted')
    } finally {
      busy.value = false
    }
  }

  async function start(prepare: () => Attempt) {
    if (disposed || busy.value) return
    if (!attempt.value) {
      try {
        // Copy nested IDs, keys, versions and display data before any asynchronous work.
        attempt.value = JSON.parse(JSON.stringify(prepare())) as Attempt
        options.onPendingChange?.(true)
      } catch (cause) {
        error.value = (cause as Error).message
        return
      }
    }
    await retry()
  }

  async function readCurrent() {
    if (disposed || busy.value || !attempt.value || !conflict.value) return
    busy.value = true
    currentRecord.value = null
    try {
      const result = await options.readCurrent(attempt.value)
      if (disposed) return
      currentRecord.value = result
      options.onCurrent?.(result)
    } catch (cause) {
      if (!disposed) error.value = (cause as Error).message + '。读取失败，原请求仍保留。'
    } finally {
      busy.value = false
    }
  }

  async function acknowledgeConflict() {
    if (disposed || busy.value || !attempt.value || !conflict.value || !currentRecord.value) return
    options.onCurrent?.(currentRecord.value)
    clear()
    await options.onResolved('acknowledged')
  }

  return {
    attempt, pending, busy, error, conflict, currentRecord,
    start, retry, readCurrent, acknowledgeConflict,
    isActive: () => !disposed
  }
}

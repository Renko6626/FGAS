import { computed, onBeforeUnmount, ref, watch } from "vue";
import { fundsApi } from "../api/funds";
import { statuses } from "../presentation/funds";
export function useFundTransferOptions(selected: () => string[], prependSelected = false) {
  const results = ref<{
    label: string;
    value: string;
  }[]>([]);
  const cache = ref<Record<string, string>>({});
  const loading = ref(false);
  let timer: number | undefined;
  let requestSequence = 0;
  function search(query: string) {
    const sequence = ++requestSequence;
    window.clearTimeout(timer);
    loading.value = true;
    timer = window.setTimeout(async () => {
      loading.value = true;
      try {
        const result = await fundsApi.transfers({ q: query.trim() || undefined, limit: 20 });
        if (sequence !== requestSequence) return;
        results.value = result.items.map(item => {
          const label = `${item.description || "资金单"} ${item.code}（${statuses[item.status] || item.status}）`;
          cache.value[item.code] = label;
          return { label, value: item.code };
        });
      }
      catch {
        if (sequence === requestSequence) results.value = [];
      }
      finally {
        if (sequence === requestSequence) loading.value = false;
      }
    }, 200);
  }
  const options = computed(() => {
    const values = [...results.value];
    for (const id of selected()) {
      if (values.some(option => option.value === id))
        continue;
      const option = { label: cache.value[id] || id, value: id };
      if (prependSelected)
        values.unshift(option);
      else
        values.push(option);
    }
    return values;
  });
  watch(() => [...selected()], (value, previous) => {
    if (value.length === 0 && previous.length > 0) {
      ++requestSequence;
      window.clearTimeout(timer);
      results.value = [];
      loading.value = false;
    }
  }, { flush: "sync" });
  onBeforeUnmount(() => {
    ++requestSequence;
    window.clearTimeout(timer);
  });
  return { options, loading, search };
}

import { computed, onBeforeUnmount, ref } from "vue";
import { fundsApi, statuses } from "../api/funds";
export function useFundTransferOptions(selected: () => string[], prependSelected = false) {
  const results = ref<{
    label: string;
    value: string;
  }[]>([]);
  const cache = ref<Record<string, string>>({});
  const loading = ref(false);
  let timer: number | undefined;
  function search(query: string) {
    window.clearTimeout(timer);
    timer = window.setTimeout(async () => {
      loading.value = true;
      try {
        const result = await fundsApi.transfers({ q: query.trim() || undefined, limit: 20 });
        results.value = result.items.map(item => {
          const label = `${item.description || item.id}（${statuses[item.status] || item.status}）`;
          cache.value[item.id] = label;
          return { label, value: item.id };
        });
      }
      catch {
        results.value = [];
      }
      finally {
        loading.value = false;
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
  onBeforeUnmount(() => window.clearTimeout(timer));
  return { options, loading, search };
}

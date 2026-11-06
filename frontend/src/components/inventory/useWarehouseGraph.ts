import { computed, onBeforeUnmount, onMounted, ref, watch, type ComputedRef } from "vue";

interface GraphBounds { x: number; y: number; width: number; height: number }

export function useWarehouseGraph(bounds: ComputedRef<GraphBounds>) {
  const viewport = ref<HTMLElement | null>(null);
  const size = ref({ width: 0, height: 0 });
  const scale = ref(1);
  const offset = ref({ x: 0, y: 0 });
  const dragging = ref(false);
  const fitScale = computed(() => Math.min(1, Math.max(1, size.value.width - 32) / bounds.value.width,
    Math.max(1, size.value.height - 32) / bounds.value.height));
  const minScale = computed(() => Math.min(0.25, fitScale.value));
  const transform = computed(() => `translate(${offset.value.x}px, ${offset.value.y}px) scale(${scale.value})`);
  const percentage = computed(() => Math.round(scale.value * 100));

  function fit() {
    if (!size.value.width || !size.value.height) return;
    scale.value = fitScale.value;
    offset.value = {
      x: (size.value.width - bounds.value.width * scale.value) / 2 - bounds.value.x * scale.value,
      y: (size.value.height - bounds.value.height * scale.value) / 2 - bounds.value.y * scale.value,
    };
  }

  function zoom(factor: number, x = size.value.width / 2, y = size.value.height / 2) {
    const next = Math.max(minScale.value, Math.min(2, scale.value * factor));
    const ratio = next / scale.value;
    offset.value = { x: x - (x - offset.value.x) * ratio, y: y - (y - offset.value.y) * ratio };
    scale.value = next;
  }

  function wheel(event: WheelEvent) {
    const element = viewport.value;
    if (!element) return;
    const rect = element.getBoundingClientRect();
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? size.value.height : 1;
    const delta = Math.max(-100, Math.min(100, event.deltaY * unit));
    zoom(Math.exp(-delta * 0.002), event.clientX - rect.left - element.clientLeft, event.clientY - rect.top - element.clientTop);
  }

  let pointer: { id: number; x: number; y: number; offsetX: number; offsetY: number } | undefined;
  let suppressClick = false;
  function pointerDown(event: PointerEvent) {
    if (!event.isPrimary || event.button !== 0) return;
    suppressClick = false;
    pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, offsetX: offset.value.x, offsetY: offset.value.y };
  }
  function pointerMove(event: PointerEvent) {
    if (!pointer || pointer.id !== event.pointerId) return;
    const dx = event.clientX - pointer.x, dy = event.clientY - pointer.y;
    if (!dragging.value && Math.hypot(dx, dy) < 5) return;
    if (!dragging.value) viewport.value?.setPointerCapture(event.pointerId);
    dragging.value = true;
    suppressClick = true;
    offset.value = { x: pointer.offsetX + dx, y: pointer.offsetY + dy };
    event.preventDefault();
  }
  function pointerEnd(event: PointerEvent) {
    if (!pointer || pointer.id !== event.pointerId) return;
    pointer = undefined;
    dragging.value = false;
    if (viewport.value?.hasPointerCapture(event.pointerId)) viewport.value.releasePointerCapture(event.pointerId);
  }
  function pointerLeave(event: PointerEvent) {
    if (!dragging.value) pointerEnd(event);
  }
  function click(event: MouseEvent) {
    if (!suppressClick || event.detail === 0) return;
    event.preventDefault();
    event.stopPropagation();
    suppressClick = false;
  }
  function keydown(event: KeyboardEvent) {
    if (event.target !== event.currentTarget) return;
    const directions: Record<string, [number, number]> = { ArrowLeft: [40, 0], ArrowRight: [-40, 0], ArrowUp: [0, 40], ArrowDown: [0, -40] };
    const direction = directions[event.key];
    if (direction) offset.value = { x: offset.value.x + direction[0], y: offset.value.y + direction[1] };
    else if (event.key === "+" || event.key === "=") zoom(1.2);
    else if (event.key === "-") zoom(1 / 1.2);
    else if (event.key === "0" || event.key === "Home") fit();
    else return;
    event.preventDefault();
  }

  let observer: ResizeObserver | undefined;
  onMounted(() => {
    observer = new ResizeObserver(() => {
      const element = viewport.value;
      if (!element) return;
      size.value = { width: element.clientWidth, height: element.clientHeight };
      fit();
    });
    if (viewport.value) observer.observe(viewport.value);
  });
  watch(viewport, (element, previous) => {
    if (previous) observer?.unobserve(previous);
    pointer = undefined;
    dragging.value = false;
    suppressClick = false;
    if (element) observer?.observe(element);
  });
  watch(() => `${bounds.value.x}:${bounds.value.y}:${bounds.value.width}:${bounds.value.height}`, fit);
  onBeforeUnmount(() => observer?.disconnect());

  return { viewport, scale, minScale, percentage, transform, dragging, fit, zoom, wheel,
    pointerDown, pointerMove, pointerEnd, pointerLeave, click, keydown };
}

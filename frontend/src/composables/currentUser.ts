import { ref } from "vue";
import type { User } from "../api/auth";

export const currentUser = ref<User | null>(null);

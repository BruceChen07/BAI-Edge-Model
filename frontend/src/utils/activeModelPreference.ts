const ACTIVE_MODEL_STORAGE_KEY = "bai-edge-model.active-model";

export function saveActiveModelPreference(modelName?: string): void {
  if (typeof window === "undefined") {
    return;
  }
  if (!modelName) {
    window.localStorage.removeItem(ACTIVE_MODEL_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(ACTIVE_MODEL_STORAGE_KEY, modelName);
}

export function loadActiveModelPreference(): string | undefined {
  if (typeof window === "undefined") {
    return undefined;
  }
  const value = window.localStorage.getItem(ACTIVE_MODEL_STORAGE_KEY)?.trim();
  return value || undefined;
}

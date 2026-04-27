class MemoryStorage implements Storage {
  private readonly items = new Map<string, string>();

  get length() {
    return this.items.size;
  }

  clear() {
    this.items.clear();
  }

  getItem(key: string) {
    return this.items.get(key) ?? null;
  }

  key(index: number) {
    return [...this.items.keys()][index] ?? null;
  }

  removeItem(key: string) {
    this.items.delete(key);
  }

  setItem(key: string, value: string) {
    this.items.set(key, value);
  }
}

function installStorage(name: "localStorage" | "sessionStorage") {
  const current = globalThis[name] as Storage | undefined;
  if (
    current &&
    typeof current.clear === "function" &&
    typeof current.getItem === "function" &&
    typeof current.setItem === "function"
  ) {
    return;
  }

  Object.defineProperty(globalThis, name, {
    value: new MemoryStorage(),
    configurable: true,
    writable: true,
  });
}

installStorage("localStorage");
installStorage("sessionStorage");

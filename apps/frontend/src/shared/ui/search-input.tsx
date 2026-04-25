import { Search } from "lucide-react";

interface SearchInputProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

export function SearchInput({ value, onChange, placeholder = "search…" }: SearchInputProps) {
  return (
    <div className="relative flex items-center">
      <Search
        size={12}
        className="pointer-events-none absolute left-2 text-muted"
        aria-hidden="true"
      />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded border border-border bg-bg-2 py-1 pl-6 pr-2 text-[11px] text-text placeholder:text-muted-2 focus:border-border-strong focus:outline-none"
      />
    </div>
  );
}

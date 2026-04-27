import { useCallback } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

export function useUrlState<T extends string>(
  key: T,
): [string | null, (next: string | null) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const value = searchParams.get(key);

  const setValue = useCallback(
    (next: string | null) => {
      setSearchParams(
        (current) => {
          const params = new URLSearchParams(current);
          if (next == null || next === "") params.delete(key);
          else params.set(key, next);
          return params;
        },
        { replace: true },
      );
    },
    [key, setSearchParams],
  );

  return [value, setValue];
}

export function useUrlList(key: string, sep = ","): [string[], (next: string[]) => void] {
  const [raw, setRaw] = useUrlState(key);
  const values = raw == null || raw === "" ? [] : raw.split(sep).filter((part) => part.length > 0);

  const setValues = useCallback(
    (next: string[]) => {
      setRaw(next.length > 0 ? next.join(sep) : null);
    },
    [sep, setRaw],
  );

  return [values, setValues];
}

export function useUrlHash(): [string, (next: string) => void] {
  const location = useLocation();
  const navigate = useNavigate();

  const setHash = useCallback(
    (next: string) => {
      navigate(
        {
          pathname: location.pathname,
          search: location.search,
          hash: next.startsWith("#") ? next.slice(1) : next,
        },
        { replace: true },
      );
    },
    [location.pathname, location.search, navigate],
  );

  return [location.hash, setHash];
}

import { useCallback, useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";

export function useParameterDrawer(): {
  paramPath: string | null;
  stepIndex: number | null;
  open: (paramPath: string, step?: number) => void;
  close: () => void;
  selectStep: (step: number) => void;
} {
  const location = useLocation();
  const navigate = useNavigate();
  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const paramPath = params.get("param");
  const stepRaw = params.get("step");
  const parsedStep = stepRaw == null ? null : Number(stepRaw);
  const stepIndex = Number.isInteger(parsedStep) ? parsedStep : null;

  const navigateWith = useCallback(
    (mutate: (next: URLSearchParams) => void) => {
      const next = new URLSearchParams(location.search);
      mutate(next);
      navigate({
        pathname: location.pathname,
        search: next.toString(),
        hash: location.hash,
      });
    },
    [location.hash, location.pathname, location.search, navigate],
  );

  return {
    paramPath,
    stepIndex,
    open: (nextParamPath, step) =>
      navigateWith((next) => {
        next.set("param", nextParamPath);
        if (step != null) next.set("step", String(step));
        else next.delete("step");
      }),
    close: () =>
      navigateWith((next) => {
        next.delete("param");
        next.delete("step");
      }),
    selectStep: (step) =>
      navigateWith((next) => {
        next.set("step", String(step));
      }),
  };
}

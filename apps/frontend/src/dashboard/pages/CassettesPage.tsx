import { CassetteList } from "@/components/panels/cassette-list";
import { dashboardApi } from "@/lib/api/dashboard";
import type { CassetteDeterminismResponse } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

export function CassettesPage() {
  const navigate = useNavigate();
  const [replayingPath, setReplayingPath] = useState<string | null>(null);
  const [checkingPath, setCheckingPath] = useState<string | null>(null);
  const [determinismByPath, setDeterminismByPath] = useState<
    Record<string, CassetteDeterminismResponse | undefined>
  >({});

  const cassettes = useQuery({
    queryKey: ["cassettes"] as const,
    queryFn: () => dashboardApi.cassettes(),
  });

  const onReplay = (path: string) => {
    setReplayingPath(path);
    void dashboardApi
      .cassetteReplay({ path, delayMs: 50 })
      .then((res) => navigate(`/runs/${res.run_id}`))
      .finally(() => setReplayingPath(null));
  };

  const onDeterminism = (path: string) => {
    setCheckingPath(path);
    void dashboardApi
      .cassetteDeterminism(path)
      .then((res) => {
        setDeterminismByPath((prev) => ({ ...prev, [path]: res }));
      })
      .finally(() => setCheckingPath(null));
  };

  if (cassettes.isLoading) return <div className="p-4 text-xs text-muted">loading cassettes…</div>;

  return (
    <CassetteList
      items={cassettes.data ?? []}
      replayingPath={replayingPath}
      checkingPath={checkingPath}
      determinismByPath={determinismByPath}
      onReplay={onReplay}
      onDeterminism={onDeterminism}
      onRefresh={() => {
        void cassettes.refetch();
      }}
    />
  );
}

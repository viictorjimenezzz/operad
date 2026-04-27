import { useUrlHash, useUrlList, useUrlState } from "@/hooks/use-url-state";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

function Probe() {
  const [sort, setSort] = useUrlState("sort");
  const [cols, setCols] = useUrlList("cols");
  const [hash, setHash] = useUrlHash();
  const location = useLocation();
  return (
    <div>
      <div>sort={sort ?? ""}</div>
      <div>cols={cols.join("|")}</div>
      <div>hash={hash}</div>
      <div>url={location.pathname + location.search + location.hash}</div>
      <button type="button" onClick={() => setSort("latency,desc")}>
        set sort
      </button>
      <button type="button" onClick={() => setCols(["run", "tokens"])}>
        set cols
      </button>
      <button type="button" onClick={() => setHash("#section=identity")}>
        set hash
      </button>
      <button type="button" onClick={() => setSort(null)}>
        clear sort
      </button>
    </div>
  );
}

describe("use-url-state hooks", () => {
  it("round-trips table params and section hash", () => {
    render(
      <MemoryRouter initialEntries={["/runs?sort=run,asc&cols=run,state#section=backend"]}>
        <Probe />
      </MemoryRouter>,
    );

    expect(screen.getByText("sort=run,asc")).toBeTruthy();
    expect(screen.getByText("cols=run|state")).toBeTruthy();
    expect(screen.getByText("hash=#section=backend")).toBeTruthy();

    fireEvent.click(screen.getByText("set sort"));
    fireEvent.click(screen.getByText("set cols"));
    fireEvent.click(screen.getByText("set hash"));

    expect(screen.getByText("sort=latency,desc")).toBeTruthy();
    expect(screen.getByText("cols=run|tokens")).toBeTruthy();
    expect(screen.getByText("hash=#section=identity")).toBeTruthy();

    fireEvent.click(screen.getByText("clear sort"));
    expect(screen.getByText("sort=")).toBeTruthy();
  });
});

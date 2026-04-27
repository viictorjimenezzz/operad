import { MarkdownView } from "@/components/ui/markdown";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

describe("MarkdownView", () => {
  it("renders common markdown nodes", () => {
    const { container } = render(
      <MarkdownView value={"# Title\n\n- item\n\n`code`\n\n[link](https://example.com)"} />,
    );

    expect(container.querySelector("h1")?.textContent).toBe("Title");
    expect(container.querySelector("li")?.textContent).toBe("item");
    expect(container.querySelector("code")?.textContent).toBe("code");
    expect(container.querySelector("a")?.getAttribute("href")).toBe("https://example.com");
  });

  it("saves edited markdown through the injected callback", async () => {
    const save = vi.fn(async () => undefined);
    render(<MarkdownView value="old" onSave={save} />);

    fireEvent.click(screen.getByLabelText("edit markdown"));
    fireEvent.change(screen.getByLabelText("markdown text"), { target: { value: "## New" } });
    fireEvent.click(screen.getByText("Preview"));
    expect(screen.getByText("New")).toBeTruthy();
    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => expect(save).toHaveBeenCalledWith("## New"));
  });

  it("shows pending state while save is in flight", () => {
    let resolveSave: () => void = () => {};
    const save = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveSave = resolve;
        }),
    );
    render(<MarkdownView value="old" onSave={save} />);

    fireEvent.click(screen.getByLabelText("edit markdown"));
    fireEvent.click(screen.getByText("Save"));
    const saveButton = screen.getByText("Save").closest("button");
    expect(saveButton?.disabled).toBe(true);
    resolveSave?.();
  });
});

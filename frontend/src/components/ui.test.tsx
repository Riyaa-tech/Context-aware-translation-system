import { render, screen } from "@testing-library/react";
import { Value, DecisionBadge } from "./ui";

test("Value renders 'unavailable' distinctly", () => {
  render(<Value v="unavailable" />);
  expect(screen.getByTitle("Not measured yet").textContent).toBe("unavailable");
});

test("Decision badge carries a text label, not colour alone", () => {
  render(<DecisionBadge d="ABSTAIN" />);
  expect(screen.getByText(/Abstained/)).toBeTruthy();
});

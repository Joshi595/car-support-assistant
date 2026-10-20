import { expect, test } from "@playwright/test";
import { ANSWER, mockApi } from "./mock";

test("answers stream in and citations open the source passage", async ({ page }) => {
  const calls = await mockApi(page, ANSWER);
  await page.goto("/");
  await page.getByRole("button", { name: "How long is the battery warranty?" }).click();

  await expect(page.getByText("8 years or 100,000 miles", { exact: true }).first()).toBeVisible();
  expect(calls[0]).toMatchObject({ path: "/v1/chat", body: { market: "uk", message: "How long is the battery warranty?" } });

  await page.getByRole("button", { name: "Source 1" }).click();
  await expect(page.getByText("Duration: 8 years or 100,000 miles, whichever comes first.")).toBeVisible();
  await expect(page.getByText("Northwind documentation")).toBeVisible();
});

test("an unhelpful answer offers a person, and the handoff is confirmed", async ({ page }) => {
  const calls = await mockApi(page, ANSWER);
  await page.goto("/");
  await page.getByLabel("Your question").fill("How long is the battery warranty?");
  await page.getByRole("button", { name: "Send" }).click();
  await page.getByRole("button", { name: "No" }).click();

  await page.getByRole("button", { name: "Talk to a person" }).click();
  await expect(page.getByText("A colleague will pick this up.")).toBeVisible();
  expect(calls.map((c) => c.path)).toEqual(["/v1/chat", "/v1/feedback", "/v1/handoff"]);
  expect(calls[1].body).toMatchObject({ message_id: 7, rating: -1 });
  expect(calls[2].body).toMatchObject({ reason: "negative_feedback" });
});

test("a refusal offers a person straight away", async ({ page }) => {
  await mockApi(page, { message_id: 8, answer: "I couldn't find that.", outcome: "refuse", sources: [], offer_handoff: true }, "");
  await page.goto("/");
  await page.getByLabel("Your question").fill("What is the drag coefficient?");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Talk to a person" })).toBeVisible();
});

test("changing the market starts a new conversation with local suggestions", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your market").selectOption("de");
  await expect(page.getByRole("button", { name: "Was kostet die Wallbox?" })).toBeVisible();
});

test("the agent desk requires sign-in", async ({ page }) => {
  await page.goto("/agent");
  await expect(page).toHaveURL(/\/agent\/signin/);
  await expect(page.getByText("No sign-in method is configured.")).toBeVisible();
});

import { expect, test } from "@playwright/test";

test.describe("login smoke", () => {
  test("login page loads with brand and form", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "etolegko" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
    await expect(page.getByLabel("Username")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("successful login with mocked API lands on companies", async ({
    page,
  }) => {
    // Mock only backend origin — never intercept Next.js page navigations.
    await page.route("http://127.0.0.1:8000/**", async (route) => {
      const url = route.request().url();
      const method = route.request().method();
      if (url.includes("/auth/login") && method === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            access_token: "e2e-test-token",
            token_type: "bearer",
          }),
        });
        return;
      }
      if (url.includes("/companies") && method === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: [],
            page: 1,
            page_size: 20,
            total: 0,
          }),
        });
        return;
      }
      await route.fulfill({ status: 404, body: "unmocked" });
    });

    await page.goto("/login");
    await page.getByLabel("Username").fill("admin");
    await page.getByLabel("Password").fill("changeme");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/http:\/\/127\.0\.0\.1:\d+\/companies/);
    await expect(
      page.getByRole("heading", { name: "Companies" }),
    ).toBeVisible();
  });

  test("failed login shows error from mocked API", async ({ page }) => {
    await page.route("http://127.0.0.1:8000/**", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({
          error: "unauthorized",
          message: "Invalid credentials.",
        }),
      });
    });

    await page.goto("/login");
    await page.getByLabel("Username").fill("admin");
    await page.getByLabel("Password").fill("wrong");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(
      page.getByRole("main").getByText("Invalid credentials."),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });
});

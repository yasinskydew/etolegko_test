import { expect, test, type Page, type Route } from "@playwright/test";

const company = {
  id: 2,
  name: "test_yasinsky_company_e2e",
  lifecycle: "ready",
  traffic_status: "active",
  geo_codes: ["MX"],
  streams: [
    { id: 1, type: "google", position: 1, offers: [] },
    {
      id: 2,
      type: "offers",
      position: 2,
          offers: [
        {
          offer_id: 3749,
          name: "Offer A",
          percent: 100,
          pinned: false,
          removed: false,
          position: 1,
        },
      ],
    },
  ],
  drift: {
    campaign_missing: false,
    offers: false,
    geo: false,
    traffic: false,
    streams: false,
  },
  reconcile_unavailable: false,
};

async function mockApi(page: Page) {
  let traffic = company.traffic_status;

  await page.route("http://127.0.0.1:8000/**", async (route: Route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.includes("/auth/login") && method === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "e2e-test-token",
          type: "bearer",
          token_type: "bearer",
        }),
      });
      return;
    }

    if (url.match(/\/companies\/2\/enable$/) && method === "POST") {
      traffic = "active";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...company, traffic_status: traffic }),
      });
      return;
    }

    if (url.match(/\/companies\/2\/disable$/) && method === "POST") {
      traffic = "disabled";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...company, traffic_status: traffic }),
      });
      return;
    }

    if (url.match(/\/companies\/2\/stats/) && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ clicks: 1, uniques: 1, bots: 0 }),
      });
      return;
    }

    if (url.match(/\/companies\/2$/) && method === "PUT") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...company, traffic_status: traffic }),
      });
      return;
    }

    if (url.match(/\/companies\/2(\?|$)/) && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...company, traffic_status: traffic }),
      });
      return;
    }

    if (url.includes("/offers") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [] }),
      });
      return;
    }

    await route.fulfill({ status: 404, body: `unmocked ${method} ${url}` });
  });
}

async function seedAuth(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("etolegko:jwt", "e2e-test-token");
  });
}

test.describe("company view / edit (mocked API)", () => {
  test("view page shows company and toggles traffic without version body", async ({
    page,
  }) => {
    await mockApi(page);
    await seedAuth(page);
    await page.goto("/companies/2");

    await expect(
      page.getByRole("heading", { name: "test_yasinsky_company_e2e" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("link", { name: "Edit" })).toBeVisible();
    await expect(page.getByText("Offer A")).toBeVisible();

    // Chakra Switch.HiddenInput exposes the checkbox control.
    await page.getByLabel("Traffic status").click({ force: true });
    await expect(page.getByText("Disabled", { exact: true })).toBeVisible({
      timeout: 10_000,
    });
  });

  test("edit page loads and streams path redirects to edit", async ({
    page,
  }) => {
    await mockApi(page);
    await seedAuth(page);

    await page.goto("/companies/2/streams");
    await expect(page).toHaveURL(/\/companies\/2\/edit/);
    await expect(page.getByRole("button", { name: "Push to KT" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Cancel" })).toBeVisible();
  });
});

import { test, expect, type Page } from "@playwright/test";

test("approval card executes through explicit controls", async ({ page }) => {
  let approvalDecision = "";
  await page.route("**/api/chat", (route) => route.fulfill({ json: {
    request_id: "req-approval", conversation_id: "conv-approval", message_id: "msg-approval",
    answer: "This action is prepared for human approval before any external write operation.", intent: "tool_action",
    kpis: [], chart_spec: { type: "none", title: "", x_key: null, y_keys: [], rows: [] },
    insights: [], recommendations: [], forecast: null, sources: [], requires_approval: true,
    suggested_questions: ["Show sales performance", "Search company documents", "Generate a forecast"], error: null,
    tool_calls: [{ tool_name: "create_calendar_event", status: "proposed", arguments: {
      meeting_title: "Final review of the project before submission", attendee: "zahsan2006@gmail.com",
      date: "Today", time: "5:00 PM", start: "2026-09-05T17:00:00+05:00", end: "2026-09-05T18:00:00+05:00"
    }}]
  }}));
  await page.route("**/api/chat/msg-approval/approval", async (route) => {
    approvalDecision = route.request().postDataJSON().decision;
    await route.fulfill({ json: { tool_name: "create_calendar_event", status: "executed", arguments: {} } });
  });
  await page.goto("/");
  await page.getByLabel("Ask anything about your business").fill("Schedule the final review");
  await page.getByLabel("Send message").click();
  const card = page.getByLabel("Approval required");
  await expect(card).toContainText("Final review of the project before submission");
  await expect(card).toContainText("zahsan2006@gmail.com");
  await expect(page.getByText("Show sales performance")).toHaveCount(0);
  await expect(page.locator(".assistant-message.is-approval .assistant-identity")).toHaveCount(0);
  await card.getByRole("button", { name: "Create Event" }).click();
  expect(approvalDecision).toBe("approve");
  await expect(card).toContainText("Created");
  await expect(card.getByRole("button", { name: "Create Event" })).toHaveCount(0);
});

test("email approval card renders and sends through Gmail action", async ({ page }) => {
  let decision = "";
  await page.route("**/api/chat", (route) => route.fulfill({ json: {
    request_id: "email-request", conversation_id: "email-conversation", message_id: "email-message",
    answer: "This action is prepared for human approval before any external write operation.", intent: "tool_action",
    kpis: [], chart_spec: { type: "none", title: "", x_key: null, y_keys: [], rows: [] }, insights: [],
    recommendations: [], forecast: null, sources: [], requires_approval: true, suggested_questions: [], error: null,
    tool_calls: [{ tool_name: "send_email", status: "proposed", arguments: { to: "zahsan2006@gmail.com",
      subject: "Final Project Review Meeting", message: "Please attend the final review at 5:00 PM today." } }]
  }}));
  await page.route("**/api/chat/email-message/approval", async (route) => {
    decision = route.request().postDataJSON().decision;
    await route.fulfill({ json: { tool_name: "send_email", status: "executed", arguments: {} } });
  });
  await page.goto("/");
  await page.getByLabel("Ask anything about your business").fill("Send the email");
  await page.getByLabel("Send message").click();
  const card = page.getByLabel("Approval required");
  await expect(card).toContainText("Review the proposed email before sending.");
  await expect(card).toContainText("Final Project Review Meeting");
  await expect(card).toContainText("5:00 PM today");
  await card.getByRole("button", { name: "Send Email" }).click();
  expect(decision).toBe("approve");
  await expect(card).toContainText("Status: Sent");
});

test("history table opens a saved conversation and continues it", async ({ page }) => {
  let continuedConversation = "";
  await page.route("**/api/chat/conversations", (route) => route.fulfill({ json: [{
    id: "conv-saved", title: "Quarterly sales review", updated_at: "2026-09-05T12:00:00Z", message_count: 2
  }] }));
  await page.route("**/api/chat/conversations/conv-saved", (route) => route.fulfill({ json: {
    id: "conv-saved", title: "Quarterly sales review", messages: [
      { id: "user-1", role: "user", content: "Show quarterly sales", created_at: "2026-09-05T11:59:00Z" },
      { id: "assistant-1", role: "assistant", content: "Quarterly sales increased.", created_at: "2026-09-05T12:00:00Z" }
    ]
  }}));
  await page.route("**/api/chat", async (route) => {
    continuedConversation = route.request().postDataJSON().conversation_id;
    await route.fulfill({ json: {
      request_id: "continued", conversation_id: "conv-saved", message_id: "assistant-2",
      answer: "Here is the follow-up.", intent: "general_chat", kpis: [],
      chart_spec: { type: "none", title: "", x_key: null, y_keys: [], rows: [] }, insights: [],
      recommendations: [], forecast: null, sources: [], tool_calls: [], requires_approval: false,
      suggested_questions: [], error: null
    }});
  });
  await page.goto("/history");
  await expect(page.getByRole("table")).toContainText("Quarterly sales review");
  await page.getByRole("button", { name: "Quarterly sales review" }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByText("Show quarterly sales")).toBeVisible();
  await expect(page.getByText("Quarterly sales increased.")).toBeVisible();
  await page.getByLabel("Ask anything about your business").fill("Break it down by region");
  await page.getByLabel("Send message").click();
  expect(continuedConversation).toBe("conv-saved");
});

test("voice dictation fills the composer and auto-send uses normal chat routing", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator,"mediaDevices",{value:{getUserMedia:async()=>({getTracks:()=>[{stop(){}}]})}});
    class FakeRecorder {
      static isTypeSupported(){return true} state="inactive"; mimeType="audio/webm";
      ondataavailable:((event:{data:Blob})=>void)|null=null; onstop:(()=>void)|null=null;
      constructor(_stream:unknown,_options:unknown){}
      start(){this.state="recording"}
      stop(){this.state="inactive";this.ondataavailable?.({data:new Blob(["voice"],{type:this.mimeType})});this.onstop?.()}
    }
    Object.defineProperty(window,"MediaRecorder",{value:FakeRecorder});
  });
  let chatBody:Record<string,unknown>|null=null;
  await page.route("**/api/voice/transcribe",route=>route.fulfill({json:{text:"show last month's sales"}}));
  await page.route("**/api/chat",async route=>{chatBody=route.request().postDataJSON();await route.fulfill({json:{
    request_id:"voice",conversation_id:"voice-conversation",message_id:"voice-answer",answer:"Sales increased.",intent:"analytics",
    kpis:[],chart_spec:{type:"none",title:"",x_key:null,y_keys:[],rows:[]},insights:[],recommendations:[],forecast:null,
    sources:[],tool_calls:[],requires_approval:false,suggested_questions:[],error:null
  }})});
  await page.goto("/");
  await page.getByRole("button",{name:"Start voice input"}).click();
  await page.getByRole("button",{name:"Stop listening"}).click();
  await expect(page.getByLabel("Ask anything about your business")).toHaveValue("show last month's sales");
  expect(chatBody).toBeNull();
  await page.evaluate(()=>{localStorage.setItem("business-agent.voice-preferences",JSON.stringify({commands:true,wakePhrase:false,replies:false,autoSend:true}));window.dispatchEvent(new Event("voice-preferences"))});
  await page.getByRole("button",{name:"Start voice input"}).click();
  await page.getByRole("button",{name:"Stop listening"}).click();
  await expect(page.getByText("Sales increased.")).toBeVisible();
  expect(chatBody).toMatchObject({query_text:"show last month's sales",voice_mode:true});
});

async function noPageScroll(page: Page) {
  expect(
    await page.evaluate(() => ({
      height: document.documentElement.scrollHeight,
      width: document.documentElement.scrollWidth,
      viewport: innerHeight,
      viewportWidth: innerWidth,
    })),
  ).toEqual({ height: 900, width: 1440, viewport: 900, viewportWidth: 1440 });
  expect(
    await page
      .locator(".workspace-page")
      .evaluate((el) => el.scrollHeight <= el.clientHeight),
  ).toBe(true);
}
async function documentsApi(page: Page, populated = false) {
  let folders = populated
    ? Array.from({ length: 28 }, (_, index) => ({
        folder_id: `folder-${index}`,
        name: `Folder ${index}`,
        document_count: 0,
      }))
    : [];
  let files = populated
    ? Array.from({ length: 40 }, (_, index) => ({
        id: `file-${index}`,
        filename: `Report ${index}.pdf`,
        mime_type: "application/pdf",
        size: 1234,
        folder_id: null,
        created_at: "2026-09-05T10:00:00",
        updated_at: "2026-09-05T10:00:00",
      }))
    : [];
  const uploads: string[] = [];
  await page.route("**/api/documents**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    const method = request.method();
    if (path.endsWith("/upload")) {
      uploads.push(path);
      await new Promise((resolve) => setTimeout(resolve, 350));
      const folder = path.match(/folders\/([^/]+)\/upload/)?.[1] ?? null;
      files.push({
        id: "uploaded",
        filename: "policy.txt",
        mime_type: "text/plain",
        size: 12,
        folder_id: folder,
        created_at: "2026-09-05T10:00:00",
        updated_at: "2026-09-05T10:00:00",
      } as any);
      folders = folders.map((item) => ({
        ...item,
        document_count: files.filter(
          (file) => file.folder_id === item.folder_id,
        ).length,
      }));
      return route.fulfill({ json: { document_id: "uploaded" } });
    }
    if (path.endsWith("/folders")) {
      if (method === "POST") {
        const folder = {
          folder_id: "finance",
          name: request.postDataJSON().name,
          document_count: 0,
        };
        folders.push(folder);
        return route.fulfill({ json: folder });
      }
      return route.fulfill({ json: folders });
    }
    if (path.includes("/folders/")) {
      const id = path.split("/").pop();
      if (method === "DELETE")
        folders = folders.filter((folder) => folder.folder_id !== id);
      if (method === "PATCH")
        folders = folders.map((folder) =>
          folder.folder_id === id
            ? { ...folder, name: request.postDataJSON().name }
            : folder,
        );
      return route.fulfill({ json: { ok: true } });
    }
    return route.fulfill({ json: files });
  });
  return uploads;
}
async function integrationsApi(page: Page, initial = false) {
  let connected = initial;
  const statuses = () =>
    ["google-calendar", "gmail"].map((provider) => ({
      provider,
      name: provider === "gmail" ? "Gmail" : "Google Calendar",
      description: "Business connection",
      configured: initial,
      account:
        connected && provider === "google-calendar" ? "user@example.com" : null,
      state:
        connected && provider === "google-calendar"
          ? "connected"
          : "not_connected",
    }));
  await page.route("**/api/integrations**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/connect"))
      return route.fulfill({
        status: 503,
        json: { detail: "Google OAuth is not configured." },
      });
    if (path.endsWith("/disconnect")) {
      connected = false;
      return route.fulfill({ json: statuses()[0] });
    }
    if (path.endsWith("/events"))
      return route.fulfill({
        json: [
          {
            id: "meeting",
            title: "Business meeting",
            start: "2026-09-05T10:00:00",
            end: "2026-09-05T11:00:00",
            attendees: ["Ahsan", "Sarah"],
            location: "Boardroom A",
          },
          {
            id: "late",
            title: "Late call",
            start: "2026-09-05T21:00:00",
            end: "2026-09-05T22:00:00",
          },
          {
            id: "all",
            title: "Planning day",
            start: "2026-09-05",
            end: "2026-09-06",
          },
        ],
      });
    return route.fulfill({ json: statuses() });
  });
}

test("documents empty state, native upload and no zero statistics", async ({
  page,
}) => {
  const uploads = await documentsApi(page);
  await page.goto("/documents");
  await expect(
    page.getByRole("heading", { name: "No documents yet" }),
  ).toBeVisible();
  await expect(page.locator(".documents-page__categories small")).toHaveCount(
    0,
  );
  await expect(page.getByRole("button", { name: "PDFs" })).toHaveCount(0);
  await noPageScroll(page);
  const chooser = page.waitForEvent("filechooser");
  await page
    .getByRole("button", { name: "Upload document", exact: true })
    .first()
    .click();
  await (
    await chooser
  ).setFiles({
    name: "policy.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Hello policy"),
  });
  await expect(page.locator(".workspace-page__notice")).toContainText(/Uploading|Processing/);
  await expect(page.locator(".documents-page__card")).toContainText(
    "policy.txt",
  );
  expect(uploads).toEqual(["/api/documents/upload"]);
  await expect(page.locator(".workspace-page__notice")).toContainText("Uploaded policy.txt");
});

test("backend folder create, rename, upload targeting and deletion confirmation", async ({
  page,
}) => {
  const uploads = await documentsApi(page);
  await page.goto("/documents");
  await page
    .getByRole("button", { name: "Create folder", exact: true })
    .click();
  await page.getByRole("textbox", { name: "Folder name" }).fill("Finance");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByLabel("Actions for folder Finance", { exact: true }).click();
  await page.getByRole("button", { name: "Rename", exact: true }).click();
  await page.getByRole("textbox", { name: "Folder name" }).fill("Reports");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByLabel("Actions for folder Reports", { exact: true }).click();
  await page
    .getByRole("button", { name: "Delete folder", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("0 documents");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.locator(".documents-page__folder-nav > button").click();
  await expect(page.locator(".documents-page__breadcrumb")).toContainText(
    "Reports",
  );
  const chooser = page.waitForEvent("filechooser");
  await page
    .getByRole("button", { name: "Upload document", exact: true })
    .first()
    .click();
  await (
    await chooser
  ).setFiles({
    name: "policy.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Hello policy"),
  });
  await expect(page.locator(".workspace-page__notice")).toContainText("Uploaded");
  expect(uploads.at(-1)).toEqual("/api/documents/folders/finance/upload");
  await page.getByLabel("Actions for folder Reports", { exact: true }).click();
  await page
    .getByRole("button", { name: "Delete folder", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Delete", exact: true }),
  ).toBeDisabled();
});

test("empty folder can be deleted only after confirmation", async ({
  page,
}) => {
  await documentsApi(page);
  await page.goto("/documents");
  await page
    .getByRole("button", { name: "Create folder", exact: true })
    .click();
  await page.getByRole("textbox", { name: "Folder name" }).fill("Finance");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByLabel("Actions for folder Finance", { exact: true }).click();
  await page
    .getByRole("button", { name: "Delete folder", exact: true })
    .click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.locator(".documents-page__folder-nav")).toHaveCount(0);
});

test("documents search, view switching and independent scrolling", async ({
  page,
}) => {
  await documentsApi(page, true);
  await page.goto("/documents");
  await expect(page.locator(".documents-page__card")).toHaveCount(68);
  await noPageScroll(page);
  for (const selector of [
    ".documents-page__results",
    ".documents-page__categories",
  ]) {
    expect(
      await page
        .locator(selector)
        .evaluate((el) => el.scrollHeight > el.clientHeight),
    ).toBe(true);
    expect(
      await page.locator(selector).evaluate((el) => {
        el.scrollTop = 100;
        return el.scrollTop;
      }),
    ).toBeGreaterThan(0);
  }
  await page
    .getByRole("textbox", { name: "Search documents" })
    .fill("Report 39");
  await expect(page.locator(".documents-page__card")).toHaveCount(1);
  await page.getByRole("button", { name: "List view", exact: true }).click();
  await expect(page.locator(".documents-page__list")).toBeVisible();
  await expect(page.getByRole("combobox")).toHaveCount(0);
});

test("calendar requires a connection and does not fake successful OAuth", async ({
  page,
}) => {
  await integrationsApi(page);
  await page.goto("/calendar");
  await expect(
    page.getByRole("heading", { name: "Connect Google Calendar" }),
  ).toBeVisible();
  await expect(page.locator(".calendar-page__time-grid")).toHaveCount(0);
  await noPageScroll(page);
  await page
    .getByRole("button", { name: "Connect Google Calendar", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("not configured");
  await page
    .getByRole("button", { name: "Manage connections", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Connections", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Not connected", { exact: true })).toHaveCount(2);
});

test("connected Day/Week calendar fits, shows events and current time; disconnect updates Calendar", async ({
  page,
}) => {
  await page.clock.setFixedTime(new Date("2026-09-05T10:30:00"));
  await integrationsApi(page, true);
  await page.goto("/calendar");
  await expect(
    page.getByRole("button", { name: /Business meeting/ }),
  ).toBeVisible();
  await expect(page.getByLabel(/^Current time/)).toBeVisible();
  await noPageScroll(page);
  await page.getByRole("button", { name: /Business meeting/ }).click();
  await expect(page.getByRole("dialog")).toContainText("Boardroom A");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".calendar-page__time-column")).toHaveCount(1);
  await noPageScroll(page);
  await page
    .getByRole("button", { name: "Open connections", exact: true })
    .click();
  await page.getByRole("button", { name: "Google Calendar options" }).click();
  await page.getByRole("button", { name: "Disconnect", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Disconnect", exact: true })
    .click();
  await expect(page.getByText("Not connected", { exact: true })).toHaveCount(2);
  await page
    .getByRole("button", { name: "Open calendar", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Connect Google Calendar" }),
  ).toBeVisible();
});

test("home, history, orb canvas and star position survive workspace navigation", async ({
  page,
}) => {
  await documentsApi(page);
  await integrationsApi(page);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.locator(".hero-heading")).toBeVisible();
  const before = await page
    .getByRole("button", { name: "Start new chat" })
    .boundingBox();
  await page.locator(".spline-orb").evaluate((el) => {
    (el as any).regressionMarker = "same-canvas";
  });
  for (const label of [
    "Open documents",
    "Open calendar",
    "Open connections",
    "Open chat history",
  ]) {
    await page.getByRole("button", { name: label, exact: true }).click();
    expect(
      await page.getByRole("button", { name: "Start new chat" }).boundingBox(),
    ).toEqual(before);
    expect(
      await page
        .locator(".spline-orb")
        .evaluate((el) => (el as any).regressionMarker),
    ).toBe("same-canvas");
  }
  await expect(
    page.getByRole("heading", { name: "Chat History" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Start new chat" }).click();
  await expect(page.locator(".hero-heading")).toBeVisible();
  expect(errors).toEqual([]);
});

test("mobile workspace pages keep their outer viewport stationary", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await documentsApi(page, true);
  await integrationsApi(page, true);
  for (const route of ["/documents", "/calendar", "/connections"]) {
    await page.goto(route);
    await expect(page.locator(".workspace-page")).toBeVisible();
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <= innerWidth &&
          document.documentElement.scrollHeight <= innerHeight,
      ),
    ).toBe(true);
    expect(
      await page
        .locator(".workspace-page")
        .evaluate(
          (el) =>
            el.scrollHeight <= el.clientHeight &&
            el.scrollWidth <= el.clientWidth,
        ),
    ).toBe(true);
  }
});


test('folder menu upload targets that folder and failures stay visible', async ({ page }) => {
  const uploads = await documentsApi(page);
  await page.goto('/documents');
  await page.getByRole('button', { name: 'Create folder', exact: true }).click();
  await page.getByRole('textbox', { name: 'Folder name' }).fill('Finance');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByLabel('Actions for folder Finance', { exact: true }).click();
  const chooser = page.waitForEvent('filechooser');
  await page.locator('.workspace-menu__items').getByRole('button', { name: 'Upload document' }).click();
  await (await chooser).setFiles({ name: 'policy.txt', mimeType: 'text/plain', buffer: Buffer.from('Hello policy') });
  await expect(page.locator('.workspace-page__notice')).toContainText('Uploaded');
  expect(uploads).toEqual(['/api/documents/folders/finance/upload']);
  await page.route('**/api/documents/upload', route => route.fulfill({ status: 422, json: { detail: 'Could not process this file.' } }));
  const secondChooser = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Upload document', exact: true }).first().click();
  await (await secondChooser).setFiles({ name: 'bad.pdf', mimeType: 'application/pdf', buffer: Buffer.from('invalid') });
  await expect(page.getByRole('alert')).toContainText('Could not process this file.');
});

test('short laptop calendar fits; all-day and late events remain accessible', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-09-05T10:30:00'));
  await page.setViewportSize({ width: 1280, height: 720 });
  await integrationsApi(page, true); await page.goto('/calendar');
  await page.getByRole('button', { name: '2 all-day / outside hours', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('Planning day');
  await expect(page.getByRole('dialog')).toContainText('Late call');
  await page.keyboard.press('Escape');
  const grid = await page.locator('.calendar-page__time-grid').boundingBox();
  expect(grid!.y + grid!.height).toBeLessThanOrEqual(720);
  expect(await page.locator('.workspace-page').evaluate(el => el.scrollHeight <= el.clientHeight)).toBe(true);
  expect((await page.locator('.calendar-page__event strong').first().boundingBox())!.height).toBeGreaterThan(12);
  await page.screenshot({ path: '../.tmp/revision-check/calendar-day.png' });
});

test('primary pages remain contained at required responsive widths', async ({ page }) => {
  await documentsApi(page); await integrationsApi(page, true);
  for (const width of [1920, 1440, 1280, 1024, 768]) {
    await page.setViewportSize({ width, height: width === 768 ? 900 : 800 });
    for (const route of ['/history', '/documents', '/calendar', '/connections']) {
      await page.goto(route);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight)).toBe(true);
    }
  }
});


"""Optional browser smoke test: pip install playwright && playwright install chromium."""

import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("FLOWCAST_URL", "http://127.0.0.1:8000")
OUTPUT = Path("test-results")
OUTPUT.mkdir(exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel=os.environ.get("FLOWCAST_BROWSER", "chromium"))
    page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
    page.emulate_media(reduced_motion="reduce")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(BASE_URL)
    expect(page.get_by_role("heading", name="Find your space.")).to_be_visible()
    expect(page.locator(".location-card")).to_have_count(8)
    expect(page.locator(".live-pill")).to_contain_text("Live")
    page.evaluate("document.fonts.ready")
    page.screenshot(path=str(OUTPUT / "desktop.png"), full_page=True)

    page.get_by_role("button", name="Save Wells Library", exact=True).click()
    page.get_by_role("button", name="Saved spaces", exact=False).first.click()
    expect(page.locator(".location-card")).to_have_count(1)
    page.reload()
    page.get_by_role("button", name="Saved spaces", exact=False).first.click()
    expect(page.locator(".location-card")).to_have_count(1)
    page.get_by_role("button", name="Overview", exact=True).click()
    page.get_by_role("textbox", name="Search spaces").fill("Roastery")
    expect(page.locator(".location-card")).to_have_count(1)
    page.get_by_role("button", name="Clear search").click()
    page.get_by_role("button", name="Fitness", exact=True).click()
    expect(page.locator(".location-card")).to_have_count(2)
    page.get_by_role("button", name="All spaces", exact=True).click()
    page.get_by_role("button", name="Wells Library", exact=True).click()
    dialog = page.get_by_role("dialog", name="Wells Library")
    expect(dialog).to_be_visible()
    expect(dialog.locator(".forecast-chart")).to_be_visible()
    dialog.get_by_role("button", name="Check in here", exact=True).click()
    expect(dialog.get_by_role("button", name="Check out", exact=True)).to_be_visible()
    dialog.get_by_role("button", name="Crowd alerts", exact=True).click()
    expect(dialog.get_by_role("button", name="Alerts on", exact=True)).to_be_visible()
    page.screenshot(path=str(OUTPUT / "forecast-detail.png"))
    dialog.get_by_role("button", name="Check out", exact=True).click()
    expect(dialog.get_by_role("button", name="Check in here", exact=True)).to_be_visible()
    dialog.get_by_role("button", name="View on campus map", exact=True).click()
    expect(page.locator(".campus-map")).to_be_visible()
    expect(page.locator(".map-marker.highlighted")).to_contain_text("Wells Library")
    page.get_by_role("button", name="Forecasts", exact=True).click()
    expect(page.locator(".forecast-table tbody tr")).to_have_count(8)
    page.get_by_role("button", name="1 hr", exact=True).click()
    expect(page.get_by_role("columnheader", name="In 60 min")).to_be_visible()
    page.get_by_role("button", name="How it works", exact=False).click()
    expect(page.get_by_role("dialog", name="About FlowCast")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).to_have_count(0)
    if os.environ.get("FLOWCAST_TEST_API_KEY"):
        # Exercise the complete protected-ingestion → Redis → WebSocket → browser alert path.
        original = page.request.get(BASE_URL + "/api/overview").json()
        original_count = next(item["occupancy"] for item in original["locations"] if item["id"] == "library")
        sensor_headers = {"X-API-Key": os.environ["FLOWCAST_TEST_API_KEY"]}
        response = page.request.post(BASE_URL + "/api/ingest/library", headers=sensor_headers, data={"occupancy": 230})
        assert response.ok
        expect(page.get_by_role("status")).to_contain_text("Wells Library is getting crowded.")
        response = page.request.post(BASE_URL + "/api/ingest/library", headers=sensor_headers, data={"occupancy": 20})
        assert response.ok
        expect(page.get_by_role("status")).to_contain_text("Wells Library is quiet now.")
        page.request.post(BASE_URL + "/api/ingest/library", headers=sensor_headers, data={"occupancy": original_count})
    page.get_by_role("button", name="Overview", exact=True).click()
    page.get_by_role("button", name="Find a quiet space", exact=True).click()
    expect(page.locator(".active-filter")).to_contain_text("Quiet spaces only")
    assert (
        page.locator(".location-card .badge").all_text_contents() == ["Quiet"] * page.locator(".location-card").count()
    )

    mobile = browser.new_page(
        viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True
    )
    mobile.emulate_media(reduced_motion="reduce")
    mobile.on("pageerror", lambda error: errors.append(str(error)))
    mobile.goto(BASE_URL)
    expect(mobile.locator(".location-card")).to_have_count(8)
    mobile.evaluate("document.fonts.ready")
    assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
        "Mobile page overflows horizontally"
    )
    mobile.screenshot(path=str(OUTPUT / "mobile.png"), full_page=True)
    mobile.get_by_role("button", name="Wells Library", exact=True).click()
    expect(mobile.get_by_role("dialog", name="Wells Library")).to_be_visible()
    mobile.screenshot(path=str(OUTPUT / "mobile-detail.png"))
    mobile.get_by_role("button", name="Close dialog").click()
    mobile.get_by_role("button", name="Campus map", exact=True).click()
    expect(mobile.locator(".map-marker")).to_have_count(8)
    mobile.screenshot(path=str(OUTPUT / "mobile-map.png"))
    assert not errors, errors
    browser.close()
    print(
        "Browser smoke passed: desktop, mobile, saved spaces, search, filters, forecasts, check-in/out, alerts, and map."
    )

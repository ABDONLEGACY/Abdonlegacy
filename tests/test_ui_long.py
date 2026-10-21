"""Big-project browser test: 800 short scenes, 800 media files, paged tables, >1500-scene warning.

usage: python tests/make_long_sample.py LONG_FOLDER 800
       python tests/test_ui_long.py LONG_FOLDER
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
LONG = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/long800")
TMP = Path(os.environ.get("SF_TEST_TMP", "/tmp/claude-0/sf_ui_long"))
SHOTS = TMP / "shots"
PORT = 7862


def start_app():
    shutil.rmtree(TMP, ignore_errors=True)
    SHOTS.mkdir(parents=True)
    env = dict(os.environ, SCENEFORGE_PROJECTS=str(TMP / "projects"),
               SCENEFORGE_TEST_TRANSCRIPT=str(LONG / "fake_transcript.json"))
    code = "import sys, app; app.free_port = lambda preferred=7860: %d; sys.argv.append('--no-browser'); app.main()" % PORT
    proc = subprocess.Popen([sys.executable, "-c", code], cwd=str(ROOT), env=env,
                            stdout=open(TMP / "app.log", "w"), stderr=subprocess.STDOUT)
    for _ in range(60):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/meta", timeout=2)
            return proc
        except Exception:
            continue
    raise RuntimeError("app did not start: " + (TMP / "app.log").read_text())


def timed(label, fn):
    t = time.time()
    fn()
    print(f"  {label}: {time.time() - t:.2f}s")


def new_project(page, name):
    page.locator("#side-new").click()
    page.locator("#np-name").fill(name)
    page.get_by_role("button", name="Create & Open Project").click()
    expect(page.locator("#title-input")).to_have_value(name)


def main():
    proc = start_app()
    errors = []
    try:
        with sync_playwright() as pw:
            exe = os.environ.get("SF_CHROMIUM", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
            browser = pw.chromium.launch(executable_path=exe if Path(exe).exists() else None)
            page = browser.new_page(viewport={"width": 1500, "height": 950})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{PORT}/")

            # ---- more than 1500 scenes: a warning you can click past
            new_project(page, "Huge script")
            page.locator("#voice-drop input").set_input_files(str(LONG / "voice.mp3"))
            expect(page.locator("#voice-box .fileitem")).to_have_count(1, timeout=60000)
            huge = "\n".join(f"Scene {i}: word{i} here." for i in range(1, 1601))
            page.get_by_role("button", name="or paste the script text instead").click()
            page.locator("#script-text").fill(huge)
            page.locator("#sync-btn").click()
            expect(page.get_by_text("more than 1500")).to_be_visible(timeout=15000)
            page.screenshot(path=str(SHOTS / "1_over_1500_warning.png"))
            page.locator("#cf-ok").click()  # Continue anyway
            expect(page.locator("#script-box")).to_contain_text("1600", timeout=20000)
            print("over-1500 warning: shown and clicked past ok")

            # ---- the real 800-scene project
            new_project(page, "Documentary 800")
            timed("upload 20-min voice-over", lambda: (
                page.locator("#voice-drop input").set_input_files(str(LONG / "voice.mp3")),
                expect(page.locator("#voice-box .fileitem")).to_have_count(1, timeout=60000)))
            page.locator("#script-drop input").set_input_files(str(LONG / "script.txt"))
            expect(page.locator("#script-box")).to_contain_text("800 scenes found", timeout=15000)
            page.locator("#expected").fill("800")
            timed("save script + sync 800 scenes", lambda: (
                page.locator("#sync-btn").click(),
                expect(page.get_by_text("Mapped scenes")).to_be_visible(timeout=120000)))
            expect(page.locator("#right-pane .scene-item")).to_have_count(100)
            assert "0 need checking" in page.locator("#right-pane .stats").inner_text().replace("\n", " ")
            page.screenshot(path=str(SHOTS / "2_mapped_800.png"))

            # step 2 table: paged, go to scene
            page.locator(".stepper .step").nth(1).click()
            expect(page.locator("table.t tbody tr")).to_have_count(100, timeout=15000)
            timed("step 2: next page", lambda: (page.locator("[data-pg='1']").first.click(),
                                                 expect(page.locator("table.t tbody tr").first).to_contain_text("101")))
            page.locator(".goto").first.fill("777")
            timed("step 2: go to scene 777", lambda: (page.locator(".goto").first.press("Enter"),
                                                       expect(page.locator("tr[data-row='777']")).to_be_visible()))

            # step 3: upload 800 files in batches
            page.get_by_role("button", name="Continue to Media").click()
            files = sorted(str(p) for p in (LONG / "media").iterdir())
            timed("upload + match 800 media files", lambda: (
                page.locator("#media-drop input").set_input_files(files),
                expect(page.locator("#m-count")).to_contain_text("all 800 scenes have media", timeout=300000)))
            expect(page.locator("#m-grid .mcard")).to_have_count(100)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(SHOTS / "3_media_800.png"))

            # step 4 review: paged, go to, nudge on a later page
            page.get_by_role("button", name="Continue to Review").click()
            expect(page.locator("table.t tbody tr")).to_have_count(100, timeout=20000)
            page.locator(".s4-bar .goto").fill("650")
            timed("review: go to scene 650", lambda: (page.locator(".s4-bar .goto").press("Enter"),
                                                       expect(page.locator("tr[data-row='650']")).to_be_visible()))
            row = page.locator("tr[data-row='650']")
            before = row.locator("td").nth(2).inner_text()
            timed("review: nudge scene 650 (+0.1 s)", lambda: (
                row.locator("button[data-d='0.1']").click(),
                expect(page.locator("tr[data-row='650']")).to_contain_text("moved by you")))
            after = page.locator("tr[data-row='650']").locator("td").nth(2).inner_text()
            assert before != after, (before, after)
            page.locator(".s4-bar [data-f='edited']").click()
            expect(page.locator("table.t tbody tr")).to_have_count(1)
            page.screenshot(path=str(SHOTS / "4_review_800.png"))
            ms = page.evaluate("""() => { const t = performance.now(); document.querySelector('.s4-bar [data-f="all"]').click();
                                     return performance.now() - t; }""")
            print(f"  review: redraw a page of 100 rows: {ms:.0f} ms")
            assert ms < 1500

            # step 5: start the real render, watch progress, stop it
            page.get_by_role("button", name="Continue to Export").click()
            page.locator("#render-btn").click()
            expect(page.locator("#render-progress .progress")).to_be_visible(timeout=60000)
            expect(page.locator("#render-progress")).to_contain_text("left", timeout=180000)
            page.screenshot(path=str(SHOTS / "5_render_progress.png"))
            print("  render progress:", page.locator("#render-progress .help").inner_text())
            page.locator("#stop-btn").click()
            expect(page.locator("#render-btn")).to_be_visible(timeout=60000)
            print("render started and stopped ok")
            browser.close()
    finally:
        proc.terminate()
        proc.wait()
    log = (TMP / "app.log").read_text()
    if "Traceback" in log:
        print(log[-3000:])
        raise SystemExit("errors in app log")
    if errors:
        raise SystemExit(f"JavaScript errors: {errors}")
    print("LONG UI TEST PASSED")


if __name__ == "__main__":
    main()

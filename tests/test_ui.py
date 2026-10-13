"""Stage 6: click through the whole studio in a real (headless) browser, like a user would.

Needs: pip install playwright (Chromium). The voiceover transcript is replaced by the sample's prepared
transcript (SCENEFORGE_TEST_TRANSCRIPT), because the speech model is not downloaded on the test machine.

usage: python tests/test_ui.py SAMPLE_FOLDER
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/sample")
TMP = Path(os.environ.get("SF_TEST_TMP", "/tmp/claude-0/sf_ui"))
SHOTS = TMP / "shots"
PORT = 7861


def start_app():
    shutil.rmtree(TMP, ignore_errors=True)
    SHOTS.mkdir(parents=True)
    env = dict(os.environ, SCENEFORGE_PROJECTS=str(TMP / "projects"),
               SCENEFORGE_TEST_TRANSCRIPT=str(SAMPLE / "fake_transcript.json"))
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


def shot(page, name, full=False):
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=full)


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
            expect(page.get_by_text("Welcome to SceneForge")).to_be_visible()
            shot(page, "0_welcome")

            # New project modal
            page.locator("#side-new").click()
            expect(page.get_by_text("Create New Project")).to_be_visible()
            page.locator("#np-name").fill("Why Ancient Temples Have No Windows")
            page.locator("#np-tpl .tpl").nth(1).click()
            shot(page, "1_new_project")
            page.get_by_role("button", name="Create & Open Project").click()
            expect(page.locator("#title-input")).to_have_value("Why Ancient Temples Have No Windows")
            expect(page.get_by_text("Your mapped scenes will appear here")).to_be_visible()
            shot(page, "2_step1_empty")
            print("project created ok")

            # Step 1: voice (two parts picked in the 'wrong' order) + script
            page.locator("#voice-drop input").set_input_files([str(SAMPLE / "voice_part2.wav"), str(SAMPLE / "voice_part1.wav")])
            expect(page.locator("#voice-box .fileitem").first).to_contain_text("voice_part1", timeout=30000)
            page.locator("#script-drop input").set_input_files(str(SAMPLE / "script.docx"))
            expect(page.locator("#script-box")).to_contain_text("5 scenes found", timeout=15000)
            page.locator("#expected").fill("6")
            page.locator("#sync-btn").click()
            expect(page.get_by_text("Scene count doesn't match")).to_be_visible(timeout=10000)
            shot(page, "3_count_warning")
            page.get_by_role("button", name="Go back").click()
            page.locator("#expected").fill("5")
            page.locator("#sync-btn").click()
            expect(page.get_by_text("Mapped scenes")).to_be_visible(timeout=60000)
            expect(page.locator("#right-pane .scene-item")).to_have_count(5, timeout=10000)
            shot(page, "4_step1_synced")
            print("sync ok")

            # Step 2 table, then media
            page.locator(".stepper .step").nth(1).click()
            expect(page.get_by_text("All 5 scenes were found confidently")).to_be_visible()
            shot(page, "5_step2")
            page.get_by_role("button", name="Continue to Media").click()
            files = sorted(str(p) for p in (SAMPLE / "media").iterdir())
            page.locator("#media-drop input").set_input_files(files)
            expect(page.locator("#m-count")).to_contain_text("all 5 scenes have media", timeout=30000)
            page.locator("#music-drop input").set_input_files(str(SAMPLE / "music.mp3"))
            expect(page.locator("#x-music")).to_contain_text("music.mp3", timeout=15000)
            page.locator("#sfx-drop input").set_input_files(str(SAMPLE / "whoosh.wav"))
            expect(page.locator("#x-sfx")).to_contain_text("sfx.wav", timeout=15000)
            page.wait_for_timeout(800)
            shot(page, "6_media")
            print("media ok")

            # Step 4 review: nudge, style, preview
            page.get_by_role("button", name="Continue to Review").click()
            expect(page.locator("table.t tbody tr")).to_have_count(5, timeout=15000)
            row3 = page.locator("table.t tbody tr").nth(2)
            before = row3.locator("td").nth(2).inner_text()
            row3.locator("button[data-d='0.1']").click()
            page.wait_for_timeout(1000)
            after = page.locator("table.t tbody tr").nth(2).locator("td").nth(2).inner_text()
            assert before.split()[0] != after.split()[0], (before, after)
            assert "moved by you" in page.locator("table.t tbody tr").nth(2).inner_text()
            page.locator("#proj-form .sf-f[data-k='mode'] .chip[data-v='phrase']").click()
            page.locator("#pf-save").click()
            expect(page.get_by_text("Project style saved.")).to_be_visible()
            shot(page, "7_review")
            page.locator("button[data-prev='4']").click()
            expect(page.locator(".overlay video")).to_be_visible(timeout=120000)
            shot(page, "8_preview")
            page.keyboard.press("Escape")
            print("review + preview ok")

            # Step 5 export
            page.get_by_role("button", name="Continue to Export").click()
            page.locator("#render-btn").click()
            expect(page.locator("#out-box video")).to_be_visible(timeout=600000)
            shot(page, "9_export")
            print("render ok")

            # Presets: duplicate, rename, edit, delete
            page.goto(f"http://127.0.0.1:{PORT}/#/presets")
            expect(page.locator(".pcard")).to_have_count(3)
            page.locator(".pcard").first.get_by_role("button", name="Duplicate").click()
            page.locator("#nm").fill("My Shorts Style")
            page.locator("#nm-ok").click()
            expect(page.locator(".pcard")).to_have_count(4)
            card = page.locator(".pcard", has_text="My Shorts Style")
            card.get_by_role("button", name="Rename").click()
            page.locator("#nm").fill("My Shorts")
            page.locator("#nm-ok").click()
            card = page.locator(".pcard", has_text="My Shorts")
            expect(card).to_have_count(1)
            card.get_by_role("button", name="Edit").click()
            page.locator("#pe-ar .choice[data-v='9:16']").click()
            shot(page, "10_preset_edit")
            page.locator("#pe-save").click()
            expect(page.locator(".filters")).to_contain_text("Portrait 9:16 (1)")
            presets = json.loads((ROOT / "settings" / "presets.json").read_text())
            assert presets["My Shorts"]["aspect"] == "9:16"
            shot(page, "11_presets")
            page.locator(".pcard", has_text="My Shorts").locator("[data-a='del']").click()
            page.locator("#cf-ok").click()
            expect(page.locator(".pcard")).to_have_count(3)
            print("presets ok")

            page.goto(f"http://127.0.0.1:{PORT}/#/projects")
            expect(page.locator(".pcard")).to_have_count(1)
            shot(page, "12_projects")
            page.goto(f"http://127.0.0.1:{PORT}/#/history")
            expect(page.locator("#h-body tr")).to_have_count(1)
            shot(page, "13_history")
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
    print("UI TEST PASSED")


if __name__ == "__main__":
    main()

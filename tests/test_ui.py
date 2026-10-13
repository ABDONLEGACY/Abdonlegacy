"""Stage 6: click through the whole app in a real (headless) browser, like a user would.

Needs: pip install playwright (Chromium). The voiceover transcript is replaced by the sample's prepared
transcript (SCENEFORGE_TEST_TRANSCRIPT), because the speech model is not downloaded in the test machine.

usage: python tests/test_ui.py SAMPLE_FOLDER
"""
import os
import shutil
import subprocess
import sys
import time
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
    code = ("import sys, app; app.free_port = lambda preferred=7860: %d; sys.argv.append('--no-browser'); app.main()"
            % PORT)
    proc = subprocess.Popen([sys.executable, "-c", code], cwd=str(ROOT), env=env,
                            stdout=open(TMP / "app.log", "w"), stderr=subprocess.STDOUT)
    for _ in range(60):
        time.sleep(1)
        try:
            import urllib.request
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2)
            return proc
        except Exception:
            continue
    raise RuntimeError("app did not start: " + (TMP / "app.log").read_text())


def main():
    proc = start_app()
    try:
        with sync_playwright() as pw:
            exe = os.environ.get("SF_CHROMIUM", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
            browser = pw.chromium.launch(executable_path=exe if Path(exe).exists() else None)
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(f"http://127.0.0.1:{PORT}/")
            page.wait_for_selector("#new-name textarea, #new-name input")

            # 1. new project
            page.locator("#new-name textarea, #new-name input").first.fill("UI Test Video")
            page.get_by_role("button", name="Create project").click()
            expect(page.get_by_text("Project: UI Test Video")).to_be_visible(timeout=15000)
            page.screenshot(path=str(SHOTS / "1_project.png"))
            print("step 1 ok")

            # 2. voice (two parts, picked in the 'wrong' order) + script file
            page.get_by_role("tab", name="2. Script & Voice").click()
            page.locator("#voice-files input[type=file]").set_input_files(
                [str(SAMPLE / "voice_part2.wav"), str(SAMPLE / "voice_part1.wav")])
            time.sleep(2)
            page.get_by_role("button", name="Save voiceover").click()
            expect(page.locator("#voice-info")).to_contain_text("Voiceover saved", timeout=30000)
            txt = page.locator("#voice-info").inner_text()
            assert txt.index("voice_part1") < txt.index("voice_part2"), txt
            page.locator("#script-file input[type=file]").set_input_files(str(SAMPLE / "script.docx"))
            time.sleep(3)
            page.locator("#expected input").fill("6")
            page.get_by_role("button", name="Save script & continue").click()
            expect(page.locator("#script-info")).to_contain_text("expected 6 scenes", timeout=15000)
            print("scene-count warning shown ok")
            page.locator("#expected input").fill("5")
            page.get_by_role("button", name="Save script & continue").click()
            expect(page.locator("#script-info")).to_contain_text("Saved 5 scenes", timeout=15000)
            page.screenshot(path=str(SHOTS / "2_script_voice.png"), full_page=True)
            print("step 2 ok")

            # 3. sync
            page.get_by_role("tab", name="3. Scene Sync").click()
            page.get_by_role("button", name="Find scene starts").click()
            expect(page.locator("#sync-info")).to_contain_text("Synced", timeout=60000)
            expect(page.locator("#sync-info")).to_contain_text("All scenes were found confidently")
            page.screenshot(path=str(SHOTS / "3_sync.png"), full_page=True)
            print("step 3 ok")

            # 4. media
            page.get_by_role("tab", name="4. Media").click()
            files = sorted(str(p) for p in (SAMPLE / "media").iterdir())
            page.locator("#media-files input[type=file]").set_input_files(files)
            time.sleep(3)
            page.get_by_role("button", name="Add media", exact=True).click()
            expect(page.locator("#media-info")).to_contain_text("5 of 5 scenes have media", timeout=30000)
            page.locator("#music-file input[type=file]").set_input_files(str(SAMPLE / "music.mp3"))
            time.sleep(2)
            page.get_by_role("button", name="Use this music").click()
            expect(page.locator("#media-info")).to_contain_text("Background music: music.mp3", timeout=15000)
            page.locator("#sfx-file input[type=file]").set_input_files(str(SAMPLE / "whoosh.wav"))
            time.sleep(2)
            page.get_by_role("button", name="Use this sound").click()
            expect(page.locator("#media-info")).to_contain_text("Transition sound: sfx.wav", timeout=15000)
            page.screenshot(path=str(SHOTS / "4_media.png"), full_page=True)
            print("step 4 ok")

            # 5. review, nudge, preview, render
            page.get_by_role("button", name="Continue to Review & Export").click()
            expect(page.locator("#review table")).to_be_visible(timeout=20000)
            assert page.locator("#review tbody tr").count() == 5
            assert page.locator("#review img").count() == 5
            page.screenshot(path=str(SHOTS / "5_review.png"), full_page=True)
            # pick scene 3, nudge +0.1
            page.get_by_label("Scene", exact=True).click()
            page.get_by_role("option", name="Scene 3").click()
            expect(page.locator("#scene-info")).to_contain_text("Scene 3", timeout=10000)
            before = page.locator("#scene-info").inner_text()
            page.get_by_role("button", name="+0.1 s").click()
            page.wait_for_timeout(2500)
            after = page.locator("#scene-info").inner_text()
            assert before != after, (before, after)
            print("nudge ok:", after.splitlines()[0])
            page.get_by_role("button", name="▶ Preview this scene").click()
            expect(page.locator("#prev-video video")).to_be_visible(timeout=120000)
            print("preview ok")
            page.get_by_role("button", name="🎬 Render video").click()
            expect(page.locator("#render-msg")).to_contain_text("Finished", timeout=600000)
            expect(page.locator("#out-video video")).to_be_visible(timeout=20000)
            page.screenshot(path=str(SHOTS / "6_rendered.png"), full_page=True)
            print("render ok:", page.locator("#render-msg").inner_text().strip().splitlines()[-1])

            # presets: duplicate + rename
            page.get_by_role("tab", name="Presets").click()
            page.get_by_label("New name (for Duplicate / Rename)").fill("My Shorts Style")
            page.get_by_role("button", name="Duplicate").click()
            page.wait_for_timeout(2000)
            import json
            presets = json.loads((ROOT / "settings" / "presets.json").read_text())
            assert "My Shorts Style" in presets, list(presets)
            page.get_by_label("New name (for Duplicate / Rename)").fill("My Shorts")
            page.get_by_role("button", name="Rename").click()
            page.wait_for_timeout(2000)
            presets = json.loads((ROOT / "settings" / "presets.json").read_text())
            assert "My Shorts" in presets and "My Shorts Style" not in presets, list(presets)
            page.get_by_role("button", name="Delete").click()
            page.wait_for_timeout(2000)
            presets = json.loads((ROOT / "settings" / "presets.json").read_text())
            assert "My Shorts" not in presets
            page.screenshot(path=str(SHOTS / "7_presets.png"), full_page=True)
            print("presets ok")
            browser.close()
    finally:
        proc.terminate()
        proc.wait()
    log = (TMP / "app.log").read_text()
    if "Traceback" in log:
        print(log[-3000:])
        raise SystemExit("errors in app log")
    out = list((TMP / "projects" / "UI Test Video" / "output").glob("*.mp4"))
    print("output:", out)
    assert out
    print("UI TEST PASSED")


if __name__ == "__main__":
    main()

"""Scene Effects in the browser: sounds in Settings, placing pins/text in the Effects window, rendering.

usage:  python tests/make_effects_sample.py FX_FOLDER
        python tests/test_ui_effects.py FX_FOLDER
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FX = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/fxs")
TMP = Path(os.environ.get("SF_TEST_TMP", "/tmp/claude-0/sf_ui_fx"))
SHOTS = TMP / "shots"
PORT = 7863
sys.path.insert(0, str(ROOT))


def start_app():
    shutil.rmtree(TMP, ignore_errors=True)
    SHOTS.mkdir(parents=True)
    env = dict(os.environ, SCENEFORGE_PROJECTS=str(TMP / "projects"), SCENEFORGE_SETTINGS=str(TMP / "settings"),
               SCENEFORGE_TEST_TRANSCRIPT=str(FX / "transcript.json"))
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


def api(path):
    return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}").read())


def click_at(page, img, fx, fy):
    b = img.bounding_box()
    page.mouse.click(b["x"] + fx * b["width"], b["y"] + fy * b["height"])


def main():
    truth = json.loads((FX / "truth.json").read_text())
    proc = start_app()
    errors = []
    try:
        with sync_playwright() as pw:
            exe = os.environ.get("SF_CHROMIUM", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
            browser = pw.chromium.launch(executable_path=exe if Path(exe).exists() else None)
            page = browser.new_page(viewport={"width": 1500, "height": 950})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{PORT}/#/settings")
            # sounds, once, in Settings
            expect(page.get_by_text("Effect sounds")).to_be_visible()
            page.locator("#snd-pin input").set_input_files(str(FX / "pin_drop.wav"))
            expect(page.locator(".sound-card[data-kind=pin] .fileitem")).to_contain_text("pin_drop.wav", timeout=15000)
            page.locator("#snd-text input").set_input_files(str(FX / "text_pop.wav"))
            expect(page.locator(".sound-card[data-kind=text] .fileitem")).to_contain_text("text_pop.wav", timeout=15000)
            rng = page.locator(".sound-card[data-kind=pin] input[type=range]")
            rng.evaluate("(r) => { r.value = 0.9; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change')); }")
            page.wait_for_timeout(800)
            assert abs(api("/api/effect-sounds")["pin"]["volume"] - 0.9) < 1e-6
            page.screenshot(path=str(SHOTS / "1_settings_sounds.png"))
            print("sounds ok")

            # project with the effects script
            page.locator("#side-new").click()
            page.locator("#np-name").fill("Effects Demo")
            page.get_by_role("button", name="Create & Open Project").click()
            page.locator("#voice-drop input").set_input_files(str(FX / "voice.wav"))
            expect(page.locator("#voice-box .fileitem")).to_have_count(1, timeout=30000)
            page.locator("#script-drop input").set_input_files(str(FX / "script.txt"))
            expect(page.locator("#script-box")).to_contain_text("3 effects", timeout=15000)
            page.locator("#expected").fill("3")
            page.locator("#sync-btn").click()
            expect(page.get_by_text("Mapped scenes")).to_be_visible(timeout=60000)
            assert "[PIN" not in page.locator("#right-pane").inner_text()
            page.screenshot(path=str(SHOTS / "2_script_synced.png"))
            page.locator(".stepper .step").nth(2).click()
            page.locator("#media-drop input").set_input_files(sorted(str(p) for p in (FX / "media").iterdir()))
            expect(page.locator("#m-count")).to_contain_text("all 3 scenes have media", timeout=30000)

            # review: effects buttons and the placement window
            page.get_by_role("button", name="Continue to Review").click()
            expect(page.locator("button[data-fx]")).to_have_count(2, timeout=15000)
            expect(page.get_by_text("Scene effects to place")).to_be_visible()
            page.locator("button[data-fx='1']").click()
            img = page.locator(".fx-img")
            expect(img).to_be_visible()
            page.wait_for_function("document.querySelector('.fx-img').naturalWidth > 0")
            # Pin 1 (Rome) is selected first: click Rome on the map; then select Carthage and click it
            click_at(page, img, *truth["cities"]["Rome"])
            page.locator(".fx-item").nth(1).click()
            click_at(page, img, *truth["cities"]["Carthage"])
            page.wait_for_timeout(300)
            page.screenshot(path=str(SHOTS / "3_effects_window_pins.png"))
            page.locator("#fx-save").click()
            expect(page.get_by_text("effect positions saved")).to_be_visible()
            p = api("/api/projects/Effects%20Demo")
            pins = p["scenes"][0]["effects"]
            for e in pins:
                tx, ty = truth["cities"][e["text"]]
                print(f"  {e['text']}: placed at {e['x']:.3f}, {e['y']:.3f} (city at {tx}, {ty}) on word '{e['word']}' t={e['t']}")
                assert abs(e["x"] - tx) < 0.006 and abs(e["y"] - ty) < 0.006 and e["placed"]

            # scene 2: drag the 1940 text a bit lower
            page.locator("button[data-fx='2']").click()
            mk = page.locator(".fx-mark.text")
            expect(mk).to_be_visible()
            b = mk.bounding_box()
            page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
            page.mouse.down()
            ib = page.locator(".fx-img").bounding_box()
            page.mouse.move(ib["x"] + 0.5 * ib["width"], ib["y"] + 0.42 * ib["height"], steps=8)
            page.mouse.up()
            page.screenshot(path=str(SHOTS / "4_effects_window_text.png"))
            page.locator("#fx-save").click()
            expect(page.get_by_text("effect positions saved")).to_be_visible()
            t = api("/api/projects/Effects%20Demo")["scenes"][1]["effects"][0]
            print(f"  text 1940 dragged to {t['x']:.3f}, {t['y']:.3f}")
            assert abs(t["y"] - 0.42) < 0.01
            page.screenshot(path=str(SHOTS / "5_review.png"))

            # styles: the Scene effects section is in the project style
            page.locator(".sf-sec summary", has_text="Scene effects").click()
            expect(page.locator(".sf-f[data-k='pin_color'] input[type=text]")).to_have_value("#E53935")
            print("placement + style ok")

            # render at full 1080p
            page.get_by_role("button", name="Continue to Export").click()
            page.locator("#render-btn").click()
            expect(page.locator("#out-box video")).to_be_visible(timeout=600000)
            page.screenshot(path=str(SHOTS / "6_export.png"))
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
    # frames of the finished 1080p video at the effect moments
    out = next((TMP / "projects" / "Effects Demo" / "output").glob("*.mp4"))
    proj = json.loads((TMP / "projects" / "Effects Demo" / "project.json").read_text())
    from sceneforge import paths
    words = json.loads((TMP / "projects" / "Effects Demo" / "work" / "words.json").read_text())
    for si, sc in enumerate(proj["scenes"]):
        sw = [w for w in words if w["scene"] == si]
        for i, e in enumerate(sc.get("effects", [])):
            T = sw[e["word"]]["s"]
            row = []
            for dt in ((-0.15, 0.0, 0.12, 0.9) if e["type"] == "pin" else (-0.05, 0.06, 0.15, 0.9)):
                raw = subprocess.run([paths.ffmpeg(), "-v", "error", "-ss", f"{T + dt:.3f}", "-i", str(out), "-frames:v", "1",
                                      "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
                f = np.frombuffer(raw, np.uint8).reshape(1080, 1920, 3).copy()
                cv2.rectangle(f, (0, 0), (1920, 56), (0, 0, 0), -1)
                cv2.putText(f, f"{e['type'].upper()} '{e['text']}' on word '{sw[e['word']]['text']}' spoken at {T:.2f}s  |  frame at {T + dt:.2f}s "
                               f"({'+' if dt >= 0 else ''}{dt:.2f}s)", (14, 38), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
                row.append(f)
            sheet = np.vstack([np.hstack(row[:2]), np.hstack(row[2:])])
            cv2.imwrite(str(SHOTS / f"video_scene{sc['number']}_{i}_{e['type']}.jpg"), cv2.resize(sheet, (1920, 1080)),
                        [cv2.IMWRITE_JPEG_QUALITY, 88])
    print("EFFECTS UI TEST PASSED - screenshots in", SHOTS)


if __name__ == "__main__":
    main()

# SceneForge 🎬

Your personal video editor for your YouTube channels. You give it a voiceover, a script split into scenes,
and one picture or video clip per scene. SceneForge finds the exact moment each scene starts in the
voiceover and puts that scene's picture or clip there. It adds smooth camera movement, transitions,
captions and music, and saves a finished MP4.

It runs **only on your laptop** and opens in your web browser. There's no login and no website, and
nothing you put in it is uploaded anywhere.

---

## 1. Install it (once)

1. On the GitHub page, click the green **Code** button, then **Download ZIP**.
2. Right-click the ZIP and choose **Extract All...**. Put it somewhere simple, for example
   `C:\SceneForge` (a short path without special characters is best).
3. Open the extracted folder and double-click **`Install_SceneForge.bat`**.
   - If Windows shows *"Windows protected your PC"*, click **More info**, then **Run anyway**.
   - If Windows asks to install the *Microsoft Visual C++ runtime*, click **Yes**.
   - The install takes about 5-15 minutes and needs the internet. It downloads only free tools:
     Python, FFmpeg and the Whisper speech model (about 460 MB). Everything goes inside the SceneForge
     folder, and nothing else on your computer changes.
4. When it says **"SceneForge is installed!"**, you will find **`SceneForge.bat` on your Desktop**.

## 2. Start it

Double-click **SceneForge.bat** on your Desktop. A black window opens, and a few seconds later your
browser opens SceneForge (the address is `http://127.0.0.1:7860`).

- **Keep the black window open** while you work. Closing it stops SceneForge.
- If the browser doesn't open by itself, type `http://127.0.0.1:7860` into your browser.

## 3. Make a video (5 steps)

1. **Project**: type a name, choose 16:9 (YouTube) or 9:16 (Shorts), and pick your channel's style
   preset. Or open an old project.
2. **Script & Voice**
   - Upload your voiceover (MP3, WAV or M4A). If it's in several files, upload them all at once.
     They are joined in name order, so name them `part1`, `part2`, `part3` ...
   - Upload the script (.docx, .txt or .md), or paste it in the box.
   - Type how many scenes you expect. SceneForge warns you if the script has a different number.
3. **Scene Sync**: press **Find scene starts**. SceneForge listens to your voiceover and finds where
   each scene's first words are spoken. A 30-minute voiceover takes roughly 10-20 minutes with the
   "small" model. Scenes it isn't sure about are marked **⚠** for you to check.
4. **Media**: select all your images and clips at once, pick the whole folder, or paste the folder
   path. SceneForge shows any scene that is still missing media. You can also add background music and
   a transition sound (for example a whoosh) here.
5. **Review & Export**: check the table. For any scene you can move its start time (−0.5 s / −0.1 s /
   +0.1 s / +0.5 s, or type a time), swap its picture or clip, or play a quick preview. Then press
   **Render video**. A progress bar shows the time left. When it's done, press **Open output folder**.

Every project is saved in its own folder in **Documents\SceneForge Projects** (inputs, settings,
timings and the finished video). You can reopen it and render again at any time.

## 4. How to write the script

Start every scene with a label like `Scene 1:` at the beginning of a line:

```
Scene 1: The ancient city was buried under the sand for two thousand years.
Scene 2: In 1922, explorers finally found the hidden entrance.
Scene 3:
Inside, they discovered walls covered with strange golden symbols.
```

- `Scene 1:`, `SCENE 1 -`, `**Scene 1:**` and `## Scene 1` all work.
- Text in **[square brackets]** is treated as a note to yourself (for example `[show a map]`). It is
  not expected in the voiceover and is not shown in the captions.
- Captions use **your script's spelling**, timed to your actual voice.

## 5. How to name your media files

The **number in the file name** is the scene number:

| File name | Goes to |
|---|---|
| `Scene 1.png`, `scene_1.jpg`, `SCENE-01.webp`, `1.png` | Scene 1 |
| `scene 10.mp4`, `10.mov` | Scene 10 (10 comes after 9, not after 1) |

Accepted types: **PNG, JPG, WEBP** pictures and **MP4, MOV** clips.

- Pictures always move (zoom or pan, varied from scene to scene). Pictures with a different shape
  from the video are cropped to fill the frame, never stretched.
- Clips longer than their scene are trimmed. Clips a little too short are slowed down slightly (up to
  20%). Clips much too short are frozen or looped at the end (you choose which in the settings).
- **Keep clip audio** (on in the Documentary preset) mixes the clip's own sound effects quietly under
  your voice.

## 6. Presets (your channel styles)

There are three ready-made presets: **Documentary**, **Animated Explainer** and **POV Finance**. Open
the **Presets** tab to change movement, transitions, captions (font, size, colours, position, style)
and audio. You can **Duplicate**, **Rename** or **Delete** presets there. Presets are saved in
`settings\presets.json` inside the SceneForge folder.

A project keeps its own copy of the settings. To change one project without changing the preset, use
**"This project's settings"** in step 5.

## 7. Fixing common problems

| Problem | What to do |
|---|---|
| Nothing happens when I double-click SceneForge.bat | Open the SceneForge folder and double-click `Start_SceneForge.bat`. If it says "not installed", run `Install_SceneForge.bat` again. |
| The installer stopped with a red "INSTALL PROBLEM" | Check your internet and run `Install_SceneForge.bat` again; it continues where it stopped. A log is saved in `install_log.txt`. |
| The browser shows "can't connect" | The black SceneForge window must stay open. Start it again from the Desktop. |
| A scene is marked ⚠ (flagged) | SceneForge couldn't confidently find that scene's first words, so it estimated the start. Pick the scene in step 5, press **Preview**, and nudge it until it's right. Usually the script and voiceover differ there (a sentence was changed while recording). |
| "Less than half the script matched" | The script probably isn't the one used for this voiceover, or the wrong language is selected in step 3. |
| A scene starts a little too early or late | Nudge it in step 5. To cut every scene slightly before its first word, use **"Cut this many seconds BEFORE each scene's first word"** in the settings. |
| Rendering stopped (laptop went to sleep, window closed, Stop pressed) | Press **Render video** again. It continues where it left off, and finished parts are reused. |
| Scenes are missing media | Check the file names have the right scene numbers (see section 5). |
| My laptop is slow | Use 1080p and quality "Standard" or "Fast". 4K takes about 4 times longer. Close other programs while rendering. A 30-minute video at 1080p takes very roughly 40-90 minutes on a laptop like the HP EliteBook 840 G5. |
| Disk is getting full | In step 5, press **Delete temporary render files** after you're happy with the video. |
| Something else went wrong | The error is shown in a red pop-up and in the black window. Close SceneForge and start it again. Your projects are saved after every step. |

**Plug in your laptop while rendering, and turn off sleep** (Windows Settings → System → Power →
Screen and sleep → "Never" while plugged in). Long renders keep the CPU busy, so the fan will run.

---

## For the curious: how it works

- **Sync**: faster-whisper (the "small" or "medium" model, on the CPU in int8) writes down every word
  with its timestamp. The whole script is then lined up with that transcript as one long sequence. It
  uses exact-match anchors plus fuzzy matching, so small transcription mistakes, numbers ("1922" vs
  "nineteen twenty-two") and split words are tolerated. Each scene starts at the measured time of its
  first word. Results are cached, so the same inputs always give the same timings. Scenes whose
  opening words can't be confidently found are flagged instead of being guessed silently.
- **Exact timing**: scene *k* starts at frame `round(start × 30)`. Each transition is centred on that
  boundary and uses extra frames from *both* neighbouring scenes. The video is always exactly as long
  as the voiceover, and each scene is half-way in when its first word is spoken.
- **Smooth motion**: pictures are warped with floating-point (sub-pixel) precision, so there's none
  of the jitter that FFmpeg's zoompan has. A fixed seed per project means re-rendering gives the same
  result.
- **Low memory and resume**: the video is rendered piece by piece (each scene body and each
  transition), then joined without re-encoding. Pieces that haven't changed are reused.

### Running the tests (for developers)

```
python tests/make_sample.py sample          # builds a 5-scene sample with generated voice
python tests/test_sync.py sample
python tests/test_render.py sample
python tests/test_ui.py sample              # needs: pip install playwright
python -m sceneforge.selfcheck
```

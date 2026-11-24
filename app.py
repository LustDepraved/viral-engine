import os
import re
import json
import math
import tempfile
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from textwrap import wrap

import streamlit as st
import requests
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

APP_NAME = "VIRAL ENGINE"
CHANNELS = {
    "Gaming": {"handle": "Gaming Shorts", "tone": "fast, energetic, surprising, gamer-friendly"},
    "Facts & Tech": {"handle": "Facts & Technology", "tone": "curious, clear, surprising, intelligent"},
}

st.set_page_config(page_title=APP_NAME, page_icon="⚡", layout="wide")

def get_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def split_sentences(text):
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]

def template_script(topic, channel, duration):
    if channel == "Gaming":
        return (
            f"Most players miss this about {topic}. "
            f"At first, it looks like a normal moment. "
            f"But watch what happens when you notice the small detail. "
            f"That changes the whole situation. "
            f"Try it in your next match and see if you catch it. "
            f"Follow for more gaming discoveries."
        )
    return (
        f"Here's something surprising about {topic}. "
        f"The first detail sounds ordinary, but the explanation is much more interesting. "
        f"Scientists and engineers study details like this to understand how the world works. "
        f"The key idea is simple: small changes can create surprisingly big results. "
        f"What part surprised you most? Follow for more quick facts."
    )

def generate_with_gemini(topic, channel, duration, api_key):
    from google import genai
    client = genai.Client(api_key=api_key)
    prompt = f"""
Write an original English YouTube Shorts voiceover script.
Channel: {channel}. Topic: {topic}. Target length: {duration} seconds.
Audience: general US viewers. Tone: {CHANNELS[channel]['tone']}.
Requirements: immediate hook in first 2 seconds, clear progression, one memorable payoff,
natural spoken English, short sentences, accurate claims, no fabricated statistics,
no copied catchphrases, no requests to harass anyone, and a concise CTA.
Return only the spoken script, no title or stage directions.
"""
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return response.text.strip()

def youtube_trends(query, api_key, region="US"):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet", "type": "video", "q": query, "regionCode": region,
        "order": "viewCount", "publishedAfter": (datetime.now(timezone.utc)-timedelta(days=7)).isoformat(),
        "maxResults": 12, "key": api_key
    }
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    items = response.json().get("items", [])
    return [{
        "title": x["snippet"]["title"],
        "channel": x["snippet"]["channelTitle"],
        "published": x["snippet"]["publishedAt"][:10],
        "url": "https://www.youtube.com/watch?v=" + x["id"]["videoId"],
        "thumbnail": x["snippet"]["thumbnails"].get("medium", {}).get("url", "")
    } for x in items]

def render_short(script, title, channel, seconds, voice=True):
    sentences = split_sentences(script)
    if not sentences:
        raise ValueError("Add a script before rendering.")
    # Keep the video within a practical Shorts length.
    seconds = max(12, min(int(seconds), 58))
    scene_count = min(max(3, len(sentences)), 8)
    chunks = [" ".join(sentences[i::scene_count]) for i in range(scene_count)]
    chunks = [c for c in chunks if c.strip()]
    seconds = max(seconds, len(chunks) * 3)
    fps, width, height = 24, 720, 1280
    tmp = tempfile.mkdtemp(prefix="viral_engine_")
    frame_dir = Path(tmp) / "frames"
    frame_dir.mkdir()
    audio_path = Path(tmp) / "voice.mp3"
    output_path = Path(tmp) / "viral_short.mp4"
    font_big, font_body, font_small = get_font(58, True), get_font(39, True), get_font(24, False)
    colors = [(12, 20, 42), (24, 18, 48), (9, 35, 49), (34, 20, 42)]
    scene_seconds = seconds / len(chunks)

    for idx, sentence in enumerate(chunks):
        for frame in range(int(math.ceil(scene_seconds * fps))):
            progress = frame / max(1, int(scene_seconds * fps))
            im = Image.new("RGB", (width, height), colors[idx % len(colors)])
            draw = ImageDraw.Draw(im)
            # Subtle moving light bands.
            offset = int(progress * 40)
            for y in range(-200, height + 300, 180):
                draw.rounded_rectangle((35, y + offset, width-35, y+70+offset), radius=35,
                                        fill=(18 + idx*3, 40 + idx*2, 67 + idx*3))
            draw.rounded_rectangle((42, 62, width-42, 132), radius=22, fill=(247, 190, 55))
            draw.text((width//2, 97), channel.upper(), font=font_small, fill=(15, 20, 35), anchor="mm")
            draw.text((width//2, 205), title[:42], font=font_big, fill="white", anchor="mm")
            words = wrap(sentence, width=23)
            line_height = 56
            y0 = 550 - (len(words)*line_height)//2
            for line in words[:7]:
                draw.text((width//2, y0), line, font=font_body, fill="white", anchor="mm",
                          stroke_width=1, stroke_fill=(0, 0, 0))
                y0 += line_height
            draw.rounded_rectangle((58, 1085, width-58, 1185), radius=24, fill=(247, 190, 55))
            draw.text((width//2, 1135), f"PART {idx+1}  •  FOLLOW FOR MORE", font=font_small,
                      fill=(18, 22, 35), anchor="mm")
            draw.text((width//2, 1230), "Original content • VIRAL ENGINE", font=font_small,
                      fill=(190, 202, 220), anchor="mm")
            im.save(frame_dir / f"frame_{idx:02d}_{frame:04d}.png")

    audio_ok = False
    if voice:
        try:
            from gtts import gTTS
            gTTS(text=script, lang="en", tld="com", slow=False).save(str(audio_path))
            audio_ok = audio_path.exists() and audio_path.stat().st_size > 1000
        except Exception:
            audio_ok = False

    # Create a concat list with each generated frame in order.
    concat_file = Path(tmp) / "frames.txt"
    with concat_file.open("w", encoding="utf-8") as f:
        for file in sorted(frame_dir.glob("*.png")):
            f.write("file '" + str(file).replace("'", "'\\''") + "'\n")
            f.write(f"duration {1/fps:.6f}\n")
        last = sorted(frame_dir.glob("*.png"))[-1]
        f.write("file '" + str(last).replace("'", "'\\''") + "'\n")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]
    if audio_ok:
        cmd += ["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    cmd += ["-vf", "fps=24,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast",
            "-crf", "27", "-movflags", "+faststart", str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError("Video rendering failed: " + result.stderr[-1200:])
    return output_path.read_bytes(), ("voiceover included" if audio_ok else "video rendered without voiceover")

def init_state():
    st.session_state.setdefault("scripts", {})
    st.session_state.setdefault("last_video", None)
    st.session_state.setdefault("last_video_name", "viral_short.mp4")
    st.session_state.setdefault("ideas", [])

init_state()

with st.sidebar:
    st.markdown("# ⚡ VIRAL ENGINE")
    st.caption("Short-form content studio")
    page = st.radio("Workspace", ["Dashboard", "Trend Explorer", "Script Studio", "Shorts Builder", "Settings"])
    st.divider()
    st.caption("Target audience")
    st.write("United States · English")
    st.caption("Publishing timezone")
    st.write("America/New_York")

if page == "Dashboard":
    st.title("VIRAL ENGINE")
    st.caption("One workspace for two original Shorts channels.")
    a, b, c = st.columns(3)
    a.metric("Channels", "2")
    b.metric("Target market", "United States")
    c.metric("Publishing format", "9:16 Shorts")
    st.subheader("Your channels")
    cols = st.columns(2)
    for col, (name, info) in zip(cols, CHANNELS.items()):
        with col:
            st.container(border=True)
            st.markdown(f"### {name}")
            st.write(info["handle"])
            st.caption(info["tone"].capitalize())
            st.write("Language: English (US)")
    st.subheader("Workflow")
    st.markdown("1. Find a topic in **Trend Explorer**.\n2. Create a hook and voiceover in **Script Studio**.\n3. Render an original vertical video in **Shorts Builder**.\n4. Review it, then upload through YouTube Studio.")
    st.info("This first release creates and exports videos. It does not publish automatically or access your YouTube account. That avoids accidental uploads and keeps account permissions out of the initial setup.")

elif page == "Trend Explorer":
    st.title("Trend Explorer")
    st.write("Search recent, high-view YouTube videos in the US for topic research. This is a discovery aid, not a guarantee that a topic is trending.")
    api_key = st.text_input("YouTube Data API key (optional)", type="password", help="Add a Google Cloud YouTube Data API v3 key. It is used only for this session.")
    channel = st.selectbox("Research channel", list(CHANNELS.keys()))
    default_query = "gaming" if channel == "Gaming" else "technology science facts"
    query = st.text_input("Search keywords", default_query)
    if st.button("Find videos", type="primary"):
        if not api_key:
            st.warning("Add a YouTube Data API key to run live search. You can still use the topic ideas below.")
        else:
            try:
                with st.spinner("Searching YouTube..."):
                    results = youtube_trends(query, api_key)
                if not results:
                    st.info("No matching recent videos were returned. Try broader keywords.")
                for item in results:
                    with st.container(border=True):
                        st.markdown(f"**[{item['title']}]({item['url']})**")
                        st.caption(f"{item['channel']} · published {item['published']}")
                        if st.button("Use topic", key="topic_"+item["url"]):
                            st.session_state["selected_topic"] = item["title"]
                            st.success("Topic copied to Script Studio. Open that page next.")
            except Exception as e:
                st.error(f"Search failed: {e}")
    st.subheader("Topic starters")
    ideas = (["hidden mechanics in popular games", "beginner mistakes that change a match", "game updates players overlooked", "unexpected speedrun discoveries"]
             if channel == "Gaming" else
             ["technology that already exists but feels futuristic", "everyday science explained simply", "misconceptions about artificial intelligence", "engineering inventions with surprising origins"])
    for idea in ideas:
        st.markdown(f"- {idea}")

elif page == "Script Studio":
    st.title("Script Studio")
    channel = st.selectbox("Channel", list(CHANNELS.keys()))
    topic = st.text_input("Video topic", st.session_state.get("selected_topic", "A surprising discovery in gaming"))
    duration = st.slider("Target duration (seconds)", 15, 58,  thirty if False else  thirty if False else  thirty if False else  thirty if False else  thirty if False else 30)
    gemini_key = st.text_input("Gemini API key (optional)", type="password", help="Without a key, the built-in script template is used.")
    if st.button("Generate script", type="primary"):
        try:
            with st.spinner("Writing an original script..."):
                script = generate_with_gemini(topic, channel, duration, gemini_key) if gemini_key else template_script(topic, channel, duration)
            st.session_state["scripts"][channel] = {"topic": topic, "text": script, "duration": duration}
            st.success("Script ready.")
        except Exception as e:
            st.error(f"AI generation failed: {e}")
    current = st.session_state["scripts"].get(channel, {})
    edited = st.text_area("Voiceover script (edit before rendering)", value=current.get("text", ""), height=260)
    title = st.text_input("Short title", value=current.get("topic", topic))
    if st.button("Save script"):
        st.session_state["scripts"][channel] = {"topic": title, "text": edited, "duration": duration}
        st.success("Saved for this session. Continue to Shorts Builder.")

elif page == "Shorts Builder":
    st.title("Shorts Builder")
    st.write("Create a vertical 9:16 video from your original script. The current renderer uses animated text cards; upload your own licensed background footage in a later build.")
    channel = st.selectbox("Channel", list(CHANNELS.keys()))
    saved = st.session_state["scripts"].get(channel, {})
    title = st.text_input("Video title", saved.get("topic", "A surprising discovery"))
    script = st.text_area("Script", saved.get("text", ""), height=230, placeholder="Paste or create your English voiceover script in Script Studio.")
    duration = st.slider("Video length target", 15, 58, int(saved.get("duration", 30)))
    add_voice = st.checkbox("Generate English voiceover (internet connection required)", value=True)
    if st.button("Render my Short", type="primary"):
        if len(script.strip()) < 40:
            st.warning("Add a more complete script (at least 40 characters).")
        else:
            try:
                with st.spinner("Rendering video in the cloud..."):
                    video, status = render_short(script, title, channel, duration, add_voice)
                st.session_state["last_video"] = video
                st.session_state["last_video_name"] = re.sub(r"[^a-zA-Z0-9_-]+", "-", title).strip("-")[:50] + ".mp4"
                st.success("Video rendered: " + status)
            except Exception as e:
                st.error(str(e))
    if st.session_state["last_video"]:
        st.video(st.session_state["last_video"])
        st.download_button("Download MP4", st.session_state["last_video"],
                           file_name=st.session_state["last_video_name"], mime="video/mp4")
        st.caption("Review the result before uploading. Check facts, pronunciation, rights to any assets, and YouTube policies.")

else:
    st.title("Settings")
    st.subheader("Channel configuration")
    st.json(CHANNELS)
    st.subheader("API integrations")
    st.markdown("""
- **YouTube Data API v3:** optional, for trend discovery. Create a key in Google Cloud Console and enable YouTube Data API v3.
- **Gemini API:** optional, for more varied script drafts. The app works with a built-in template without it.
- **Voiceover:** optional online text-to-speech. If it fails, the video is still rendered without audio.
""")
    st.subheader("Current limitations")
    st.markdown("""
- No automatic publishing or scheduled uploads in this release.
- No downloading, clipping, or reposting other creators' videos.
- Free hosting has resource and sleep limits; generated files and session data may not persist after a restart.
- API quotas and free tiers can change. No paid service is activated by this app.
""")
    st.caption("VIRAL ENGINE · MVP · Built for original English-language Shorts")

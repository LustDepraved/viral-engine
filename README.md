# VIRAL ENGINE

Cloud workspace for original English-language YouTube Shorts.

## Included
- Two channel presets: Gaming and Facts & Technology.
- US-focused topic research through YouTube Data API v3 (optional key).
- Script drafting with Gemini (optional key) and a built-in fallback.
- Vertical 9:16 MP4 text-card videos with optional English TTS voiceover.
- Preview and MP4 export.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy
Render configuration is included in `render.yaml`. The free web service can sleep when idle and has limited CPU/RAM. Temporary files and session state may be lost on restart.

## Optional integrations
- YouTube Data API v3 key for trend discovery.
- Gemini API key for AI script generation.
Keys are entered in the app session and are not stored in the repository.

## Safety and platform compliance
The app creates original text-card videos. It does not download, clip, or repost third-party videos and does not publish to YouTube automatically. Review facts, voiceover, rights to all assets, and YouTube monetization policies before uploading. Do not use misleading claims or copyrighted footage/music without permission.

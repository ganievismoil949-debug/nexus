# Nexus — local AI desktop assistant

Nexus is an English desktop assistant for Zorin OS. A polished pearl-like animated companion lives at the center of Home, with separate Chat and Memory pages and Settings at the bottom left. Click the Nexus logo to smoothly switch the sidebar between labels and icons. The character reacts while listening, thinking and speaking, and pauses its motion when the window is hidden. Its face is drawn in SVG and needs no graphics card.

## Open Nexus

Run **Launch Nexus.sh** in this folder. In Files, right-click it and choose **Run as a Program**, or open a terminal here and run:

```bash
./"Launch Nexus.sh"
```

The app uses GTK 3 and WebKit, with its own local window. The launcher selects Wayland when Zorin is running a Wayland session; `NEXUS_GDK_BACKEND=x11` can explicitly select X11 if needed. It reuses Ollama or starts an already installed Ollama engine on localhost. The model setting defaults to **Automatic**: it chooses an installed local Qwen model from currently available memory. On an 8 GB machine, start with `ollama pull qwen2.5:1.5b`; it is compact and tool-capable. `ollama pull qwen3.5:2b-q4_K_M` installs a newer quantized model when you have enough free memory. Automatic may still choose the smaller model when other programs are using RAM. Larger models remain selectable in Settings and may respond more slowly. No model can be both the most capable and equally fast on every low-memory computer.

## First things to try

Type in Chat, or press **Talk to Nexus** and speak English during the eight-second listening window:

- `Create a file named hello.txt in Documents containing exactly "Hello from Nexus."`
- `Delete that file` — moves the most recently identified file to recoverable Trash.
- `Remember that I prefer short answers`
- `Open YouTube`
- `Open Calculator`
- `List my Downloads folder`
- `Read my unread Gmail messages` — after connecting your account.

Explicit create/save commands preserve the supplied text directly. Other requests use the local language model to select an available action. Recent conversation helps resolve short follow-ups such as “delete it”; Nexus asks which item you mean when the target is unclear, and moves only one identified item to recoverable Trash. Small local models can still misunderstand complex instructions, so inspect Activity in Settings. You can stop before the next action, but an action already completed is not undone. Files are never intentionally overwritten.

## Try a stronger model in Google Colab

Open [`Nexus_Colab_GPU.ipynb`](Nexus_Colab_GPU.ipynb) in Google Colab, select a GPU runtime, and run the cells from top to bottom. The notebook uses Ollama with Qwen 3.5 9B by default; choose 4B in its first code cell if the assigned GPU has limited memory. Colab GPU types and availability change over time, and free runtimes can be stopped. The notebook keeps its chat in the Colab session and does not connect a public tunnel or access your Zorin computer. It is a model chat lab, not GPU acceleration for Nexus's local desktop-control tools.

Release snapshots are marked with Git tags: `v0.1.0` is the local desktop version and `v0.2.0` adds this Colab notebook.

## Offline operation and voice

Chat, local file tools, saved memory, speech recognition and speech synthesis run on this computer after setup. There is no cloud AI API key. Network services such as YouTube, Gmail and Telegram still need an internet connection to retrieve new content.

Speech uses the English **Alan** Piper voice; eSpeak is a fallback when the Piper assets are absent. Vosk handles English speech recognition. Microphone capture is push-to-talk, not always listening, and temporary audio files are removed after use. Disable automatic speech in Settings if you prefer text replies.

On another Zorin installation, run `bash setup.sh` once while connected to the internet. This downloads Python dependencies and roughly 100 MB of voice assets and can resume interrupted asset downloads. Required system packages are Python 3, `python3-venv`, `python3-gi`, `gir1.2-gtk-3.0`, `gir1.2-webkit2-4.1`, `gir1.2-atspi-2.0`, `gir1.2-secret-1`, `libglib2.0-bin`, `alsa-utils`, and `espeak-ng`. Install missing system packages through Zorin's package manager. Install Ollama from its official site, then pull one of the local models above. Setup does not change system packages or download an LLM automatically.

## Connect your accounts

In Settings, expand Gmail and enter your address and a [Google app password](https://support.google.com/accounts/answer/185833). This requires an eligible Google account with two-step verification. Organization policies may prevent app passwords. Nexus reads up to five unread emails and leaves them unread. HTML-only messages may require opening Gmail.

For Telegram, obtain your own API ID and API hash from [my.telegram.org/apps](https://my.telegram.org/apps), enter them with your phone number, then enter Telegram's login code and two-step password if requested. Nexus reads recent unread chats. It does not send messages or mark them read.

Credentials use the OS keyring when available; otherwise they last only for the current session. Telegram's session is stored in the private `.data` directory. Live account sign-in requires your own credentials and has not been verified with your accounts.

## Data and scope

Chat history, preferences, settings and a short action log are stored in `.data/nexus.sqlite3` beside the app. Memory can be inspected and forgotten individually. New chat clears chat history but keeps preferences. Keep `.data` private; exclude it when sharing the source. An alternative data directory can be selected with `NEXUS_DATA_DIR`.

Version 0.1 can launch installed apps, open websites, read accessible screen text when applications expose it, and create/read/move/trash ordinary files in your home directory. It excludes hidden configuration directories, system files and its own storage. It is **not yet a general mouse/keyboard agent**: arbitrary UI clicking, video understanding, attachments, message sending, administrator changes and unrestricted computer control are not implemented. Wayland and each app's accessibility support affect screen-text access. Ambiguous file references require a specific name.

The local server binds only to 127.0.0.1 and uses a per-launch session token. It is not intended for public hosting. Webpage, file and message contents are treated as data; tool calls are allowlisted and mutation types must match the user's original request. These checks reduce unintended actions but do not make a small language model infallible.

## Development and verification

```bash
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js
```

`app.py --headless --write-session /tmp/nexus-session.json` runs an authenticated local browser UI for development; the session file is private and should not be shared. Tests use disposable data. See `VALIDATION.md` for the checks completed on this machine.

Components: [Ollama](https://ollama.com), [Qwen 3.5 models](https://ollama.com/library/qwen3.5), [Qwen local model guide](https://qwen.readthedocs.io/en/v2.5/run_locally/ollama.html), [Piper](https://github.com/OHF-Voice/piper1-gpl), [Vosk](https://alphacephei.com/vosk/), and [Telethon](https://docs.telethon.dev). Dependencies and downloaded models retain their own licenses. The Alan model card is included in `assets/MODEL_CARD`.

# Validation — 27 October 2026

Machine: Zorin OS 18.1, Intel Core i5-10310U, Intel integrated graphics, 8 GB RAM, Wayland, Python 3.12.

- **40 automated tests passed.** They cover safe file access, recoverable Trash, memory and history, request authorization, ambiguous deletion, ordinary and polite language, graceful model fallback, multi-step tool handling, HTTP authentication and settings.
- Python compilation, JavaScript syntax, shell syntax and SVG XML parsing passed.
- Real local-model sample: `qwen2.5:1.5b` answered “In one short sentence, greet the user as Nexus.” with “Hello, Nexus!” in 5.29 seconds including model startup; Ollama reported 0.36 seconds for the five generated tokens. This is one short prompt, not a general speed guarantee.
- A clear create-file command used the direct local route and completed in 20 ms in a disposable folder, without waiting for the language model.
- The current model list includes `qwen2.5:1.5b` and `qwen3.5:4b`. Automatic selected the smaller model based on available RAM. A pull for `qwen3.5:2b-q4_K_M` was attempted, but the large download repeatedly stalled and did not finish, so it was stopped. The existing local models remain usable; no claim is made about the new model's speed or quality.
- New UI code uses a custom SVG companion, CSS motion for idle/listening/thinking/speaking states, a collapsible icon-only sidebar, hidden-page animation pause, and reduced-motion support. JavaScript syntax and page structure checks pass. A browser screenshot could not be captured because browser use is disabled in this Work environment; the stored `preview.jpg` images are from the earlier design.
- Existing offline speech assets remain installed. Earlier validation confirmed Piper English male voice generation and Vosk transcription from synthesized speech. Live microphone capture and speaker playback are not verified here.

Live Gmail or Telegram sign-in and message retrieval were not tested because they require the user's credentials. Arbitrary mouse/keyboard automation and interpreting YouTube video content are not implemented. Website message reading needs internet access even though Nexus's assistant model, file tools, memory and voice processing are local.

## Previous validation

The original v0.1 validation ran 22 tests and confirmed the native Wayland GTK/WebKit window reached “Nexus interface loaded.” It also documented the account, microphone and accessibility limitations above. The current test count includes expanded natural-language and tool-protocol checks.

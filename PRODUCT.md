# Product

The name is Gym. The home screen is a notepad. Trends, Coach, and Account are the other tabs. Warm paper, ink, one amber accent. The design system lives in `mobile/src/constants/theme.ts`.

## What it does

- Login opens the demo book.
- Notes is one plain text field for the whole log. Typing autosaves. A pause parses a short note when a model key is set. The unsent draft stays on the device.
- Trends reads `/trends`. Strength lists estimated 1RM. Body and Fuel stay on the screen. Bodyweight and calories are empty until something records them. The supplement line counts session dates.
- Coach asks the model about the log and does not change it.
- Account edits height and the weekday split, and can reset the demo book.

The API base is `EXPO_PUBLIC_API_URL`, default `http://127.0.0.1:9477`. Each account is a JSON book under `data/`.

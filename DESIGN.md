# Design

The home screen is a notepad. The dashboard is the diary that note becomes once it has been read. Warm paper, ink, and one amber mark for the thing you can do.

## Color

Light paper `#F3EEE6`, ink `#1C1915`, secondary `#5E574C`, rule `#DDD4C6`. Amber `#8A5A12` with white text.

Dark paper `#16130F`, raised `#221E19`, ink `#F4EFE6`, secondary `#B7AA9A`, rule `#3A332B`. Amber `#E0B15A` with `#1A140C` text.

On iPhone and Android, backgrounds, labels, and separators use the platform semantic colors. Amber stays the action color. Tokens live in `mobile/src/constants/theme.ts`.

## Type

The note and the list use the system face. Body 17. The diary date uses the platform serif at 34. Measurements use tabular figures.

## Structure

Notes is a list: large title, search, first line, then the day and the next lines, date at the trailing edge. New is a plus. The editor is the page. There is no save button. Dashboard reads as dates, exercise names, and set lines. Day, Photo, and Account sit behind More.

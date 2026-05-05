from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cleaning import normalize_transcript_text
from .pathing import resolve_unique_path, sanitize_stem


DEFAULT_TRANSCRIPT_LANGUAGES = ("en", "en-US", "en-GB")
AUDIO_SUFFIXES = {".aac", ".aiff", ".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".oga", ".ogg", ".wav", ".webm"}
WHISPER_MAX_BYTES = 25 * 1024 * 1024
CHUNK_SECONDS = 1200


@dataclass(frozen=True)
class RemoteTranscript:
    url: str
    title: str
    text: str
    source_type: str
    transcript_source: str
    metadata: dict[str, str] = field(default_factory=dict)


def is_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def load_remote_transcript(
    url: str,
    *,
    transcriber: str = "auto",
    languages: tuple[str, ...] = DEFAULT_TRANSCRIPT_LANGUAGES,
    transcription_model: str | None = None,
    transcription_language: str | None = None,
    transcription_prompt: str | None = None,
) -> RemoteTranscript:
    if transcriber not in {"auto", "captions", "openai"}:
        raise ValueError("transcriber must be one of: auto, captions, openai")

    if is_youtube_url(url):
        if transcriber in {"auto", "captions"}:
            try:
                return load_youtube_captions(url, languages=languages)
            except RuntimeError:
                if transcriber == "captions":
                    raise
        return transcribe_remote_audio(
            url,
            source_type="youtube",
            model=transcription_model,
            language=transcription_language,
            prompt=transcription_prompt,
        )

    if is_spotify_episode_url(url):
        return load_spotify_podcast(
            url,
            transcriber=transcriber,
            languages=languages,
            transcription_model=transcription_model,
            transcription_language=transcription_language,
            transcription_prompt=transcription_prompt,
        )

    if transcriber in {"auto", "captions"}:
        try:
            return load_podcast_transcript(url)
        except RuntimeError:
            if transcriber == "captions":
                raise

    episode = resolve_podcast_episode(url)
    audio_url = episode.get("audio_url") or url
    return transcribe_remote_audio(
        audio_url,
        source_type="podcast",
        title=episode.get("title") or _title_from_url(url),
        model=transcription_model,
        language=transcription_language,
        prompt=transcription_prompt,
        metadata={
            "source_url": url,
            "audio_url": audio_url,
            "feed_url": episode.get("feed_url", ""),
            "episode_url": episode.get("episode_url", ""),
        },
    )


def is_youtube_url(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    host = host.removeprefix("www.")
    return host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "youtube-nocookie.com"}


def is_spotify_episode_url(url: str) -> bool:
    return bool(re.search(r"open\.spotify\.com/(?:intl-[a-z]{2}/)?episode/[A-Za-z0-9]+", url))


def extract_youtube_video_id(url: str) -> str | None:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url.strip()):
        return url.strip()
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if host == "youtu.be":
        return parsed.path.strip("/") or None
    if parsed.path == "/watch":
        return urllib.parse.parse_qs(parsed.query).get("v", [None])[0]
    match = re.match(r"^/(?:embed|shorts|live)/([^/?#]+)", parsed.path)
    return match.group(1) if match else None


def load_youtube_captions(
    url: str,
    *,
    languages: tuple[str, ...] = DEFAULT_TRANSCRIPT_LANGUAGES,
) -> RemoteTranscript:
    video_id = extract_youtube_video_id(url)
    if not video_id:
        raise RuntimeError(f"could not extract YouTube video id from URL: {url}")

    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "YouTube captions require the optional dependency: "
            "pip install 'phrasify[media]'"
        ) from exc

    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id) if hasattr(api, "list") else YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_manually_created_transcript(languages)
        except Exception:
            transcript = transcript_list.find_generated_transcript(languages)
        fetched = transcript.fetch()
        rows = fetched.snippets if hasattr(fetched, "snippets") else fetched
    except Exception as exc:
        raise RuntimeError(f"could not load YouTube captions for {video_id}: {exc}") from exc

    lines = [_caption_text(row) for row in rows]
    text = normalize_transcript_text("\n".join(line for line in lines if line))
    if not text:
        raise RuntimeError(f"empty YouTube captions for {video_id}")

    return RemoteTranscript(
        url=url if is_url(url) else f"https://www.youtube.com/watch?v={video_id}",
        title=f"youtube-{video_id}",
        text=text,
        source_type="youtube",
        transcript_source="youtube-captions",
        metadata={"video_id": video_id},
    )


def _caption_text(row: Any) -> str:
    if isinstance(row, dict):
        return html.unescape(str(row.get("text", ""))).strip()
    return html.unescape(str(getattr(row, "text", ""))).strip()


def load_podcast_transcript(url: str) -> RemoteTranscript:
    episode = resolve_podcast_episode(url)
    transcript_url = episode.get("transcript_url")
    if not transcript_url:
        raise RuntimeError("podcast episode does not expose a transcript URL")

    transcript_body, transcript_type, _ = _fetch_text(transcript_url)
    text = _parse_transcript_payload(transcript_body, transcript_type)
    if not text:
        raise RuntimeError(f"empty podcast transcript: {transcript_url}")

    return RemoteTranscript(
        url=url,
        title=episode.get("title") or _title_from_url(url),
        text=text,
        source_type="podcast",
        transcript_source="podcast-transcript",
        metadata={
            "feed_url": episode.get("feed_url", ""),
            "episode_url": episode.get("episode_url", ""),
            "transcript_url": transcript_url,
            "audio_url": episode.get("audio_url", ""),
        },
    )


def resolve_podcast_episode(url: str) -> dict[str, str]:
    if _looks_like_audio_url(url):
        return {
            "title": _title_from_url(url),
            "episode_url": url,
            "audio_url": url,
            "feed_url": "",
            "transcript_url": "",
        }

    body, content_type, final_url = _fetch_text(url)
    if _looks_like_feed(body, content_type):
        return _episode_from_feed(body, preferred_url=final_url, feed_url=final_url)
    else:
        feed_url = _discover_feed_url(body, final_url)
        if not feed_url:
            raise RuntimeError("could not discover a podcast RSS feed from this URL")
        feed_body, _, _ = _fetch_text(feed_url)
        return _episode_from_feed(feed_body, preferred_url=final_url, feed_url=feed_url)


def load_spotify_podcast(
    url: str,
    *,
    transcriber: str,
    languages: tuple[str, ...],
    transcription_model: str | None,
    transcription_language: str | None,
    transcription_prompt: str | None,
) -> RemoteTranscript:
    episode = resolve_spotify_episode(url)
    if transcriber == "captions":
        yt = find_youtube_episode_captions(
            episode["show_name"],
            episode["title"],
            languages=languages,
            duration_hint_seconds=_int_or_none(episode.get("duration_seconds")),
        )
        if yt is None:
            raise RuntimeError("no YouTube captions found for this podcast episode")
        return yt

    apple = resolve_apple_episode(
        episode["show_name"],
        episode["title"],
        country=os.environ.get("PHRASIFY_PODCAST_COUNTRY", "jp"),
    )
    prompt = transcription_prompt or ", ".join(
        part for part in (episode.get("show_name"), episode.get("title")) if part
    )
    if apple and apple.get("audio_url"):
        try:
            return transcribe_remote_audio(
                apple["audio_url"],
                source_type="podcast",
                title=episode["title"],
                model=transcription_model,
                language=transcription_language,
                prompt=prompt,
                metadata={
                    "source_url": url,
                    "spotify_episode_id": episode["episode_id"],
                    "show_name": episode.get("show_name", ""),
                    "apple_episode_url": apple.get("episode_url", ""),
                    "audio_url": apple.get("audio_url", ""),
                    "feed_url": apple.get("feed_url", ""),
                },
            )
        except RuntimeError:
            if transcriber == "openai":
                raise

    yt = find_youtube_episode_captions(
        episode["show_name"],
        episode["title"],
        languages=languages,
        duration_hint_seconds=_int_or_none(episode.get("duration_seconds")),
    )
    if yt:
        return yt
    raise RuntimeError(
        "could not transcribe podcast: Apple RSS audio was not available or transcription failed, "
        "and no matching YouTube captions were found"
    )


def transcribe_remote_audio(
    url: str,
    *,
    source_type: str,
    title: str | None = None,
    model: str | None = None,
    language: str | None = None,
    prompt: str | None = None,
    metadata: dict[str, str] | None = None,
) -> RemoteTranscript:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "no transcript/captions were found, and OPENAI_API_KEY is not set for audio transcription"
        )

    with tempfile.TemporaryDirectory() as td:
        audio_path = _download_audio(url, Path(td))
        result = _transcribe_audio_file(
            audio_path,
            model=model or os.environ.get("PHRASIFY_OPENAI_TRANSCRIBE_MODEL", "whisper-1"),
            language=language,
            prompt=prompt,
        )
    text = normalize_transcript_text(result["full_text"])
    if not text:
        raise RuntimeError(f"empty transcription result for {url}")
    return RemoteTranscript(
        url=url,
        title=title or _title_from_url(url),
        text=text,
        source_type=source_type,
        transcript_source="openai-transcription",
        metadata={
            **(metadata or {}),
            "audio_url": url,
            "language": result.get("language", ""),
            "language_code": _to_iso639_1(result.get("language") or language or ""),
            "model": model or os.environ.get("PHRASIFY_OPENAI_TRANSCRIBE_MODEL", "whisper-1"),
        },
    )


def _download_audio(url: str, directory: Path) -> Path:
    if _looks_like_audio_url(url):
        suffix = Path(urllib.parse.urlparse(url).path).suffix or ".mp3"
        destination = directory / f"audio{suffix}"
        with urllib.request.urlopen(url, timeout=30) as response:
            destination.write_bytes(response.read())
        return destination

    yt_dlp = shutil.which("yt-dlp")
    if yt_dlp is None:
        raise RuntimeError(
            "audio extraction from this URL requires yt-dlp; install with: "
            "pip install 'phrasify[media]'"
        )

    output_template = str(directory / "audio.%(ext)s")
    result = subprocess.run(
        [
            yt_dlp,
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "9",
            "--postprocessor-args",
            "ffmpeg:-ar 16000 -ac 1 -b:a 32k",
            "-o",
            output_template,
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp audio extraction failed: {result.stderr.strip()}")
    audio_files = sorted(directory.glob("audio.*"))
    if not audio_files:
        raise RuntimeError("yt-dlp did not produce an audio file")
    return audio_files[0]


def _transcribe_audio_file(
    audio_path: Path,
    *,
    model: str,
    language: str | None,
    prompt: str | None,
) -> dict[str, Any]:
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "audio transcription requires the optional dependency: "
            "pip install 'phrasify[openai]'"
        ) from exc

    if not _ffmpeg_available() and audio_path.stat().st_size > WHISPER_MAX_BYTES:
        raise RuntimeError("audio is larger than 25MB and ffmpeg/ffprobe are required to split it")

    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)
        source = audio_path
        encoded = workdir / "encoded.mp3"
        if _ffmpeg_available():
            _reencode_audio(audio_path, encoded, bitrate_kbps=32)
            source = encoded

        chunks = [source]
        if source.stat().st_size > WHISPER_MAX_BYTES:
            chunks = _split_chunks(source, workdir, chunk_seconds=CHUNK_SECONDS)

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        full_text_parts: list[str] = []
        all_segments: list[dict[str, Any]] = []
        detected_language = language or ""
        offset = 0.0
        for chunk in chunks:
            with chunk.open("rb") as audio_file:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "file": audio_file,
                    "response_format": "verbose_json",
                    "timestamp_granularities": ["segment"],
                }
                if language:
                    kwargs["language"] = language
                if prompt:
                    kwargs["prompt"] = prompt
                response = client.audio.transcriptions.create(**kwargs)
            text = str(getattr(response, "text", "") or "")
            full_text_parts.append(text)
            detected_language = detected_language or str(getattr(response, "language", "") or "")
            for segment in getattr(response, "segments", []) or []:
                start = float(getattr(segment, "start", 0.0))
                end = float(getattr(segment, "end", start))
                all_segments.append(
                    {
                        "text": str(getattr(segment, "text", "")).strip(),
                        "start": start + offset,
                        "duration": max(0.0, end - start),
                    }
                )
            if len(chunks) > 1:
                offset += _get_duration_seconds(chunk)
    return {
        "language": detected_language or "unknown",
        "segments": all_segments,
        "full_text": "\n\n".join(part for part in full_text_parts if part).strip(),
    }


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _reencode_audio(src: Path, dst: Path, *, bitrate_kbps: int) -> None:
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-b:a",
            f"{bitrate_kbps}k",
            "-loglevel",
            "error",
            str(dst),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio re-encode failed: {result.stderr.strip()}")


def _split_chunks(audio: Path, out_dir: Path, *, chunk_seconds: int) -> list[Path]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(audio),
            "-f",
            "segment",
            "-segment_time",
            str(chunk_seconds),
            "-c",
            "copy",
            "-reset_timestamps",
            "1",
            "-loglevel",
            "error",
            str(out_dir / "chunk_%03d.mp3"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio split failed: {result.stderr.strip()}")
    chunks = sorted(out_dir.glob("chunk_*.mp3"))
    if not chunks:
        raise RuntimeError("ffmpeg did not produce audio chunks")
    return chunks


def _get_duration_seconds(audio: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(audio),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")
    return float(result.stdout.strip())


def _fetch_text(url: str) -> tuple[str, str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "phrasify/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
        content_type = response.headers.get("Content-Type", "")
        final_url = response.geturl()
    charset = _charset_from_content_type(content_type) or "utf-8"
    return raw.decode(charset, errors="replace"), content_type, final_url


def _charset_from_content_type(content_type: str) -> str | None:
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _looks_like_feed(body: str, content_type: str) -> bool:
    lowered = content_type.lower()
    if "xml" in lowered or "rss" in lowered or "atom" in lowered:
        return True
    return body.lstrip().startswith(("<rss", "<?xml", "<feed"))


def _looks_like_audio_url(url: str) -> bool:
    return Path(urllib.parse.urlparse(url).path.lower()).suffix in AUDIO_SUFFIXES


def _episode_from_feed(feed_body: str, *, preferred_url: str, feed_url: str = "") -> dict[str, str]:
    try:
        root = ET.fromstring(feed_body)
    except ET.ParseError as exc:
        raise RuntimeError(f"invalid podcast feed XML: {exc}") from exc

    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    if not items:
        raise RuntimeError("podcast feed has no episodes")

    preferred = _canonical_url(preferred_url)
    chosen = items[0]
    for item in items:
        values = {_canonical_url(v) for v in _episode_match_values(item) if v}
        if preferred in values:
            chosen = item
            break

    title = _child_text(chosen, "title") or _child_text(chosen, "{http://www.w3.org/2005/Atom}title")
    episode_url = _first_nonempty(_episode_match_values(chosen))
    transcript_url = _find_transcript_url(chosen)
    enclosure_url = _find_enclosure_url(chosen)
    return {
        "title": title,
        "episode_url": episode_url,
        "transcript_url": transcript_url,
        "audio_url": enclosure_url,
        "feed_url": feed_url,
    }


def _episode_match_values(item: ET.Element) -> list[str]:
    values = [
        _child_text(item, "link"),
        _child_text(item, "guid"),
        _child_text(item, "{http://www.w3.org/2005/Atom}id"),
    ]
    for link in item.findall("{http://www.w3.org/2005/Atom}link"):
        href = link.attrib.get("href")
        if href:
            values.append(href)
    return [value for value in values if value]


def _find_transcript_url(item: ET.Element) -> str:
    for element in item.iter():
        tag = _local_name(element.tag)
        if tag != "transcript":
            continue
        url = element.attrib.get("url") or element.attrib.get("href") or (element.text or "").strip()
        if url:
            return url
    return ""


def _find_enclosure_url(item: ET.Element) -> str:
    for element in item.iter():
        tag = _local_name(element.tag)
        if tag in {"enclosure", "link"}:
            url = element.attrib.get("url") or element.attrib.get("href")
            media_type = element.attrib.get("type", "")
            if url and (media_type.startswith("audio/") or _looks_like_audio_url(url)):
                return url
    return ""


def _child_text(item: ET.Element, tag: str) -> str:
    child = item.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def _first_nonempty(values: list[str]) -> str:
    return next((value for value in values if value), "")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _canonical_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", parsed.query, "")
    )


def _discover_feed_url(html_body: str, page_url: str) -> str | None:
    pattern = re.compile(
        r"<link\b(?=[^>]*\btype=[\"']application/(?:rss|atom)\+xml[\"'])(?=[^>]*\bhref=[\"']([^\"']+)[\"'])[^>]*>",
        flags=re.IGNORECASE,
    )
    match = pattern.search(html_body)
    if not match:
        return None
    return urllib.parse.urljoin(page_url, html.unescape(match.group(1)))


def _parse_transcript_payload(body: str, content_type: str) -> str:
    lowered = content_type.lower()
    stripped = body.lstrip()
    if "json" in lowered or stripped.startswith(("{", "[")):
        return _parse_json_transcript(body)
    return normalize_transcript_text(body)


def _parse_json_transcript(body: str) -> str:
    payload = json.loads(body)
    if isinstance(payload, dict):
        for key in ("text", "transcript"):
            if isinstance(payload.get(key), str):
                return normalize_transcript_text(payload[key])
        if isinstance(payload.get("segments"), list):
            payload = payload["segments"]
    if isinstance(payload, list):
        lines: list[str] = []
        for item in payload:
            if isinstance(item, dict):
                text = item.get("text") or item.get("body") or item.get("content")
                if text:
                    lines.append(str(text))
            elif isinstance(item, str):
                lines.append(item)
        return normalize_transcript_text("\n".join(lines))
    return normalize_transcript_text(str(payload))


def resolve_spotify_episode(url: str) -> dict[str, str]:
    _require_optional("requests", "bs4", "dateutil")
    import requests  # type: ignore[import-not-found]
    from bs4 import BeautifulSoup  # type: ignore[import-not-found]
    from dateutil import parser as dateparser  # type: ignore[import-not-found]

    episode_id = _extract_spotify_episode_id(url)
    canonical = url.split("?", 1)[0]
    response = requests.get(
        canonical,
        headers={
            "User-Agent": "facebookexternalhit/1.1",
            "Accept-Language": "ja,en;q=0.8",
        },
        timeout=20,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    jsonld = _spotify_jsonld(soup)
    html_title = soup.title.get_text().strip() if soup.title else ""

    title = jsonld.get("name") or _meta(soup, "og:title") or html_title
    title = re.sub(r"\s*\|\s*Podcast on Spotify\s*$", "", title).strip()
    if " - " in title and title == html_title.replace(" | Podcast on Spotify", "").strip():
        title = title.rsplit(" - ", 1)[0].strip()

    show_name = ""
    part_of = jsonld.get("partOfSeries") or jsonld.get("partOfSeason")
    if isinstance(part_of, dict):
        show_name = str(part_of.get("name") or "")
    show_name = show_name or _parse_show_from_title(html_title)
    if not show_name:
        og_desc = _meta(soup, "og:description") or ""
        match = re.search(r"from\s+(.+?)\s+on Spotify", og_desc)
        if match:
            show_name = match.group(1).strip()
        elif "·" in og_desc:
            show_name = og_desc.split("·", 1)[0].strip()

    published_iso = ""
    published = jsonld.get("datePublished") or jsonld.get("uploadDate") or _meta(soup, "music:release_date")
    if published:
        try:
            published_iso = dateparser.parse(str(published)).date().isoformat()
        except (ValueError, TypeError):
            published_iso = ""

    duration_seconds = _iso_duration_to_seconds(str(jsonld.get("duration") or ""))
    music_duration = _meta(soup, "music:duration")
    if duration_seconds is None and music_duration and music_duration.isdigit():
        duration_seconds = int(music_duration)

    if not title or not show_name:
        raise RuntimeError("could not extract Spotify podcast episode title/show metadata")

    return {
        "episode_id": episode_id,
        "url": canonical,
        "title": title,
        "show_name": show_name,
        "published_iso": published_iso,
        "duration_seconds": str(duration_seconds or ""),
    }


def resolve_apple_episode(show_name: str, episode_title: str, *, country: str = "jp") -> dict[str, str] | None:
    _require_optional("requests", "feedparser", "dateutil")
    import feedparser  # type: ignore[import-not-found]
    import requests  # type: ignore[import-not-found]
    from dateutil import parser as dateparser  # type: ignore[import-not-found]

    feed_url = _find_apple_feed_url(show_name, country=country)
    if not feed_url:
        return None
    response = requests.get(feed_url, headers={"User-Agent": "phrasify/0.1"}, timeout=30)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    if not feed.entries:
        return None

    scored = [
        (_token_overlap(episode_title, entry.get("title", "")), entry)
        for entry in feed.entries
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    score, entry = scored[0]
    if score < 0.4:
        return None

    audio_url = ""
    for enclosure in entry.get("enclosures") or []:
        if enclosure.get("url") and (str(enclosure.get("type", "")).startswith("audio") or not enclosure.get("type")):
            audio_url = enclosure["url"]
            break

    published_iso = ""
    if entry.get("published"):
        try:
            published_iso = dateparser.parse(entry["published"]).date().isoformat()
        except (ValueError, TypeError):
            published_iso = ""
    return {
        "feed_url": feed_url,
        "show_name": str(feed.feed.get("title", show_name)),
        "title": str(entry.get("title", episode_title)),
        "audio_url": audio_url,
        "episode_url": str(entry.get("link", "")),
        "published_iso": published_iso,
    }


def _find_apple_feed_url(show_name: str, *, country: str) -> str | None:
    import requests  # type: ignore[import-not-found]

    response = requests.get(
        "https://itunes.apple.com/search",
        params={"term": show_name, "entity": "podcast", "limit": 5, "country": country},
        headers={"User-Agent": "phrasify/0.1"},
        timeout=15,
    )
    response.raise_for_status()
    scored = [
        (item.get("feedUrl"), _token_overlap(show_name, item.get("collectionName", "")))
        for item in response.json().get("results", [])
        if item.get("feedUrl")
    ]
    if not scored:
        return None
    scored.sort(key=lambda item: item[1], reverse=True)
    feed_url, score = scored[0]
    return str(feed_url) if score >= 0.3 else None


def find_youtube_episode_captions(
    show_name: str,
    episode_title: str,
    *,
    languages: tuple[str, ...],
    duration_hint_seconds: int | None = None,
    min_score: float = 0.4,
) -> RemoteTranscript | None:
    yt_dlp = shutil.which("yt-dlp")
    if yt_dlp is None:
        return None
    query = f"{show_name} {episode_title}".strip()
    result = subprocess.run(
        [
            yt_dlp,
            f"ytsearch5:{query}",
            "--skip-download",
            "--print",
            '{"id":"%(id)s","title":"%(title)s","channel":"%(channel)s","duration":%(duration)s}',
            "--no-warnings",
            "--quiet",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        return None

    candidates: list[tuple[float, dict[str, Any]]] = []
    for line in result.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        score = _token_overlap(episode_title, item.get("title", ""))
        if show_name and (
            _token_overlap(show_name, item.get("title", "")) > 0.5
            or _token_overlap(show_name, item.get("channel", "")) > 0.5
        ):
            score += 0.15
        duration = item.get("duration")
        if duration_hint_seconds and isinstance(duration, (int, float)) and duration > 0:
            ratio = duration / duration_hint_seconds
            if ratio < 0.7 or ratio > 1.3:
                score -= 0.2
        candidates.append((score, item))

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    for score, item in candidates:
        if score < min_score or not item.get("id"):
            break
        try:
            transcript = load_youtube_captions(str(item["id"]), languages=languages)
        except RuntimeError:
            continue
        return RemoteTranscript(
            url=transcript.url,
            title=episode_title,
            text=transcript.text,
            source_type="podcast",
            transcript_source="youtube-captions",
            metadata={
                **transcript.metadata,
                "youtube_title": str(item.get("title", "")),
                "youtube_channel": str(item.get("channel", "")),
                "youtube_match_score": f"{score:.3f}",
                "show_name": show_name,
            },
        )
    return None


def write_remote_transcript(remote: RemoteTranscript, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = resolve_unique_path(directory / f"{sanitize_stem(remote.title)}.md")
    metadata = {
        "title": remote.title,
        "source_url": remote.url,
        "source_type": remote.source_type,
        "transcript_source": remote.transcript_source,
        **{k: v for k, v in remote.metadata.items() if v},
    }
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {_yaml_quote(value)}")
    lines.extend(["---", "", "## Transcript", "", remote.text.strip(), ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _extract_spotify_episode_id(url: str) -> str:
    match = re.search(r"open\.spotify\.com/(?:intl-[a-z]{2}/)?episode/([A-Za-z0-9]+)", url)
    if not match:
        raise ValueError(f"could not extract Spotify episode id from URL: {url}")
    return match.group(1)


def _spotify_jsonld(soup: Any) -> dict[str, Any]:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("@type") in {
                "PodcastEpisode",
                "Episode",
                "AudioObject",
            }:
                return candidate
    return {}


def _meta(soup: Any, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    if tag and tag.get("content"):
        return str(tag["content"]).strip()
    return None


def _parse_show_from_title(html_title: str) -> str:
    cleaned = re.sub(r"\s*\|\s*Podcast on Spotify\s*$", "", html_title).strip()
    if " - " in cleaned:
        return cleaned.rsplit(" - ", 1)[-1].strip()
    return ""


def _iso_duration_to_seconds(value: str) -> int | None:
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return None
    hours, minutes, seconds = (int(part) if part else 0 for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def _normalize_for_match(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"[\s\-_:：・。、,.!?！？\"'\[\]()「」『』【】#]", "", value)


def _token_overlap(left: str, right: str) -> float:
    a = _normalize_for_match(left)
    b = _normalize_for_match(right)
    if not a or not b:
        return 0.0
    if a == b or a in b or b in a:
        return 1.0
    grams_a = {a[i : i + 2] for i in range(len(a) - 1)}
    grams_b = {b[i : i + 2] for i in range(len(b) - 1)}
    if not grams_a or not grams_b:
        return 0.0
    return len(grams_a & grams_b) / len(grams_a | grams_b)


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _require_optional(*packages: str) -> None:
    import importlib.util

    missing = [package for package in packages if importlib.util.find_spec(package) is None]
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(
            f"podcast URL support requires optional dependencies ({names}); "
            "install with: pip install 'phrasify[media]'"
        )


def _yaml_quote(value: str) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


_LANG_NAME_TO_ISO = {
    "english": "en",
    "japanese": "ja",
    "spanish": "es",
    "chinese": "zh",
    "mandarin": "zh",
    "french": "fr",
    "german": "de",
    "korean": "ko",
    "italian": "it",
    "portuguese": "pt",
    "russian": "ru",
}


def _to_iso639_1(lang: str) -> str:
    if not lang:
        return "unknown"
    lowered = lang.strip().lower()
    if len(lowered) == 2 and lowered.isalpha():
        return lowered
    return _LANG_NAME_TO_ISO.get(lowered, lowered[:2] if lowered else "unknown")


def _title_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    stem = Path(parsed.path.rstrip("/")).stem
    return stem or parsed.netloc

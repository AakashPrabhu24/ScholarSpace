import json
import re
import time

import httpx
import requests
import wikipedia
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_not_required, login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import generic
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from youtubesearchpython import VideosSearch

from .forms import *
from .forms import DashboardForm

User = get_user_model()

# ---- Begin Monkey-Patch for youtube-search-python ----
from youtubesearchpython.core import requests as yt_requests
from youtubesearchpython.core.search import SearchCore
from youtubesearchpython.handlers.componenthandler import ComponentHandler


def patched_syncPostRequest(self):
    # Call httpx.post() without passing the unsupported 'proxies' parameter.
    return httpx.post(self.url, headers=self.headers, json=self.data, timeout=None)


yt_requests.syncPostRequest = patched_syncPostRequest


def patched_getVideoComponent(self, element: dict, shelfTitle: str = None) -> dict:
    # Use the constant from the class if available, else default to 'videoRenderer'
    video_key = getattr(self, "videoElementKey", "videoRenderer")
    video = element.get(video_key)
    if not video:
        return None
    component = {
        "type": "video",
        "id": self._getValue(video, ["videoId"]),
        "title": self._getValue(video, ["title", "runs", 0, "text"]),
        "publishedTime": self._getValue(video, ["publishedTimeText", "simpleText"]),
        "duration": self._getValue(video, ["lengthText", "simpleText"]),
        "viewCount": {
            "text": self._getValue(video, ["viewCountText", "simpleText"]),
            "short": self._getValue(video, ["shortViewCountText", "simpleText"]),
        },
        "thumbnails": self._getValue(video, ["thumbnail", "thumbnails"]),
        "richThumbnail": self._getValue(
            video,
            [
                "richThumbnail",
                "movingThumbnailRenderer",
                "movingThumbnailDetails",
                "thumbnails",
                0,
            ],
        ),
        "descriptionSnippet": self._getValue(
            video, ["detailedMetadataSnippets", 0, "snippetText", "runs"]
        ),
        "channel": {
            "name": self._getValue(video, ["ownerText", "runs", 0, "text"]),
            "id": self._getValue(
                video,
                [
                    "ownerText",
                    "runs",
                    0,
                    "navigationEndpoint",
                    "browseEndpoint",
                    "browseId",
                ],
            ),
            "thumbnails": self._getValue(
                video,
                [
                    "channelThumbnailSupportedRenderers",
                    "channelThumbnailWithLinkRenderer",
                    "thumbnail",
                    "thumbnails",
                ],
            ),
        },
        "accessibility": {
            "title": self._getValue(
                video, ["title", "accessibility", "accessibilityData", "label"]
            ),
            "duration": self._getValue(
                video, ["lengthText", "accessibility", "accessibilityData", "label"]
            ),
        },
    }

    # Fix: Safely concatenate strings by checking for None
    if component.get("id"):
        component["link"] = "https://www.youtube.com/watch?v=" + str(component["id"])
    else:
        component["link"] = None

    if component.get("channel") and component["channel"].get("id"):
        component["channel"]["link"] = "https://www.youtube.com/channel/" + str(
            component["channel"]["id"]
        )
    else:
        if "channel" in component:
            component["channel"]["link"] = None

    component["shelfTitle"] = shelfTitle
    return component


# Apply the patch to both the base class and the core search class
ComponentHandler._getVideoComponent = patched_getVideoComponent
SearchCore._getVideoComponent = patched_getVideoComponent

_original_getComponents = SearchCore._getComponents


def patched_getComponents(self, findVideos, findChannels, findPlaylists):
    # Library iterates `self.responseSource` without guarding None when YouTube's
    # response shape omits itemSection contents on the first request.
    if self.responseSource is None:
        self.responseSource = []
    return _original_getComponents(self, findVideos, findChannels, findPlaylists)


SearchCore._getComponents = patched_getComponents

_original_getShelfComponent = ComponentHandler._getShelfComponent


def patched_getShelfComponent(self, element: dict) -> dict:
    out = _original_getShelfComponent(self, element)
    if out.get("elements") is None:
        out = {**out, "elements": []}
    return out


ComponentHandler._getShelfComponent = patched_getShelfComponent
# ---- End Monkey-Patch ----


# Helper: Return the current user if authenticated; otherwise, return the default user.
def get_user(request):
    if request.user.is_authenticated:
        return request.user
    try:
        # Try to get the user with pk=1.
        return User.objects.get(pk=1)
    except User.DoesNotExist:
        # If no default user exists, create one.
        guest = User.objects.create(username="guest")
        return guest


def home(request):
    """Public marketing page at /. Logged-in users are sent to the app dashboard."""
    if request.user.is_authenticated:
        return redirect("dashboard_home")
    return render(request, "dashboard/landing.html")


def public_landing(request):
    """Public marketing page; always shows landing.html (no redirect if user is logged in)."""
    return render(request, "dashboard/landing.html")


@login_not_required
@csrf_protect
@never_cache
@require_http_methods(["GET", "POST", "OPTIONS"])
def site_logout(request):
    """Always end the session and redirect — avoids LogoutView GET showing Django's logged-out template."""
    auth_logout(request)
    return redirect("public_landing")


@login_required
def dashboard_home(request):
    """Logged-in dashboard (Your Learning Hub). Not used for anonymous visitors."""
    return render(request, "dashboard/home.html")


def _calendar_event_preview(ev):
    from datetime import datetime

    title = (ev.get("summary") or "").strip() or "(No title)"
    start = ev.get("start") or {}
    when = ""
    if start.get("dateTime"):
        raw = start["dateTime"].replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
            when = dt.strftime("%b %d • %I:%M %p")
        except ValueError:
            when = start["dateTime"][:16]
    elif start.get("date"):
        when = start["date"]
    return {"title": title, "when": when}


@login_required
def google_calendar(request):
    """
    ScholarSpace calendar hub: full Google Calendar embed + server-side Calendar API for sidebar
    (API key stays on the server only).
    """
    import urllib.parse
    from django.utils import timezone
    from manage_work.models import GoogleCalendarSync

    key = (getattr(settings, "GOOGLE_CALENDAR_API_KEY", None) or "").strip()
    calendar_id = (
        getattr(settings, "GOOGLE_CALENDAR_PUBLIC_CALENDAR_ID", None) or ""
    ).strip()
    events = []
    api_error = None

    cid_encoded = urllib.parse.quote(calendar_id, safe="")
    # Rich embed: month view, nav, tabs (user can switch week/day inside Google’s UI)
    iframe_src = (
        f"https://calendar.google.com/calendar/embed?src={cid_encoded}"
        f"&mode=MONTH&wkst=1&bgcolor=%23fbf8fe&ctz=UTC"
        f"&showTitle=0&showNav=1&showDate=1&showPrint=1&showTabs=1&showCalendars=1&showTz=1&hl=en"
    )

    if key:
        try:
            time_min = timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            api_url = (
                f"https://www.googleapis.com/calendar/v3/calendars/{cid_encoded}/events"
                f"?key={urllib.parse.quote(key, safe='')}"
                f"&maxResults=25&orderBy=startTime&singleEvents=true"
                f"&timeMin={urllib.parse.quote(time_min)}"
            )
            resp = requests.get(api_url, timeout=20)
            if resp.status_code == 200:
                events = (resp.json() or {}).get("items") or []
            else:
                api_error = f"Calendar API returned {resp.status_code}."
        except requests.RequestException as exc:
            api_error = str(exc)

    now = timezone.now()
    event_previews = [_calendar_event_preview(e) for e in events[:8]]

    return render(
        request,
        "dashboard/google_calendar.html",
        {
            "iframe_src": iframe_src,
            "events": events,
            "event_previews": event_previews,
            "api_error": api_error,
            "has_api_key": bool(key),
            "calendar_id": calendar_id,
            "month_year": now.strftime("%B %Y"),
            "google_calendar_connected": GoogleCalendarSync.objects.filter(user=request.user).exists(),
        },
    )


from .forms import NotesForm
from .models import Notes


@login_required
def notes(request):
    # Check if it's a POST request (form submission)
    if request.method == "POST":
        form = NotesForm(request.POST, request.FILES)
        if form.is_valid():
            # Save the note with the current logged-in user
            notes = form.save(commit=False)
            notes.user = request.user
            notes.save()
            messages.success(request, "Note Added Successfully!")
            from .models import push_notification
            push_notification(
                request.user, 'Note Added',
                f'New note "{request.POST["title"]}" has been saved.',
                notif_type='notes', icon='note_alt', link='/notes/'
            )
            return redirect("notes")
    else:
        # If it's a GET request, create a new form
        form = NotesForm()

    # Get all notes for the current user
    notes = Notes.objects.filter(user=request.user)
    return render(request, "dashboard/notes.html", {"notes": notes, "form": form})


from django.shortcuts import get_object_or_404, render

from .models import Notes


@login_required
def notes_detail(request, pk):
    notes = get_object_or_404(Notes, pk=pk, user=request.user)

    # Detailed Logging
    print(f"PDF File Exists: {bool(notes.pdf_file)}")
    print(f"PDF File Name: {notes.pdf_file.name}")
    print(f"PDF File URL: {notes.pdf_file.url}")
    print(f"PDF File Path: {notes.pdf_file.path}")

    return render(request, "dashboard/notes_detail.html", {"notes": notes})


def delete_note(request, pk=None):
    Notes.objects.get(id=pk).delete()
    return redirect("notes")


class NotesDetailView(generic.DetailView):
    model = Notes


def homework(request):
    user = get_user(request)
    if request.method == "POST":
        form = HomeworkForm(request.POST)
        if form.is_valid():
            try:
                finished = request.POST["is_finished"]
                finished = True if finished == "on" else False
            except:
                finished = False
            hw = Homework(
                user=user,
                subject=request.POST["subject"],
                title=request.POST["title"],
                description=request.POST["description"],
                due=request.POST["due"],
                is_finished=finished,
            )
            hw.save()
            messages.success(request, f"Homework Added from {user.username}!!")
            from .models import push_notification
            push_notification(
                user, "Homework Added",
                "New homework added.",
                notif_type="homework", icon="assignment", link="/homework"
            )
    else:
        form = HomeworkForm()
    homework_qs = Homework.objects.filter(user=user)
    homework_done = True if len(homework_qs) == 0 else False
    context = {"homeworks": homework_qs, "homeworks_done": homework_done, "form": form}
    return render(request, "dashboard/homework.html", context)


def update_homework(request, pk=None):
    hw = Homework.objects.get(id=pk)
    hw.is_finished = not hw.is_finished
    hw.save()
    return redirect("homework")


def delete_homework(request, pk=None):
    Homework.objects.get(id=pk).delete()
    return redirect("homework")


_YOUTUBE_VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{6,32}$")


def youtube_video_id_from_result(link, api_id=None):
    """Resolve YouTube video id from API id or watch URL."""
    if api_id and isinstance(api_id, str):
        vid = api_id.strip()
        if _YOUTUBE_VIDEO_ID_RE.match(vid):
            return vid
    if not link or not isinstance(link, str):
        return None
    from urllib.parse import parse_qs, urlparse

    link = link.strip()
    if "youtu.be/" in link:
        part = link.split("youtu.be/", 1)[-1]
        vid = part.split("?")[0].split("/")[0]
        return vid if _YOUTUBE_VIDEO_ID_RE.match(vid) else None
    try:
        parsed = urlparse(link)
        host = (parsed.netloc or "").lower()
        if "youtube.com" not in host and "youtube-nocookie.com" not in host:
            return None
        if parsed.path.startswith("/watch"):
            v = (parse_qs(parsed.query).get("v") or [None])[0]
            return v if v and _YOUTUBE_VIDEO_ID_RE.match(v) else None
        for prefix in ("/embed/", "/shorts/", "/live/"):
            if prefix in parsed.path:
                vid = parsed.path.split(prefix, 1)[-1].split("?")[0]
                return vid if _YOUTUBE_VIDEO_ID_RE.match(vid) else None
    except (ValueError, TypeError, IndexError):
        pass
    return None


def youtube_watch(request, video_id):
    """In-site player: YouTube embed iframe + metadata via oEmbed (no API key)."""
    if not _YOUTUBE_VIDEO_ID_RE.match(video_id):
        from django.http import HttpResponseBadRequest

        return HttpResponseBadRequest("Invalid video id")

    from_q = (request.GET.get("from_q") or "").strip()
    embed_url = (
        f"https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1&playsinline=1"
    )
    meta_title = ""
    meta_author = ""
    oembed_error = None
    try:
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        r = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": watch_url, "format": "json"},
            timeout=12,
        )
        if r.status_code == 200:
            data = r.json()
            meta_title = (data.get("title") or "").strip()
            meta_author = (data.get("author_name") or "").strip()
        else:
            oembed_error = "Could not load video details."
    except requests.RequestException:
        oembed_error = "Could not load video details."

    from urllib.parse import urlencode

    back_url = reverse("youtube")
    if from_q:
        back_url = f"{back_url}?{urlencode({'q': from_q})}"

    return render(
        request,
        "dashboard/youtube_watch.html",
        {
            "video_id": video_id,
            "embed_url": embed_url,
            "meta_title": meta_title,
            "meta_author": meta_author,
            "oembed_error": oembed_error,
            "from_q": from_q,
            "back_url": back_url,
            "watch_on_youtube": f"https://www.youtube.com/watch?v={video_id}",
        },
    )


def youtube(request):
    form = DashboardForm(request.POST) if request.method == "POST" else DashboardForm()
    result_list = []
    search_query = ""
    search_error = None

    text = ""
    if request.method == "POST":
        text = (request.POST.get("text") or "").strip()
    else:
        text = (request.GET.get("q") or "").strip()

    if text:
        search_query = text
        try:
            video = VideosSearch(text, limit=12)
            raw = (video.result() or {}).get("result")
            if not isinstance(raw, list):
                raw = []
            for i in raw:
                if i is None:
                    continue
                thumbs = i.get("thumbnails") or []
                if not isinstance(thumbs, list):
                    thumbs = []
                thumb_url = thumbs[0].get("url", "") if thumbs else ""
                channel = (i.get("channel") or {}).get("name", "") or ""
                views = (i.get("viewCount") or {}).get("short", "") or ""
                desc = ""
                snippet = i.get("descriptionSnippet")
                if snippet is None:
                    snippet_parts = []
                elif isinstance(snippet, list):
                    snippet_parts = snippet
                elif isinstance(snippet, dict):
                    snippet_parts = [snippet]
                else:
                    snippet_parts = []
                for j in snippet_parts:
                    if isinstance(j, dict) and j.get("text"):
                        desc += j["text"]
                vid = youtube_video_id_from_result(i.get("link", ""), i.get("id"))
                result_list.append(
                    {
                        "title": i.get("title", ""),
                        "duration": i.get("duration", "") or "—",
                        "thumbnail": thumb_url,
                        "channel": channel,
                        "link": i.get("link", "#"),
                        "views": views,
                        "published": i.get("publishedTime", ""),
                        "description": desc,
                        "video_id": vid,
                    }
                )
        except Exception as exc:
            search_error = "Search could not be completed. Try again in a moment."
            if settings.DEBUG:
                search_error = f"{search_error} ({exc})"

    return render(
        request,
        "dashboard/youtube.html",
        {
            "form": form,
            "results": result_list,
            "search_query": search_query,
            "search_error": search_error,
        },
    )


def todo(request):
    if request.method == "POST":
        form = TodoForm(request.POST)
        if form.is_valid():
            try:
                finished = request.POST["is_finished"]
                if finished == "on":
                    finished = True
                else:
                    finished = False
            except:
                finished = False
            todos = Todo(
                user=request.user, title=request.POST["title"], is_finished=finished
            )
            todos.save()
            messages.success(request, f"Todo Added from {request.user.username}!!")
            from .models import push_notification
            push_notification(
                request.user, "Goal Added",
                f"New goal added successfully.",
                notif_type="todo", icon="ads_click", link="/todo"
            )
    else:
        form = TodoForm()
    todo = Todo.objects.filter(user=request.user)
    if len(todo) == 0:
        todos_done = True
    else:
        todos_done = False
    context = {"form": form, "todos": todo, "todo_done": todos_done}
    return render(request, "dashboard/todo.html", context)


def update_todo(request, pk=None):
    todo = Todo.objects.get(id=pk)
    if todo.is_finished == True:
        todo.is_finished = False
    else:
        todo.is_finished = True
    todo.save()
    return redirect("todo")


def delete_todo(request, pk=None):
    Todo.objects.get(id=pk).delete()
    return redirect("todo")


def _volume_to_book_result(vi):
    """Build one result dict from Google Books volumeInfo (or None if unusable)."""
    if not vi or not isinstance(vi, dict):
        return None
    image_links = vi.get("imageLinks") or {}
    thumb = image_links.get("thumbnail") or image_links.get("smallThumbnail") or ""
    if thumb:
        thumb = thumb.replace("http:", "https:", 1)
    cats = vi.get("categories")
    if cats is None:
        cats = []
    elif not isinstance(cats, list):
        cats = [str(cats)]
    authors = vi.get("authors") or []
    if isinstance(authors, list):
        authors_str = ", ".join(authors[:5])
    else:
        authors_str = str(authors)
    subtitle = (vi.get("subtitle") or "").strip()
    if not subtitle and authors_str:
        subtitle = authors_str
    return {
        "title": vi.get("title") or "Untitled",
        "subtitle": subtitle,
        "description": (vi.get("description") or "")[:400],
        "count": vi.get("pageCount"),
        "categories": cats,
        "rating": vi.get("averageRating"),
        "thumbnail": thumb,
        "preview": vi.get("previewLink") or vi.get("infoLink") or "#",
    }


# Plain browser UA only: Open Library returns 429 for custom product tokens in User-Agent.
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _google_books_fetch_volumes(search_q, api_key):
    """
    Return (list of raw volume dicts, error_message_or_none).
    Uses optional API key for quota; handles JSON error bodies and rate limits.
    """
    api_url = "https://www.googleapis.com/books/v1/volumes"
    all_items = []
    last_err = None
    try:
        for start_index in (0, 40):
            params = {"q": search_q, "maxResults": 40, "startIndex": start_index}
            if api_key:
                params["key"] = api_key
            r = requests.get(api_url, params=params, timeout=25, headers=_HTTP_HEADERS)
            if r.status_code == 429:
                last_err = (
                    "Google Books is rate-limiting requests. Results may use Open Library below, "
                    "or add a Books API key (see project settings / google_books_api_key.txt)."
                )
                break
            if r.status_code != 200:
                last_err = f"Google Books could not complete the search (HTTP {r.status_code})."
                break
            try:
                payload = r.json()
            except ValueError:
                last_err = "Google Books returned an invalid response."
                break
            err = payload.get("error")
            if isinstance(err, dict):
                msg = (err.get("message") or "API error").strip()
                code = err.get("code", "")
                last_err = f"Google Books: {msg}" + (f" ({code})" if code else "")
                break
            batch = payload.get("items")
            if not batch:
                break
            if not isinstance(batch, list):
                break
            all_items.extend(batch)
            try:
                total = int(payload.get("totalItems") or 0)
            except (TypeError, ValueError):
                total = 0
            if len(batch) < 40 or (total and start_index + len(batch) >= total):
                break
    except requests.RequestException:
        last_err = "Could not reach Google Books. Check your network connection."
    return all_items, last_err


def _openlibrary_doc_to_result(doc):
    if not isinstance(doc, dict):
        return None
    title = doc.get("title")
    if isinstance(title, list):
        title = (title[0] or "Untitled").strip() if title else "Untitled"
    elif isinstance(title, str):
        title = title.strip() or "Untitled"
    else:
        title = "Untitled"
    authors = doc.get("author_name") or []
    if isinstance(authors, list):
        sub = ", ".join(str(a) for a in authors[:6])
    else:
        sub = str(authors) if authors else ""
    year = doc.get("first_publish_year")
    desc = ""
    if year:
        desc = f"First published {year}."
    cover_i = doc.get("cover_i")
    thumb = f"https://covers.openlibrary.org/b/id/{cover_i}-M.jpg" if cover_i else ""
    key = (doc.get("key") or "").strip()
    if key.startswith("/"):
        preview = f"https://openlibrary.org{key}"
    elif key:
        preview = f"https://openlibrary.org/{key}"
    else:
        preview = "https://openlibrary.org/"
    cats = ["Open Library"] if not doc.get("subject") else []
    if isinstance(doc.get("subject"), list) and doc["subject"]:
        cats = [str(doc["subject"][0])]
    return {
        "title": title,
        "subtitle": sub,
        "description": desc,
        "count": None,
        "categories": cats,
        "rating": None,
        "thumbnail": thumb,
        "preview": preview,
    }


def _openlibrary_search(search_q):
    docs = []
    for attempt in range(2):
        try:
            r = requests.get(
                "https://openlibrary.org/search.json",
                params={"q": search_q, "limit": 50},
                timeout=25,
                headers=_HTTP_HEADERS,
            )
            if r.status_code == 429 and attempt == 0:
                time.sleep(1.2)
                continue
            if r.status_code != 200:
                return []
            data = r.json()
            docs = data.get("docs") or []
            if not isinstance(docs, list):
                return []
            break
        except (requests.RequestException, ValueError, TypeError):
            return []
    return docs


def _parse_google_volume_items(google_items):
    result_list = []
    for raw in google_items:
        try:
            if not isinstance(raw, dict):
                continue
            vi = raw.get("volumeInfo")
            row = _volume_to_book_result(vi)
            if row:
                result_list.append(row)
        except (TypeError, ValueError, AttributeError):
            continue
    return result_list


def _books_search_single_query(search_q, api_key):
    """Google Books volumes + Open Library fallback. Returns (rows, google_error)."""
    google_items, g_err = _google_books_fetch_volumes(search_q, api_key)
    rows = _parse_google_volume_items(google_items)
    if rows:
        return rows, g_err
    for doc in _openlibrary_search(search_q):
        row = _openlibrary_doc_to_result(doc)
        if row:
            rows.append(row)
    return rows, g_err


def _common_prefix_len(a, b):
    a, b = (a or "").lower(), (b or "").lower()
    n = 0
    for c1, c2 in zip(a, b):
        if c1 != c2:
            break
        n += 1
    return n


def _lev_dist(s1, s2):
    s1, s2 = s1.lower(), s2.lower()
    if len(s1) < len(s2):
        return _lev_dist(s2, s1)
    if not s2:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        cur = [i + 1]
        for j, c2 in enumerate(s2):
            cur.append(min(prev[j + 1] + 1, cur[j] + 1, prev[j] + (c1 != c2)))
        prev = cur
    return prev[-1]


def _datamuse_typo_suggestion(term):
    """
    Suggest a corrected single token: Datamuse wildcard by last 3 letters, then
    pick the closest word by edit distance (so 'ptyhon' -> 'python', not 'archon').
    """
    term = (term or "").strip().lower()
    if len(term) < 4 or " " in term:
        return ""
    suf = term[-3:]
    pattern = f"*{suf}"
    try:
        r = requests.get(
            "https://api.datamuse.com/words",
            params={"sp": pattern, "max": 40},
            timeout=10,
            headers=_HTTP_HEADERS,
        )
        if r.status_code != 200:
            return ""
        data = r.json()
        if not isinstance(data, list):
            return ""
        candidates = []
        for row in data:
            if not isinstance(row, dict):
                continue
            w = (row.get("word") or "").strip()
            if not w or w.lower() == term or " " in w:
                continue
            dm = int(row.get("score", 0) or 0)
            candidates.append((w, dm))
        if not candidates:
            return ""
        best_word = ""
        best_dist = 99
        best_len_diff = 99
        best_pref = -1
        best_score = -1
        for w, dm in candidates:
            if abs(len(w) - len(term)) > 3:
                continue
            d = _lev_dist(term, w)
            len_diff = abs(len(w) - len(term))
            pref = _common_prefix_len(term, w)
            if d < best_dist or (
                d == best_dist
                and (
                    len_diff < best_len_diff
                    or (
                        len_diff == best_len_diff
                        and (
                            pref > best_pref or (pref == best_pref and dm > best_score)
                        )
                    )
                )
            ):
                best_dist = d
                best_word = w
                best_len_diff = len_diff
                best_pref = pref
                best_score = dm
        if best_dist <= 3 and best_word:
            return best_word
        return ""
    except (requests.RequestException, ValueError, TypeError):
        return ""


def books(request):
    search_q = ""
    if request.method == "POST":
        form = DashboardForm(request.POST)
        if form.is_valid():
            search_q = (form.cleaned_data.get("text") or "").strip()
        else:
            search_q = (request.POST.get("text") or "").strip()
    else:
        search_q = (request.GET.get("q") or "").strip()
        form = DashboardForm(initial={"text": search_q})

    result_list = []
    books_api_error = None
    books_source = None
    books_did_you_mean = None

    if search_q:
        api_key = (getattr(settings, "GOOGLE_BOOKS_API_KEY", None) or "").strip()
        result_list, g_err = _books_search_single_query(search_q, api_key)

        if not result_list:
            alt = _datamuse_typo_suggestion(search_q)
            if alt:
                retry_rows, g_err2 = _books_search_single_query(alt, api_key)
                if retry_rows:
                    result_list = retry_rows
                    books_did_you_mean = alt
                    g_err = g_err2

        if result_list:
            preview0 = result_list[0].get("preview") or ""
            books_source = "openlibrary" if "openlibrary.org" in preview0 else "google"
        elif g_err:
            books_api_error = g_err

    return render(
        request,
        "dashboard/books.html",
        {
            "form": form,
            "results": result_list,
            "search_query": search_q,
            "books_api_error": books_api_error,
            "books_source": books_source,
            "books_did_you_mean": books_did_you_mean,
        },
    )


import requests
from django.shortcuts import render

from .forms import DashboardForm  # Adjust the import if needed


@login_required
def dictionary(request):
    if request.method == "POST":
        form = DashboardForm(request.POST)
        text = request.POST.get("text", "")
        url = "https://api.dictionaryapi.dev/api/v2/entries/en_US/" + text
        r = requests.get(url)
        data = r.json()
        try:
            # Extract phonetic text and audio URL
            phonetic_text = ""
            audio_url = ""
            for phonetic in data[0].get("phonetics", []):
                if not phonetic_text and phonetic.get("text"):
                    phonetic_text = phonetic["text"]
                if phonetic.get("audio"):
                    audio_url = phonetic["audio"]
                    if audio_url:
                        break

            # Get the first available definition and example (if any)
            definition = ""
            example = ""
            for meaning in data[0].get("meanings", []):
                for d in meaning.get("definitions", []):
                    if (d.get("definition") or d.get("example")) and not (
                        definition or example
                    ):
                        definition = d.get("definition", "")
                        example = d.get("example", "")
                        break
                if definition or example:
                    break

            # Set default messages if fields are empty
            if not definition:
                definition = "No definition available."
            if not example:
                example = "No example available."

            # Gather synonyms from every definition and meaning level
            synonyms = []
            for meaning in data[0].get("meanings", []):
                # synonyms from definitions
                for d in meaning.get("definitions", []):
                    if d.get("synonyms"):
                        synonyms.extend(d.get("synonyms"))
                # synonyms provided at the meaning level (if any)
                if meaning.get("synonyms"):
                    synonyms.extend(meaning.get("synonyms"))
            # Remove duplicates
            synonyms = list(set(synonyms))
            if not synonyms:
                synonyms = ["No synonyms available."]

            context = {
                "form": form,
                "input": text,
                "phonetics": phonetic_text,
                "audio": audio_url,
                "definition": definition,
                "example": example,
                "synonyms": synonyms,
            }
        except Exception as e:
            context = {"form": form, "input": "", "error": str(e)}
        return render(request, "dashboard/dictionary.html", context)
    else:
        form = DashboardForm()
        context = {
            "form": form,
            "suggestion_words": ["Ephemeral", "Serendipity", "Melancholy", "Perspicacious", "Eloquent", "Resilience"]
        }
    return render(request, "dashboard/dictionary.html", context)


def wiki(request):
    if request.method != "POST":
        return render(request, "dashboard/wiki.html", {"form": DashboardForm()})

    text = request.POST.get("text", "").strip()
    form = DashboardForm(request.POST)

    if not text:
        return render(request, "dashboard/wiki.html", {"form": form})

    # ── Step 1: Run a search first so we always have suggestions ─────────────
    search_results = []
    try:
        search_results = wikipedia.search(text, results=8)
    except Exception:
        pass

    page = None
    page_error = None

    # ── Step 2: Try direct page lookup (auto_suggest handles minor typos) ────
    try:
        page = wikipedia.page(text, auto_suggest=True)
    except wikipedia.exceptions.DisambiguationError as e:
        # Ambiguous term — pick the first concrete option automatically
        for option in e.options[:4]:
            try:
                page = wikipedia.page(option, auto_suggest=False)
                break
            except Exception:
                continue
        if not page:
            page_error = (
                f'"{text}" matches multiple Wikipedia topics. "'
                f"Showing results for the closest match below."
            )
    except wikipedia.exceptions.PageError:
        page_error = f'No exact Wikipedia page matched "{text}".'
    except Exception as exc:
        page_error = str(exc)

    # ── Step 3: Fall back to top search result when direct lookup fails ──────
    if not page and search_results:
        for result in search_results[:4]:
            try:
                page = wikipedia.page(result, auto_suggest=False)
                break
            except wikipedia.exceptions.DisambiguationError as e:
                try:
                    page = wikipedia.page(e.options[0], auto_suggest=False)
                    break
                except Exception:
                    continue
            except Exception:
                continue

    # ── Build context ─────────────────────────────────────────────────────────
    if page:
        # Filter suggestions: remove the page we already found
        suggestions = [
            r for r in search_results
            if r.strip().lower() != page.title.strip().lower()
        ][:6]
        context = {
            "form": form,
            "title":       page.title,
            "link":        page.url,
            "details":     page.summary,
            "suggestions": suggestions,
        }
    else:
        context = {
            "form": form,
            "error":       page_error or f'No Wikipedia page found for "{text}".',
            "suggestions": search_results[:6],
        }

    return render(request, "dashboard/wiki.html", context)


def conversion(request):
    if request.method == "POST":
        form = ConversionForm(request.POST)
        measurement = request.POST.get("measurement")

        # Length Conversion (existing logic)
        if measurement == "length":
            measurement_form = ConversionLengthForm()
            user_input_str = request.POST.get("input", "").strip()
            if user_input_str:
                try:
                    user_input_val = float(user_input_str)
                    first = request.POST["measure1"]
                    second = request.POST["measure2"]
                    if first == "yard" and second == "foot":
                        answer = f"{user_input_val} yard = {user_input_val * 3} foot"
                    elif first == "foot" and second == "yard":
                        answer = f"{user_input_val} foot = {user_input_val / 3} yard"
                    else:
                        answer = "Conversion not supported."
                except ValueError:
                    answer = "Invalid input number."
            else:
                answer = "Please enter a number."
            context = {
                "form": form,
                "m_form": measurement_form,
                "input": True,
                "answer": answer,
            }

        # Mass Conversion (existing logic)
        elif measurement == "mass":
            measurement_form = ConversionMassForm()
            user_input_str = request.POST.get("input", "").strip()
            if user_input_str:
                try:
                    user_input_val = float(user_input_str)
                    first = request.POST["measure1"]
                    second = request.POST["measure2"]
                    if first == "pound" and second == "kilogram":
                        answer = f"{user_input_val} pound = {user_input_val * 0.453592} kilogram"
                    elif first == "kilogram" and second == "pound":
                        answer = f"{user_input_val} kilogram = {user_input_val * 2.20462} pound"
                    else:
                        answer = "Conversion not supported."
                except ValueError:
                    answer = "Invalid input number."
            else:
                answer = "Please enter a number."
            context = {
                "form": form,
                "m_form": measurement_form,
                "input": True,
                "answer": answer,
            }

        # Time Conversion
        elif measurement == "time":
            measurement_form = ConversionTimeForm()
            user_input_str = request.POST.get("input", "").strip()
            if user_input_str:
                try:
                    user_input_val = float(user_input_str)
                    first = request.POST["measure1"]
                    second = request.POST["measure2"]
                    if first == "second" and second == "minute":
                        answer = (
                            f"{user_input_val} seconds = {user_input_val / 60} minutes"
                        )
                    elif first == "minute" and second == "second":
                        answer = (
                            f"{user_input_val} minutes = {user_input_val * 60} seconds"
                        )
                    elif first == "second" and second == "hour":
                        answer = (
                            f"{user_input_val} seconds = {user_input_val / 3600} hours"
                        )
                    elif first == "hour" and second == "second":
                        answer = (
                            f"{user_input_val} hours = {user_input_val * 3600} seconds"
                        )
                    elif first == "minute" and second == "hour":
                        answer = (
                            f"{user_input_val} minutes = {user_input_val / 60} hours"
                        )
                    elif first == "hour" and second == "minute":
                        answer = (
                            f"{user_input_val} hours = {user_input_val * 60} minutes"
                        )
                    else:
                        answer = "Conversion not supported."
                except ValueError:
                    answer = "Invalid input number."
            else:
                answer = "Please enter a number."
            context = {
                "form": form,
                "m_form": measurement_form,
                "input": True,
                "answer": answer,
            }

        # Temperature Conversion
        elif measurement == "temperature":
            measurement_form = ConversionTemperatureForm()
            user_input_str = request.POST.get("input", "").strip()
            if user_input_str:
                try:
                    user_input_val = float(user_input_str)
                    first = request.POST["measure1"]
                    second = request.POST["measure2"]
                    if first == "celsius" and second == "kelvin":
                        answer = f"{user_input_val}°C = {user_input_val + 273.15} K"
                    elif first == "kelvin" and second == "celsius":
                        answer = f"{user_input_val} K = {user_input_val - 273.15}°C"
                    elif first == "celsius" and second == "fahrenheit":
                        answer = (
                            f"{user_input_val}°C = {(user_input_val * 9 / 5) + 32}°F"
                        )
                    elif first == "fahrenheit" and second == "celsius":
                        answer = (
                            f"{user_input_val}°F = {(user_input_val - 32) * 5 / 9}°C"
                        )
                    elif first == "fahrenheit" and second == "kelvin":
                        celsius = (user_input_val - 32) * 5 / 9
                        answer = f"{user_input_val}°F = {celsius + 273.15} K"
                    elif first == "kelvin" and second == "fahrenheit":
                        answer = f"{user_input_val} K = {((user_input_val - 273.15) * 9 / 5) + 32}°F"
                    else:
                        answer = "Conversion not supported."
                except ValueError:
                    answer = "Invalid input number."
            else:
                answer = "Please enter a number."
            context = {
                "form": form,
                "m_form": measurement_form,
                "input": True,
                "answer": answer,
            }

        # Electric Current Conversion
        elif measurement == "electric_current":
            measurement_form = ConversionElectricCurrentForm()
            user_input_str = request.POST.get("input", "").strip()
            if user_input_str:
                try:
                    user_input_val = float(user_input_str)
                    first = request.POST["measure1"]
                    second = request.POST["measure2"]
                    if first == "ampere" and second == "milliampere":
                        answer = f"{user_input_val} A = {user_input_val * 1000} mA"
                    elif first == "milliampere" and second == "ampere":
                        answer = f"{user_input_val} mA = {user_input_val / 1000} A"
                    else:
                        answer = "Conversion not supported."
                except ValueError:
                    answer = "Invalid input number."
            else:
                answer = "Please enter a number."
            context = {
                "form": form,
                "m_form": measurement_form,
                "input": True,
                "answer": answer,
            }

        # Amount of Substance Conversion
        elif measurement == "amount_substance":
            measurement_form = ConversionAmountSubstanceForm()
            user_input_str = request.POST.get("input", "").strip()
            if user_input_str:
                try:
                    user_input_val = float(user_input_str)
                    first = request.POST["measure1"]
                    second = request.POST["measure2"]
                    if first == "mole" and second == "millimole":
                        answer = f"{user_input_val} mole = {user_input_val * 1000} mmol"
                    elif first == "millimole" and second == "mole":
                        answer = f"{user_input_val} mmol = {user_input_val / 1000} mole"
                    else:
                        answer = "Conversion not supported."
                except ValueError:
                    answer = "Invalid input number."
            else:
                answer = "Please enter a number."
            context = {
                "form": form,
                "m_form": measurement_form,
                "input": True,
                "answer": answer,
            }

        # Luminous Intensity Conversion
        elif measurement == "luminous_intensity":
            measurement_form = ConversionLuminousIntensityForm()
            user_input_str = request.POST.get("input", "").strip()
            if user_input_str:
                try:
                    user_input_val = float(user_input_str)
                    first = request.POST["measure1"]
                    second = request.POST["measure2"]
                    if first == "candela" and second == "millicandela":
                        answer = f"{user_input_val} cd = {user_input_val * 1000} mcd"
                    elif first == "millicandela" and second == "candela":
                        answer = f"{user_input_val} mcd = {user_input_val / 1000} cd"
                    else:
                        answer = "Conversion not supported."
                except ValueError:
                    answer = "Invalid input number."
            else:
                answer = "Please enter a number."
            context = {
                "form": form,
                "m_form": measurement_form,
                "input": True,
                "answer": answer,
            }

        context["type_choices"] = [
        ('length',           'straighten',    'Length'),
        ('mass',             'scale',         'Mass'),
        ('time',             'timer',         'Time'),
        ('temperature',      'thermostat',    'Temp'),
        ('electric_current', 'electric_bolt', 'Current'),
        ('amount_substance', 'science',       'Substance'),
        ('luminous_intensity','light_mode',   'Luminous'),
    ]
        return render(request, "dashboard/conversion.html", context)
    else:
        form = ConversionForm()
        context = {"form": form, "input": False, "type_choices": [
        ('length',           'straighten',    'Length'),
        ('mass',             'scale',         'Mass'),
        ('time',             'timer',         'Time'),
        ('temperature',      'thermostat',    'Temp'),
        ('electric_current', 'electric_bolt', 'Current'),
        ('amount_substance', 'science',       'Substance'),
        ('luminous_intensity','light_mode',   'Luminous'),
    ]}
    return render(request, "dashboard/conversion.html", context)


def register(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            # Save core User record (username + hashed password + email via Meta.fields)
            user = form.save(commit=False)

            # Ensure email is lower-cased and stored
            email = form.cleaned_data.get("email", "").strip().lower()
            if email:
                user.email = email

            user.save()

            username = user.username
            phone    = form.cleaned_data.get("phone_number", "").strip()

            # Persist phone number to UserProfile
            # Use get_or_create so this works even if the post_save signal
            # hasn't fired yet (e.g. during unit tests or custom backends).
            from dashboard.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if phone:
                profile.phone_number = phone
                profile.save(update_fields=["phone_number"])

            # Welcome notification
            from .models import push_notification
            welcome_msg = (
                f"Hi {username}! Your ScholarSpace account is ready. "
            )
            if email and phone:
                welcome_msg += (
                    f"Email reminders will go to {email} and "
                    f"SMS reminders to {phone}. "
                )
            elif email:
                welcome_msg += f"Email reminders will go to {email}. "
            elif phone:
                welcome_msg += f"SMS reminders will go to {phone}. "

            welcome_msg += "Click 'Take a Tour' on the Notifications page to explore every feature."

            push_notification(
                user,
                "Welcome to ScholarSpace!",
                welcome_msg,
                notif_type="welcome",
                icon="celebration",
                link="/notifications/",
            )

            messages.success(request, f"Account created for {username}! Please sign in.")
            return redirect("login")

    else:
        form = UserRegistrationForm()

    return render(request, "dashboard/register.html", {"form": form})


@login_required
def profile(request):
    from .models import UserProfile
    
    if request.method == "POST":
        new_username = request.POST.get("username", "").strip()
        new_email = request.POST.get("email", "").strip()
        new_phone = request.POST.get("phone", "").strip()
        
        updated = False
        if new_username and new_username != request.user.username:
            request.user.username = new_username
            updated = True
        if new_email and new_email != request.user.email:
            request.user.email = new_email
            updated = True
            
        if updated:
            request.user.save()
            
        profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
        if new_phone != profile_obj.phone_number:
            profile_obj.phone_number = new_phone
            profile_obj.save(update_fields=["phone_number"])
            
        messages.success(request, "Profile updated successfully.")
        return redirect("profile")

    homeworks = Homework.objects.filter(is_finished=False, user=request.user)
    todos = Todo.objects.filter(is_finished=False, user=request.user)
    if len(homeworks) == 0:
        homework_done = True
    else:
        homework_done = False

    if len(todos) == 0:
        todos_done = True
    else:
        todos_done = False
    context = {
        "homeworks": homeworks,
        "todos": todos,
        "homework_done": homework_done,
        "todos_done": todos_done,
    }

    return render(request, "dashboard/profile.html", context)


import threading

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from .models import Homework


def setup_email_notification(request):
    if request.method == "POST":
        email = request.POST.get("email")

        # Start a background thread for email notifications
        notification_thread = threading.Thread(
            target=send_homework_notifications, args=(email,)
        )
        notification_thread.daemon = True
        notification_thread.start()

        messages.success(request, "Email notifications set up successfully!")
        return redirect("homework")
    return redirect("homework")


def send_homework_notifications(email):
    while True:
        # Fetch all incomplete homeworks
        homeworks = Homework.objects.filter(is_finished=False)

        if homeworks:
            # Prepare email content
            subject = "Homework Reminder By ScholarSpace"
            message = "Your Pending Homeworks:\n\n"
            for hw in homeworks:
                message += f"Subject: {hw.subject}\n"
                message += f"Title: {hw.title}\n"
                message += f"Description: {hw.description}\n"
                message += f"Due Date: {hw.due}\n\n"

            # Send email
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Email sending failed: {e}")

        # Wait for 1 minute before next notification
        time.sleep(60)


# ── Notification views ───────────────────────────────────────────────────────

@login_required
def notifications_view(request):
    from .models import Notification
    notifs = Notification.objects.filter(user=request.user)
    # mark all unread as read on page load
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return render(request, "dashboard/notifications.html", {"notifications": notifs})


@login_required
def mark_all_read_view(request):
    """POST-only — marks all notifications read and redirects back."""
    from .models import Notification
    if request.method == "POST":
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect("notifications")

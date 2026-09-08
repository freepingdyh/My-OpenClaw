# -*- coding: utf-8 -*-
"""v1.12.06x — secure Cloud Villa H3 playback and deletion controls."""
from __future__ import annotations

import os
from typing import Any, Dict

_MARKER = "XIAOXIA_VIDEO_ROOM_PRIVACY_V11206X"

_SCRIPT = r'''
    <script>
    // XIAOXIA_VIDEO_ROOM_PRIVACY_V11206X
    const VAULT_VIDEO_KEY = 'xiaoxia_vault_key';
    let vaultVideoObjectUrls = [];

    function vaultAuthHeaders() {
        const key = sessionStorage.getItem(VAULT_VIDEO_KEY) || '';
        return { 'X-Xiaoxia-Vault-Key': key };
    }

    async function loadVideoArchive() {
        try {
            const res = await fetch('/api/videos', { headers: vaultAuthHeaders() });
            if (res.status === 401) throw new Error('vault-auth-required');
            allVideos = res.ok ? await res.json() : [];
            renderVideoArchive('all');
        } catch (e) {
            console.error('Secure video archive load error', e);
            const grid = document.getElementById('video-archive-grid');
            if (grid) grid.innerHTML = '<p class="col-span-full text-center text-red-400 py-16">放映室需要重新登入別墅才能讀取。</p>';
        }
    }

    async function hydrateVaultVideos(rows) {
        vaultVideoObjectUrls.forEach(u => { try { URL.revokeObjectURL(u); } catch (_) {} });
        vaultVideoObjectUrls = [];
        for (const v of rows) {
            const id = String(v.video_id || '');
            const el = document.getElementById('vault-video-' + id);
            if (!id || !el) continue;
            try {
                const res = await fetch(`/api/videos/${encodeURIComponent(id)}/stream`, { headers: vaultAuthHeaders() });
                if (!res.ok) throw new Error(`stream-${res.status}`);
                const blob = await res.blob();
                const objectUrl = URL.createObjectURL(blob);
                vaultVideoObjectUrls.push(objectUrl);
                el.src = objectUrl;
                el.load();
            } catch (e) {
                console.error('Secure video stream failed', id, e);
                el.outerHTML = '<div class="text-xs text-red-300 p-4">影片讀取失敗，請重新登入。</div>';
            }
        }
    }

    function renderVideoArchive(filterType = 'all') {
        if (!VIDEO_FILTERS.includes(filterType)) filterType = 'all';
        VIDEO_FILTERS.forEach(t => {
            const btn = document.getElementById('btn-video-' + t);
            if (!btn) return;
            btn.className = t === filterType
                ? 'px-3 py-1 text-sm rounded-md bg-pink-500 text-white shadow transition whitespace-nowrap'
                : 'px-3 py-1 text-sm rounded-md text-gray-600 hover:bg-pink-100 transition whitespace-nowrap';
        });
        const grid = document.getElementById('video-archive-grid');
        if (!grid) return;
        const rows = allVideos.filter(v => filterType === 'all' || String(v.source_mode || '').toLowerCase() === filterType);
        if (!rows.length) {
            grid.innerHTML = '<p class="col-span-full text-center text-gray-400 py-16">這個分類目前還沒有收藏影片。</p>';
            return;
        }
        grid.innerHTML = rows.map(v => {
            const title = videoEscape(v.source_title || v.video_theme || '小俠的 H3 片段');
            const date = videoEscape(String(v.saved_at || v.source_date || '').slice(0, 10));
            const label = videoSourceLabel(v.source_mode);
            const poster = videoEscape(v.source_image_url || '');
            const id = videoEscape(v.video_id || '');
            return `
            <article class="bg-white/80 rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                <div class="bg-gray-900 aspect-video flex items-center justify-center">
                    <video id="vault-video-${id}" controls preload="metadata" ${poster ? `poster="${poster}"` : ''} class="w-full h-full object-contain bg-black"></video>
                </div>
                <div class="p-4">
                    <div class="flex items-center justify-between gap-3 mb-2">
                        <span class="text-[11px] text-pink-600 bg-pink-50 px-2 py-1 rounded-full whitespace-nowrap">${label}</span>
                        <span class="text-[11px] text-gray-400">${date}</span>
                    </div>
                    <h3 class="font-bold text-gray-800 text-sm leading-relaxed line-clamp-2 min-h-[2.5rem]">${title}</h3>
                    ${v.video_theme ? `<p class="text-xs text-gray-400 mt-2 line-clamp-2">${videoEscape(v.video_theme)}</p>` : ''}
                    <div class="flex flex-wrap justify-between items-center gap-2 mt-4 pt-3 border-t border-gray-100">
                        <button onclick="openVideoOrigin('${id}')" class="text-xs font-bold text-pink-500 hover:text-pink-700 transition">為何拍／原文</button>
                        <div class="flex gap-3 items-center">
                            ${v.source_jump_url ? `<a href="${videoEscape(v.source_jump_url)}" target="_blank" rel="noopener" class="text-xs text-gray-400 hover:text-gray-700 transition">回到來源 ↗</a>` : ''}
                            <button onclick="deleteVaultVideo('${id}')" class="text-xs font-bold text-red-400 hover:text-red-600 transition">🗑️ 刪除</button>
                        </div>
                    </div>
                </div>
            </article>`;
        }).join('');
        hydrateVaultVideos(rows);
    }

    async function deleteVaultVideo(videoId) {
        const v = allVideos.find(x => String(x.video_id || '') === String(videoId || ''));
        const title = v ? (v.source_title || v.video_theme || '這支影片') : '這支影片';
        if (!confirm(`確定刪除「${title}」嗎？\n\n會同時刪除影片檔與收藏紀錄，無法復原。`)) return;
        try {
            const res = await fetch(`/api/videos/${encodeURIComponent(videoId)}`, { method: 'DELETE', headers: vaultAuthHeaders() });
            if (!res.ok) throw new Error(`delete-${res.status}`);
            allVideos = allVideos.filter(x => String(x.video_id || '') !== String(videoId || ''));
            renderVideoArchive('all');
        } catch (e) {
            console.error('Delete video failed', e);
            alert('刪除失敗，請重新登入別墅後再試。');
        }
    }
    </script>
'''


def install_video_room_privacy(app: Any, index_path: str | None = None) -> Dict[str, Any]:
    path = index_path or os.path.join(os.getcwd(), "index.html")
    if not os.path.exists(path):
        return {"patched": False, "reason": "index_not_found", "path": path}
    with open(path, "r", encoding="utf-8") as fh:
        html = fh.read()
    if _MARKER in html:
        return {"patched": False, "reason": "already_patched", "path": path}

    # Keep the user's entered vault key only for this browser session, then send it
    # as an API header. Raw media paths are never placed in the HTML/Discord UI.
    needle = "sessionStorage.setItem(VAULT_SESSION_KEY, '1');"
    replacement = needle + "\n                sessionStorage.setItem('xiaoxia_vault_key', pass);"
    if needle in html:
        html = html.replace(needle, replacement, 1)

    logout = "sessionStorage.removeItem(VAULT_SESSION_KEY);"
    if logout in html:
        html = html.replace(logout, logout + "\n            sessionStorage.removeItem('xiaoxia_vault_key');", 1)

    body = "</body>"
    if body not in html:
        return {"patched": False, "reason": "body_anchor_missing", "path": path}
    html = html.replace(body, _SCRIPT + "\n" + body, 1)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return {"patched": True, "path": path, "protected_fetch": True, "raw_video_url_removed": True, "delete_button": True, "confirm_delete": True}

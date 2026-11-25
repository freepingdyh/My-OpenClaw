# -*- coding: utf-8 -*-
"""Cloud Villa H3 screening-room UI injector.

Keeps the existing index.html as the visual baseline and injects one restrained room,
source-detail modal, and small JS controller at runtime.  The patch is idempotent and
fully removable by rolling back the runtime.
"""
from __future__ import annotations

import os
from typing import Any, Dict

_MARKER = "XIAOXIA_VIDEO_ROOM_V11206P"

_VIDEO_TAB = '''
                    <button onclick="switchTab('videos')" id="tab-videos" class="text-gray-400 hover:text-pink-400 font-bold pb-1 text-lg transition whitespace-nowrap">小俠放映室</button>'''

_VIDEO_ROOM = r'''
        <!-- XIAOXIA_VIDEO_ROOM_V11206P -->
        <div id="content-videos" class="tab-content">
            <div class="glass p-6 rounded-2xl min-h-[600px]">
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6 border-b pb-4">
                    <div>
                        <h2 class="text-xl font-bold text-gray-800">小俠放映室</h2>
                        <p class="text-xs text-gray-400 mt-1">只收藏大俠親手留下的 H3 片段。</p>
                    </div>
                    <div class="flex gap-2 bg-white/50 p-1 rounded-lg border border-pink-100 overflow-x-auto w-full md:w-auto">
                        <button onclick="renderVideoArchive('all')" id="btn-video-all" class="px-3 py-1 text-sm rounded-md bg-pink-500 text-white shadow transition whitespace-nowrap">全部</button>
                        <button onclick="renderVideoArchive('cosplay')" id="btn-video-cosplay" class="px-3 py-1 text-sm rounded-md text-gray-600 hover:bg-pink-100 transition whitespace-nowrap">Cosplay</button>
                        <button onclick="renderVideoArchive('calendar')" id="btn-video-calendar" class="px-3 py-1 text-sm rounded-md text-gray-600 hover:bg-pink-100 transition whitespace-nowrap">小俠月曆</button>
                        <button onclick="renderVideoArchive('diary')" id="btn-video-diary" class="px-3 py-1 text-sm rounded-md text-gray-600 hover:bg-pink-100 transition whitespace-nowrap">交換日記</button>
                        <button onclick="renderVideoArchive('autonomy')" id="btn-video-autonomy" class="px-3 py-1 text-sm rounded-md text-gray-600 hover:bg-pink-100 transition whitespace-nowrap">小俠自主</button>
                        <button onclick="renderVideoArchive('photo')" id="btn-video-photo" class="px-3 py-1 text-sm rounded-md text-gray-600 hover:bg-pink-100 transition whitespace-nowrap">小俠寫真</button>
                    </div>
                </div>
                <div id="video-archive-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <p class="col-span-full text-center text-gray-400 py-16">正在讀取收藏影片...</p>
                </div>
            </div>
        </div>
'''

_SOURCE_MODAL = r'''
    <div id="video-origin-modal" class="fixed inset-0 bg-black/50 z-[110] hidden items-center justify-center p-4 backdrop-blur-sm" onclick="closeVideoOrigin(event)">
        <div class="bg-white w-full max-w-xl rounded-2xl shadow-2xl border border-pink-100 p-6" onclick="event.stopPropagation()">
            <div class="flex items-start justify-between gap-4 border-b border-gray-100 pb-4 mb-4">
                <div>
                    <p id="video-origin-type" class="text-xs font-bold text-pink-500 mb-1"></p>
                    <h3 id="video-origin-title" class="text-lg font-bold text-gray-800 serif"></h3>
                    <p id="video-origin-date" class="text-xs text-gray-400 mt-1"></p>
                </div>
                <button onclick="closeVideoOrigin()" class="text-gray-300 hover:text-gray-600 text-2xl leading-none">×</button>
            </div>
            <div class="space-y-4 max-h-[55vh] overflow-y-auto pr-1">
                <div id="video-origin-reason-wrap" class="hidden">
                    <p class="text-xs font-bold text-gray-400 mb-1">為何拍</p>
                    <p id="video-origin-reason" class="text-sm leading-relaxed text-gray-700 whitespace-pre-wrap"></p>
                </div>
                <div id="video-origin-text-wrap" class="hidden bg-pink-50/60 rounded-xl p-4 border border-pink-100">
                    <p class="text-xs font-bold text-pink-500 mb-2">原文</p>
                    <p id="video-origin-text" class="text-sm leading-relaxed text-gray-700 whitespace-pre-wrap"></p>
                </div>
                <div id="video-origin-scene-wrap" class="hidden">
                    <p class="text-xs font-bold text-gray-400 mb-1">當時場景</p>
                    <p id="video-origin-scene" class="text-xs leading-relaxed text-gray-500 whitespace-pre-wrap"></p>
                </div>
            </div>
            <div class="flex flex-wrap justify-end gap-2 pt-5 mt-4 border-t border-gray-100">
                <button id="video-origin-villa-btn" onclick="jumpToVideoSourceInVilla()" class="hidden px-4 py-2 rounded-lg bg-pink-500 text-white text-sm font-bold hover:bg-pink-600 transition">回到別墅原始內容</button>
                <a id="video-origin-discord-btn" target="_blank" rel="noopener" class="hidden px-4 py-2 rounded-lg bg-gray-700 text-white text-sm font-bold hover:bg-gray-800 transition">開啟 Discord 原訊息 ↗</a>
            </div>
        </div>
    </div>
'''

_VIDEO_JS = r'''
        // XIAOXIA_VIDEO_ROOM_V11206P
        let allVideos = [];
        let activeVideoOrigin = null;
        const VIDEO_FILTERS = ['all', 'cosplay', 'calendar', 'diary', 'autonomy', 'photo'];

        function videoEscape(value) {
            return String(value == null ? '' : value)
                .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
        }

        function videoSourceLabel(mode) {
            const labels = {
                cosplay: '🎭 Cosplay', calendar: '📅 小俠月曆', diary: '📖 交換日記',
                autonomy: '🌿 小俠自主', photo: '📸 小俠寫真', photobook: '📷 小俠寫真',
                travel: '✈️ 旅行', love_intent: '💗 心動片刻'
            };
            return labels[String(mode || '').toLowerCase()] || '🎬 小俠影片';
        }

        async function loadVideoArchive() {
            try {
                const res = await fetch('/api/videos');
                allVideos = res.ok ? await res.json() : [];
                renderVideoArchive('all');
            } catch (e) {
                console.error('Video archive load error', e);
                const grid = document.getElementById('video-archive-grid');
                if (grid) grid.innerHTML = '<p class="col-span-full text-center text-red-400 py-16">無法讀取放映室資料。</p>';
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
                const src = videoEscape(v.video_url || '');
                const id = videoEscape(v.video_id || '');
                return `
                <article class="bg-white/80 rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                    <div class="bg-gray-900 aspect-video flex items-center justify-center">
                        <video controls preload="metadata" ${poster ? `poster="${poster}"` : ''} class="w-full h-full object-contain bg-black">
                            <source src="${src}" type="video/mp4">
                        </video>
                    </div>
                    <div class="p-4">
                        <div class="flex items-center justify-between gap-3 mb-2">
                            <span class="text-[11px] text-pink-600 bg-pink-50 px-2 py-1 rounded-full whitespace-nowrap">${label}</span>
                            <span class="text-[11px] text-gray-400">${date}</span>
                        </div>
                        <h3 class="font-bold text-gray-800 text-sm leading-relaxed line-clamp-2 min-h-[2.5rem]">${title}</h3>
                        ${v.video_theme ? `<p class="text-xs text-gray-400 mt-2 line-clamp-2">${videoEscape(v.video_theme)}</p>` : ''}
                        <div class="flex justify-between items-center mt-4 pt-3 border-t border-gray-100">
                            <button onclick="openVideoOrigin('${id}')" class="text-xs font-bold text-pink-500 hover:text-pink-700 transition">為何拍／原文</button>
                            ${v.source_jump_url ? `<a href="${videoEscape(v.source_jump_url)}" target="_blank" rel="noopener" class="text-xs text-gray-400 hover:text-gray-700 transition">回到來源 ↗</a>` : ''}
                        </div>
                    </div>
                </article>`;
            }).join('');
        }

        function canJumpVideoSourceInVilla(v) {
            if (!v) return false;
            if (String(v.source_mode || '').toLowerCase() === 'diary' && v.source_date) return true;
            if (v.source_id && allPhotos.some(p => String(p.id || '') === String(v.source_id))) return true;
            if (v.source_image_url && allPhotos.some(p => (p.local_url || p.image_url) === v.source_image_url)) return true;
            return false;
        }

        function openVideoOrigin(videoId) {
            const v = allVideos.find(x => String(x.video_id || '') === String(videoId || ''));
            if (!v) return;
            activeVideoOrigin = v;
            document.getElementById('video-origin-type').textContent = videoSourceLabel(v.source_mode);
            document.getElementById('video-origin-title').textContent = v.source_title || v.video_theme || '小俠的 H3 片段';
            document.getElementById('video-origin-date').textContent = v.source_date || String(v.saved_at || '').slice(0, 10);

            const reason = String(v.source_reason || '').trim();
            const original = String(v.source_original_text || '').trim();
            const scene = String(v.source_scene || '').trim();
            const setBlock = (wrap, el, text) => {
                document.getElementById(el).textContent = text;
                document.getElementById(wrap).classList.toggle('hidden', !text);
            };
            setBlock('video-origin-reason-wrap', 'video-origin-reason', reason);
            setBlock('video-origin-text-wrap', 'video-origin-text', original);
            setBlock('video-origin-scene-wrap', 'video-origin-scene', scene);

            const villaBtn = document.getElementById('video-origin-villa-btn');
            villaBtn.classList.toggle('hidden', !canJumpVideoSourceInVilla(v));
            const discordBtn = document.getElementById('video-origin-discord-btn');
            if (v.source_jump_url) {
                discordBtn.href = v.source_jump_url;
                discordBtn.classList.remove('hidden');
            } else {
                discordBtn.classList.add('hidden');
                discordBtn.removeAttribute('href');
            }
            const modal = document.getElementById('video-origin-modal');
            modal.classList.remove('hidden');
            modal.classList.add('flex');
        }

        function closeVideoOrigin(event) {
            if (event && event.target && event.target.id !== 'video-origin-modal') return;
            const modal = document.getElementById('video-origin-modal');
            if (!modal) return;
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        }

        function jumpToVideoSourceInVilla() {
            const v = activeVideoOrigin;
            if (!v) return;
            const mode = String(v.source_mode || '').toLowerCase();
            if (mode === 'diary' && v.source_date) {
                closeVideoOrigin();
                switchTab('diary');
                const input = document.getElementById('diary-date-jump');
                input.value = String(v.source_date).slice(0, 10);
                setTimeout(() => jumpToDiaryDate(), 120);
                return;
            }
            let idx = -1;
            if (v.source_id) idx = allPhotos.findIndex(p => String(p.id || '') === String(v.source_id));
            if (idx < 0 && v.source_image_url) idx = allPhotos.findIndex(p => (p.local_url || p.image_url) === v.source_image_url);
            if (idx >= 0) {
                closeVideoOrigin();
                document.getElementById('gallery-search').value = '';
                filteredPhotos = allPhotos.filter(p => getOverviewCategory(p) !== 'project');
                const targetId = String(allPhotos[idx].id || '');
                const fidx = filteredPhotos.findIndex(p => String(p.id || '') === targetId);
                currentIndex = fidx >= 0 ? fidx : 0;
                switchTab('gallery');
                renderMainDisplay();
                renderTimelineList();
                return;
            }
            if (v.source_jump_url) window.open(v.source_jump_url, '_blank', 'noopener');
        }
'''


def install_video_room_ui(app: Any, index_path: str | None = None) -> Dict[str, Any]:
    path = index_path or os.path.join(os.getcwd(), "index.html")
    if not os.path.exists(path):
        return {"patched": False, "reason": "index_not_found", "path": path}
    with open(path, "r", encoding="utf-8") as fh:
        html = fh.read()
    if _MARKER in html:
        return {"patched": False, "reason": "already_patched", "path": path}

    diary_tab = '''                    <button onclick="switchTab('diary')" id="tab-diary" class="text-gray-400 hover:text-pink-400 font-bold pb-1 text-lg transition whitespace-nowrap">交換日記</button>'''
    if diary_tab not in html:
        return {"patched": False, "reason": "tab_anchor_missing", "path": path}
    html = html.replace(diary_tab, diary_tab + _VIDEO_TAB, 1)

    projects_anchor = '        <div id="content-projects" class="tab-content">'
    if projects_anchor not in html:
        return {"patched": False, "reason": "content_anchor_missing", "path": path}
    html = html.replace(projects_anchor, _VIDEO_ROOM + "\n" + projects_anchor, 1)

    lightbox_anchor = '    <!-- 🌟 重新設計的燈箱 HTML 結構，確保隨處點擊皆可關閉 -->'
    html = html.replace(lightbox_anchor, _SOURCE_MODAL + "\n" + lightbox_anchor, 1)

    html = html.replace('            loadProjectsAndMusic();', '            loadProjectsAndMusic();\n            loadVideoArchive();', 1)
    html = html.replace("['gallery', 'overview', 'projects', 'music', 'diary'].includes(savedTab)", "['gallery', 'overview', 'projects', 'music', 'diary', 'videos'].includes(savedTab)", 1)
    html = html.replace("['gallery', 'overview', 'projects', 'music', 'diary'].forEach(t => {", "['gallery', 'overview', 'projects', 'music', 'diary', 'videos'].forEach(t => {", 1)

    script_anchor = '    </script>'
    if script_anchor not in html:
        return {"patched": False, "reason": "script_anchor_missing", "path": path}
    html = html.replace(script_anchor, _VIDEO_JS + "\n" + script_anchor, 1)

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return {"patched": True, "path": path, "room": "小俠放映室", "style": "existing Cloud Villa baseline"}

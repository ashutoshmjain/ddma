
        // State variables
        let activeProjectId = null;
        let projectInfo = null;
        let transcriptionData = null;
        let allWords = [];
        let availableMusicFiles = [];
        
        let startWordIdx = null;
        let endWordIdx = null;
        let ctxWordIdx = null;
        
        let clips = [];
        let activeSearchQuery = "";
        let activeClipPlayIdx = null;
        let lastCombinedUrl = "";
        let compiledVideos = [];
        let clipStatuses = {};
        let dragSrcCardIdx = null;
        let showUsedRanges = false;
        let showHiddenClips = false;
        let editingSegmentRef = null; // { clipIdx, segIdx }
        
        let pollingInterval = null;
        let undoStack = [];
        let lastSavedStateString = "[]";
        let activeLockedSequence = null;
        let sequencePlayIdx = -1;
        let segmentClipboard = null;

        function calculateClipDuration(clip) {
            let total = 0;
            if (clip && clip.segments) {
                clip.segments.forEach((seg, idx) => {
                    total += parseFloat(seg.duration || 0);
                    if (idx < clip.segments.length - 1) {
                        total -= parseFloat(seg.crossfade || 0);
                    }
                });
            }
            return total;
        }

        // Elements
        const projectList = document.getElementById('projectList');
        const activeProjectBadge = document.getElementById('activeProjectBadge');
        const activeProjectTitleHeader = document.getElementById('activeProjectTitleHeader');
        
        const transcriptContainer = document.getElementById('transcriptContainer');
        const transcriptionEmptyState = document.getElementById('transcriptionEmptyState');
        const segmentCount = document.getElementById('segmentCount');
        const searchInput = document.getElementById('searchInput');
        const toggleUsedBtn = document.getElementById('toggleUsedBtn');
        
        const selStart = document.getElementById('selStart');
        const selEnd = document.getElementById('selEnd');
        const selDuration = document.getElementById('selDuration');
        
        const clipListContainer = document.getElementById('clipListContainer');
        const planEmptyState = document.getElementById('planEmptyState');
        const exportBtn = document.getElementById('exportBtn');
        const combineVideoBtn = document.getElementById('combineVideoBtn');
        const newClipBtn = document.getElementById('newClipBtn');
        const collapseAllBtn = document.getElementById('collapseAllBtn');
        const expandAllBtn = document.getElementById('expandAllBtn');
        const toggleShowHiddenBtn = document.getElementById('toggleShowHiddenBtn');
        
        const clipsToolbar = document.getElementById('clipsToolbar');
        const undoBtn = document.getElementById('undoBtn');
        const undoCountLabel = document.getElementById('undoCountLabel');
        const saveSnapshotBtn = document.getElementById('saveSnapshotBtn');
        const restoreSnapshotBtn = document.getElementById('restoreSnapshotBtn');
        const playLockedBtn = document.getElementById('playLockedBtn');
        
        const audioElement = document.getElementById('audioElement');
        const playBtn = document.getElementById('playBtn');
        const playerSlider = document.getElementById('playerSlider');
        const currTime = document.getElementById('currTime');
        const totTime = document.getElementById('totTime');
        const nowPlayingTitle = document.getElementById('nowPlayingTitle');
        const playerDownloadBtn = document.getElementById('playerDownloadBtn');
        
        const exportModalOverlay = document.getElementById('exportModalOverlay');
        const closeModalBtn = document.getElementById('closeModalBtn');
        const minimizeModalBtn = document.getElementById('minimizeModalBtn');
        const combineModalHeaderTitle = document.getElementById('combineModalHeaderTitle');
        const openExportModalBtn = document.getElementById('openExportModalBtn');
        const exportTextarea = document.getElementById('exportTextarea');
        const copyJsonBtn = document.getElementById('copyJsonBtn');
        const downloadPlanBtn = document.getElementById('downloadPlanBtn');
        
        // Video Preview elements
        const videoModalOverlay = document.getElementById('videoModalOverlay');
        const closeVideoModalBtn = document.getElementById('closeVideoModalBtn');
        
        // Mosaic Prompt Modal elements
        const mosaicPromptModalOverlay = document.getElementById('mosaicPromptModalOverlay');
        const closeMosaicPromptModalBtn = document.getElementById('closeMosaicPromptModalBtn');
        const cancelMosaicPromptBtn = document.getElementById('cancelMosaicPromptBtn');
        const submitMosaicPromptBtn = document.getElementById('submitMosaicPromptBtn');
        const mosaicPromptTextarea = document.getElementById('mosaicPromptTextarea');
        const previewVideoPlayer = document.getElementById('previewVideoPlayer');
        const videoModalTitle = document.getElementById('videoModalTitle');
        const videoModalSubtitle = document.getElementById('videoModalSubtitle');
        const downloadVideoBtn = document.getElementById('downloadVideoBtn');

        const combineLoadingState = document.getElementById('combineLoadingState');
        const combinePlayerState = document.getElementById('combinePlayerState');
        const combinedAudioPlayer = document.getElementById('combinedAudioPlayer');
        const downloadCombinedAudioBtn = document.getElementById('downloadCombinedAudioBtn');
        const showPlanJsonBtn = document.getElementById('showPlanJsonBtn');
        const planJsonSection = document.getElementById('planJsonSection');
        const contextMenu = document.getElementById('contextMenu');
        const debugStatus = document.getElementById('debugStatus');
        const playerStateBar = document.getElementById('playerStateBar');

        // Project Creation Elements
        const newProjectBtn = document.getElementById('newProjectBtn');
        const projectModalOverlay = document.getElementById('projectModalOverlay');
        const closeProjectModalBtn = document.getElementById('closeProjectModalBtn');
        const cancelProjectBtn = document.getElementById('cancelProjectBtn');
        const saveProjectBtn = document.getElementById('saveProjectBtn');
        const newProjectNameInput = document.getElementById('newProjectNameInput');
        const newProjectAudioSelect = document.getElementById('newProjectAudioSelect');

        // Resizer and Collapse Elements
        const resizer = document.getElementById('panelResizer');
        const leftPanel = document.querySelector('.left-panel');
        const sidebarPanel = document.querySelector('.sidebar-panel');
        const rightPanel = document.querySelector('.right-panel');
        const collapseSidebarBtn = document.getElementById('collapseSidebarBtn');
        const expandSidebarBtn = document.getElementById('expandSidebarBtn');
        const collapseTranscriptBtn = document.getElementById('collapseTranscriptBtn');
        const expandTranscriptBtn = document.getElementById('expandTranscriptBtn');
        const leftCollapsedTab = document.getElementById('leftCollapsedTab');
        const rightCollapsedTab = document.getElementById('rightCollapsedTab');

        // Help Chat Elements
        const helpChatPanel = document.getElementById('helpChatPanel');
        const toggleHelpChatBtn = document.getElementById('toggleHelpChatBtn');
        const helpChatToggleArrow = document.getElementById('helpChatToggleArrow');
        const helpChatBody = document.getElementById('helpChatBody');
        const helpChatMessages = document.getElementById('helpChatMessages');
        const helpChatInput = document.getElementById('helpChatInput');
        const sendHelpChatBtn = document.getElementById('sendHelpChatBtn');

        // Settings Elements
        const settingsBtn = document.getElementById('settingsBtn');
        const settingsModalOverlay = document.getElementById('settingsModalOverlay');
        const closeSettingsModalBtn = document.getElementById('closeSettingsModalBtn');
        const saveSettingsBtn = document.getElementById('saveSettingsBtn');
        const themeSelector = document.getElementById('themeSelector');
        
        const importMusicBtn = document.getElementById('importMusicBtn');
        const musicUploadInput = document.getElementById('musicUploadInput');
        const settingsMusicList = document.getElementById('settingsMusicList');

        // Export Settings Elements
        const exportFormatSelector = document.getElementById('exportFormatSelector');
        const videoSettingsArea = document.getElementById('videoSettingsArea');
        const videoResolutionSelector = document.getElementById('videoResolutionSelector');
        const videoBgPresetSelector = document.getElementById('videoBgPresetSelector');
        const customColorField = document.getElementById('customColorField');
        const videoBgCustomInput = document.getElementById('videoBgCustomInput');

        function showDebug(msg, isError = true) {
            const statusText = document.getElementById('debugStatusText');
            const copyBtn = document.getElementById('copyDebugBtn');
            
            if (statusText) {
                statusText.textContent = msg;
                statusText.style.color = isError ? '#f87171' : '#34d399';
            }
            
            debugStatus.style.borderColor = isError ? 'rgba(239, 68, 68, 0.4)' : 'rgba(16, 185, 129, 0.4)';
            debugStatus.style.display = 'block';
            
            if (copyBtn) {
                copyBtn.onclick = (e) => {
                    e.stopPropagation();
                    navigator.clipboard.writeText(msg).then(() => {
                        const originalText = copyBtn.textContent;
                        copyBtn.textContent = "✅ Copied!";
                        setTimeout(() => { copyBtn.textContent = originalText; }, 1500);
                    }).catch(err => {
                        console.error("Failed to copy debug msg: ", err);
                    });
                };
            }
            
            // Keep on screen for 15 seconds to allow ample time to copy
            if (window.debugHideTimeout) clearTimeout(window.debugHideTimeout);
            window.debugHideTimeout = setTimeout(() => { debugStatus.style.display = 'none'; }, 15000);
        }

        function updateStateBar(stateMsg) {
            playerStateBar.textContent = `🎙 STATE: ${stateMsg}`;
        }

        // Save settings to settings.json on server
        function saveSettingsToServer() {
            if (!window.location.protocol.startsWith('http')) return;
            const theme = localStorage.getItem('ddma-theme') || 'midnight';
            const format = localStorage.getItem('ddma-export-format') || 'audio';
            const res = localStorage.getItem('ddma-video-res') || '740x740';
            const bg = localStorage.getItem('ddma-video-bg') || 'black';
            
            const settings = {
                theme: theme,
                export_format: format,
                resolution: res,
                bg_color: bg,
                mosaic_api_key: localStorage.getItem('ddma-mosaic-api-key') || '',
                mosaic_agent_id: localStorage.getItem('ddma-mosaic-agent-id') || '',
                mosaic_mogr_node_id: localStorage.getItem('ddma-mosaic-mogr-node-id') || '',
                mosaic_captions_node_id: localStorage.getItem('ddma-mosaic-captions-node-id') || '',
                gemini_api_key: localStorage.getItem('ddma-gemini-api-key') || '',
                mosaic_default_prompt: localStorage.getItem('ddma-mosaic-default-prompt') || ''
            };
            
            fetch('/save-settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            })
            .then(res => {
                if (!res.ok) console.error("Saving settings to server failed");
            })
            .catch(err => {
                console.warn("Saving settings to server failed: ", err.message);
            });
        }

        // Initialize App
        window.addEventListener('DOMContentLoaded', () => {
            const initApp = () => {
                // Apply loaded theme preference on load
                const savedTheme = localStorage.getItem('ddma-theme') || 'midnight';
                applyTheme(savedTheme, false); // pass false so we don't save back immediately
                themeSelector.value = savedTheme;

                // Load saved export settings
                const savedFormat = localStorage.getItem('ddma-export-format') || 'audio';
                exportFormatSelector.value = savedFormat;
                if (savedFormat === 'video') {
                    videoSettingsArea.style.display = 'flex';
                } else {
                    videoSettingsArea.style.display = 'none';
                }
                
                const savedRes = localStorage.getItem('ddma-video-res') || '740x740';
                videoResolutionSelector.value = savedRes;
                
                const savedBg = localStorage.getItem('ddma-video-bg') || 'black';
                if (savedBg !== 'black' && savedBg !== '#161822' && savedBg !== '#475569') {
                    videoBgPresetSelector.value = 'custom';
                    customColorField.style.display = 'flex';
                    videoBgCustomInput.value = savedBg;
                } else {
                    videoBgPresetSelector.value = savedBg;
                    customColorField.style.display = 'none';
                }

                if (window.location.protocol.startsWith('http')) {
                    updateStateBar("Loading projects list...");
                    
                    // Fetch music stings
                    fetch('/list-music')
                        .then(r => r.json())
                        .then(files => {
                            availableMusicFiles = files;
                            // Fetch projects
                            loadProjectsList();
                        })
                        .catch(err => {
                            console.error("Music stings load failure: ", err);
                            loadProjectsList();
                        });
                }
                
                setupResizer();
                setupSidebarCollapse();
                setupTranscriptCollapse();
                setupSettingsModal();
                setupHelpChat();
            };

            if (window.location.protocol.startsWith('http')) {
                // Fetch settings from server
                fetch('/get-settings')
                    .then(r => {
                        if (!r.ok) throw new Error("Could not retrieve settings");
                        return r.json();
                    })
                    .then(data => {
                        if (data.theme) localStorage.setItem('ddma-theme', data.theme);
                        if (data.export_format) localStorage.setItem('ddma-export-format', data.export_format);
                        if (data.resolution) localStorage.setItem('ddma-video-res', data.resolution);
                        if (data.bg_color) localStorage.setItem('ddma-video-bg', data.bg_color);
                        
                        localStorage.setItem('ddma-mosaic-api-key', data.mosaic_api_key || '');
                        localStorage.setItem('ddma-mosaic-agent-id', data.mosaic_agent_id || '');
                        localStorage.setItem('ddma-mosaic-mogr-node-id', data.mosaic_mogr_node_id || '');
                        localStorage.setItem('ddma-mosaic-captions-node-id', data.mosaic_captions_node_id || '');
                        localStorage.setItem('ddma-gemini-api-key', data.gemini_api_key || '');
                        localStorage.setItem('ddma-mosaic-default-prompt', data.mosaic_default_prompt || '');
                    })
                    .catch(err => {
                        console.warn("Could not load settings from server, using local fallback:", err);
                    })
                    .finally(() => {
                        initApp();
                    });
            } else {
                initApp();
            }
        });

        // Theme applier logic
        function applyTheme(themeName, save = true) {
            document.documentElement.className = '';
            if (themeName !== 'midnight') {
                document.documentElement.classList.add(`theme-${themeName}`);
            }
            localStorage.setItem('ddma-theme', themeName);
            if (save) {
                saveSettingsToServer();
            }
        }

        // Settings Modal Setup
        function setupSettingsModal() {
            settingsBtn.addEventListener('click', () => {
                // Refresh settings modal fields to match current localStorage
                const savedFormat = localStorage.getItem('ddma-export-format') || 'audio';
                exportFormatSelector.value = savedFormat;
                if (savedFormat === 'video') {
                    videoSettingsArea.style.display = 'flex';
                } else {
                    videoSettingsArea.style.display = 'none';
                }
                
                const savedRes = localStorage.getItem('ddma-video-res') || '740x740';
                videoResolutionSelector.value = savedRes;
                
                const savedBg = localStorage.getItem('ddma-video-bg') || 'black';
                if (savedBg !== 'black' && savedBg !== '#161822' && savedBg !== '#475569') {
                    videoBgPresetSelector.value = 'custom';
                    customColorField.style.display = 'flex';
                    videoBgCustomInput.value = savedBg;
                } else {
                    videoBgPresetSelector.value = savedBg;
                    customColorField.style.display = 'none';
                }

                document.getElementById('settingsMosaicApiKey').value = localStorage.getItem('ddma-mosaic-api-key') || '';
                document.getElementById('settingsMosaicAgentId').value = localStorage.getItem('ddma-mosaic-agent-id') || '';
                document.getElementById('settingsMosaicMogrNodeId').value = localStorage.getItem('ddma-mosaic-mogr-node-id') || '';
                document.getElementById('settingsMosaicCaptionsNodeId').value = localStorage.getItem('ddma-mosaic-captions-node-id') || '';
                document.getElementById('settingsGeminiApiKey').value = localStorage.getItem('ddma-gemini-api-key') || '';
                document.getElementById('settingsMosaicDefaultPrompt').value = localStorage.getItem('ddma-mosaic-default-prompt') || '';

                renderSettingsMusicList();
                settingsModalOverlay.classList.add('active');
            });

            closeSettingsModalBtn.addEventListener('click', () => {
                settingsModalOverlay.classList.remove('active');
            });

            // Toggle video settings visibility
            exportFormatSelector.addEventListener('change', function() {
                if (this.value === 'video') {
                    videoSettingsArea.style.display = 'flex';
                } else {
                    videoSettingsArea.style.display = 'none';
                }
            });

            // Toggle custom color input visibility
            videoBgPresetSelector.addEventListener('change', function() {
                if (this.value === 'custom') {
                    customColorField.style.display = 'flex';
                } else {
                    customColorField.style.display = 'none';
                }
            });

            saveSettingsBtn.addEventListener('click', () => {
                const selectedTheme = themeSelector.value;
                applyTheme(selectedTheme);

                const format = exportFormatSelector.value;
                localStorage.setItem('ddma-export-format', format);
                localStorage.setItem('ddma-video-res', videoResolutionSelector.value);
                
                let bg = videoBgPresetSelector.value;
                if (bg === 'custom') {
                    bg = videoBgCustomInput.value.trim() || '#000000';
                    if (!bg.startsWith('#') && bg.length === 6) {
                        bg = '#' + bg;
                    }
                }
                localStorage.setItem('ddma-video-bg', bg);
                
                localStorage.setItem('ddma-mosaic-api-key', document.getElementById('settingsMosaicApiKey').value.trim());
                localStorage.setItem('ddma-mosaic-agent-id', document.getElementById('settingsMosaicAgentId').value.trim());
                localStorage.setItem('ddma-mosaic-mogr-node-id', document.getElementById('settingsMosaicMogrNodeId').value.trim());
                localStorage.setItem('ddma-mosaic-captions-node-id', document.getElementById('settingsMosaicCaptionsNodeId').value.trim());
                localStorage.setItem('ddma-gemini-api-key', document.getElementById('settingsGeminiApiKey').value.trim());
                localStorage.setItem('ddma-mosaic-default-prompt', document.getElementById('settingsMosaicDefaultPrompt').value);
                
                saveSettingsToServer();

                settingsModalOverlay.classList.remove('active');
                showDebug(`Settings saved successfully!`, false);
            });
            
            // Music Upload triggers
            importMusicBtn.addEventListener('click', () => {
                musicUploadInput.click();
            });
            
            musicUploadInput.addEventListener('change', function() {
                if (this.files.length === 0) return;
                const file = this.files[0];
                
                updateStateBar(`Uploading music: ${file.name}...`);
                importMusicBtn.disabled = true;
                importMusicBtn.textContent = '⏳ Uploading...';
                
                fetch('/upload-music', {
                    method: 'POST',
                    headers: {
                        'X-Filename': file.name,
                        'Content-Type': file.type || 'application/octet-stream'
                    },
                    body: file
                })
                .then(res => {
                    importMusicBtn.disabled = false;
                    importMusicBtn.textContent = '🎵 Import New Sting';
                    if (!res.ok) throw new Error("Upload failed on server");
                    return res.json();
                })
                .then(data => {
                    showDebug(`Music uploaded successfully: ${data.filename}`, false);
                    musicUploadInput.value = '';
                    
                    // Refresh music and reload UI dropdowns
                    fetch('/list-music')
                        .then(r => r.json())
                        .then(files => {
                            availableMusicFiles = files;
                            renderSettingsMusicList();
                            renderClips();
                        });
                })
                .catch(err => {
                    importMusicBtn.disabled = false;
                    importMusicBtn.textContent = '🎵 Import New Sting';
                    showDebug("Upload failed: " + err.message);
                });
            });
        }

        // Populate dynamic global music list with deletes
        function renderSettingsMusicList() {
            settingsMusicList.innerHTML = '';
            if (availableMusicFiles.length === 0) {
                settingsMusicList.innerHTML = `<div style="font-size: 0.7rem; color: var(--text-muted); text-align: center; padding: 0.5rem;">No music stings available.</div>`;
                return;
            }
            
            availableMusicFiles.forEach(file => {
                const item = document.createElement('div');
                item.className = 'settings-music-item';
                
                item.innerHTML = `
                    <span class="settings-music-name" title="${file}">🎵 ${file}</span>
                    <button class="icon-btn icon-btn-danger delete-music-btn" data-file="${file}" title="Delete sting" style="padding: 0.1rem 0.25rem;">🗑</button>
                `;
                
                item.querySelector('.delete-music-btn').addEventListener('click', function(e) {
                    e.stopPropagation();
                    const fileName = this.dataset.file;
                    if (!confirm(`Are you sure you want to delete global music file: "${fileName}"?`)) return;
                    
                    updateStateBar(`Deleting music: ${fileName}...`);
                    fetch(`/delete-music?file=${encodeURIComponent(fileName)}`, { method: 'POST' })
                        .then(res => {
                            if (!res.ok) throw new Error("Delete request failed");
                            return res.json();
                        })
                        .then(() => {
                            showDebug(`Music file deleted: ${fileName}`, false);
                            fetch('/list-music')
                                .then(r => r.json())
                                .then(files => {
                                    availableMusicFiles = files;
                                    renderSettingsMusicList();
                                    renderClips();
                                });
                        })
                        .catch(err => {
                            showDebug("Failed to delete music: " + err.message);
                        });
                });
                
                settingsMusicList.appendChild(item);
            });
        }

        // Interactive panel resizing logic
        function setupResizer() {
            let isDragging = false;
            
            resizer.addEventListener('mousedown', function(e) {
                isDragging = true;
                resizer.classList.add('dragging');
                document.body.style.cursor = 'col-resize';
                document.body.style.userSelect = 'none';
            });
            
            document.addEventListener('mousemove', function(e) {
                if (!isDragging) return;
                
                const sidebarWidth = sidebarPanel.offsetWidth;
                const newWidth = e.clientX - sidebarWidth;
                
                if (newWidth > 320 && newWidth < 850) {
                    leftPanel.style.width = `${newWidth}px`;
                }
            });
            
            document.addEventListener('mouseup', function() {
                if (isDragging) {
                    isDragging = false;
                    resizer.classList.remove('dragging');
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';
                }
            });
        }

        // Sidebar collapse logic
        function setupSidebarCollapse() {
            collapseSidebarBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                sidebarPanel.classList.add('collapsed');
                leftCollapsedTab.style.display = 'flex';
            });
            
            leftCollapsedTab.addEventListener('click', function(e) {
                e.stopPropagation();
                sidebarPanel.classList.remove('collapsed');
                leftCollapsedTab.style.display = 'none';
            });
            
            expandSidebarBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                sidebarPanel.classList.remove('collapsed');
                leftCollapsedTab.style.display = 'none';
            });
        }

        // Transcript panel collapse logic
        let lastLeftPanelWidth = 500;
        function setupTranscriptCollapse() {
            collapseTranscriptBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                lastLeftPanelWidth = leftPanel.offsetWidth;
                
                rightPanel.classList.add('collapsed');
                resizer.style.display = 'none';
                rightCollapsedTab.style.display = 'flex';
                
                leftPanel.style.width = 'auto';
                leftPanel.style.flex = '1';
            });
            
            rightCollapsedTab.addEventListener('click', function(e) {
                e.stopPropagation();
                leftPanel.style.flex = 'none';
                leftPanel.style.width = `${lastLeftPanelWidth}px`;
                
                rightPanel.classList.remove('collapsed');
                resizer.style.display = 'block';
                rightCollapsedTab.style.display = 'none';
            });
            
            expandTranscriptBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                leftPanel.style.flex = 'none';
                leftPanel.style.width = `${lastLeftPanelWidth}px`;
                
                rightPanel.classList.remove('collapsed');
                resizer.style.display = 'block';
                rightCollapsedTab.style.display = 'none';
            });
        }

        // Help Chatbot logic (Co-Pilot)
        let helpChatHistory = [];
        function setupHelpChat() {
            // Toggle collapse state
            toggleHelpChatBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                const isCollapsed = helpChatPanel.classList.contains('collapsed');
                if (isCollapsed) {
                    helpChatPanel.classList.remove('collapsed');
                    helpChatBody.style.display = 'flex';
                    helpChatToggleArrow.textContent = '▼';
                    setTimeout(() => {
                        helpChatMessages.scrollTop = helpChatMessages.scrollHeight;
                    }, 50);
                } else {
                    helpChatPanel.classList.add('collapsed');
                    helpChatBody.style.display = 'none';
                    helpChatToggleArrow.textContent = '▲';
                }
            });
            
            // Suggestion chips
            document.querySelectorAll('.chat-chip').forEach(chip => {
                chip.addEventListener('click', function(e) {
                    e.stopPropagation();
                    const text = this.getAttribute('data-text');
                    if (text) {
                        helpChatInput.value = text;
                        sendHelpChatMessage();
                    }
                });
            });
            
            // Send button
            sendHelpChatBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                sendHelpChatMessage();
            });
            
            // Enter key
            helpChatInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    sendHelpChatMessage();
                }
            });
        }
        
        function sendHelpChatMessage() {
            const text = helpChatInput.value.trim();
            if (!text) return;
            
            helpChatInput.value = '';
            
            appendChatMessage("user", text);
            const typingIndicator = appendChatMessage("model", "⏳ Co-Pilot is thinking...");
            
            fetch('/help-bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    history: helpChatHistory
                })
            })
            .then(res => {
                if (!res.ok) throw new Error("Server error");
                return res.json();
            })
            .then(data => {
                typingIndicator.remove();
                appendChatMessage("model", data.reply);
                
                helpChatHistory.push({ role: "user", text: text });
                helpChatHistory.push({ role: "model", text: data.reply });
            })
            .catch(err => {
                typingIndicator.remove();
                appendChatMessage("model", "❌ Error: Could not connect to Co-Pilot server.");
            });
        }
        
        function appendChatMessage(role, text) {
            const msgEl = document.createElement('div');
            if (role === 'model' && (text.startsWith('Co-Pilot Error:') || text.startsWith('❌'))) {
                msgEl.className = 'msg msg-model msg-error';
            } else {
                msgEl.className = `msg msg-${role}`;
            }
            
            let parsedText = text
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/\n/g, "<br>")
                .replace(/`([^`]+)`/g, "<code>$1</code>");
                
            msgEl.innerHTML = parsedText;
            helpChatMessages.appendChild(msgEl);
            helpChatMessages.scrollTop = helpChatMessages.scrollHeight;
            return msgEl;
        }

        // Project management helpers
        function clearActiveProjectState() {
            activeProjectId = null;
            projectInfo = null;
            clips = [];
            transcriptionData = null;
            document.getElementById('activeProjectBadge').textContent = "No active project";
            document.getElementById('activeProjectBadge').style.display = "none";
            document.getElementById('activeProjectTitleHeader').textContent = "CLIP PLAN";
            document.getElementById('clipsToolbar').style.display = 'none';
            
            // Clear player
            audioElement.pause();
            audioElement.src = "";
            document.getElementById('nowPlayingTitle').textContent = "No project loaded";
            
            renderClips();
            renderTranscript();
            updateUsedHighlights();
            loadProjectsListOnly();
        }

        function renameProjectPrompt(projectId, currentName) {
            const newName = prompt(`Rename project "${currentName}" to:`, currentName);
            if (!newName || newName.trim() === "" || newName.trim() === currentName) return;
            
            updateStateBar("Renaming project...");
            fetch(`/rename-project?id=${projectId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName.trim() })
            })
            .then(r => {
                if (!r.ok) {
                    return r.text().then(text => { throw new Error(text); });
                }
                return r.json();
            })
            .then(data => {
                if (data.success) {
                    updateStateBar("Project renamed successfully!");
                    if (activeProjectId === projectId) {
                        activeProjectId = data.new_id || projectId;
                        selectProject(activeProjectId);
                    } else {
                        loadProjectsList();
                    }
                } else {
                    throw new Error("Failed to rename project");
                }
            })
            .catch(err => {
                showDebug("Rename project failed: " + err.message, true);
            });
        }
 
        function duplicateProjectPrompt(projectId, currentName) {
            const newName = prompt(`Duplicate project "${currentName}" as:`, `${currentName} Copy`);
            if (!newName || newName.trim() === "") return;
            
            updateStateBar("Duplicating project...");
            fetch(`/duplicate-project?id=${projectId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName.trim() })
            })
            .then(r => {
                if (!r.ok) {
                    return r.text().then(text => { throw new Error(text); });
                }
                return r.json();
            })
            .then(data => {
                if (data.success) {
                    updateStateBar("Project duplicated successfully!");
                    selectProject(data.project_id);
                } else {
                    throw new Error("Failed to duplicate project");
                }
            })
            .catch(err => {
                showDebug("Duplicate project failed: " + err.message, true);
            });
        }
 
        function deleteProjectConfirm(projectId, name) {
            const confirmed = confirm(`Are you sure you want to permanently delete the project "${name}"?\n\nThis will delete all its metadata, segment plans, transcripts, and copied audio files. This action CANNOT be undone.`);
            if (!confirmed) return;
            
            updateStateBar("Deleting project...");
            fetch(`/delete-project?id=${projectId}`, {
                method: 'POST'
            })
            .then(r => {
                if (!r.ok) {
                    return r.text().then(text => { throw new Error(text); });
                }
                return r.json();
            })
            .then(data => {
                if (data.success) {
                    updateStateBar("Project deleted.");
                    if (activeProjectId === projectId) {
                        clearActiveProjectState();
                    } else {
                        loadProjectsList();
                    }
                } else {
                    throw new Error("Failed to delete project");
                }
            })
            .catch(err => {
                showDebug("Delete project failed: " + err.message, true);
            });
        }

        // Load Projects List from Backend
        function loadProjectsList() {
            fetch('/list-projects')
                .then(r => r.json())
                .then(projects => {
                    projectList.innerHTML = '';
                    if (projects.length === 0) {
                        projectList.innerHTML = `<div style="font-size: 0.75rem; color: var(--text-muted); text-align: center; padding: 1rem 0;">No projects. Create one above!</div>`;
                        return;
                    }
                    
                    projects.forEach(p => {
                        const item = document.createElement('div');
                        item.className = `project-nav-item ${activeProjectId === p.id ? 'active' : ''}`;
                        
                        let statusText = 'Ready';
                        if (p.status === 'transcribing') statusText = 'Transcribing...';
                        if (p.status === 'error') statusText = 'Error';
                        
                        item.innerHTML = `
                            <div class="project-nav-content">
                                <span class="project-nav-name">${p.name}</span>
                                <span class="project-status-badge ${p.status}">${statusText}</span>
                            </div>
                            <div class="project-nav-actions" onclick="event.stopPropagation();">
                                <button class="project-action-btn rename-proj-btn" data-id="${p.id}" title="Rename Project">✏️</button>
                                <button class="project-action-btn duplicate-proj-btn" data-id="${p.id}" title="Duplicate Project">👥</button>
                                <button class="project-action-btn delete-proj-btn" data-id="${p.id}" title="Delete Project">🗑</button>
                            </div>
                        `;
                        
                        item.querySelector('.project-nav-content').addEventListener('click', () => {
                            selectProject(p.id);
                        });
                        
                        item.querySelector('.rename-proj-btn').addEventListener('click', (e) => {
                            e.stopPropagation();
                            renameProjectPrompt(p.id, p.name);
                        });
                        
                        item.querySelector('.duplicate-proj-btn').addEventListener('click', (e) => {
                            e.stopPropagation();
                            duplicateProjectPrompt(p.id, p.name);
                        });
                        
                        item.querySelector('.delete-proj-btn').addEventListener('click', (e) => {
                            e.stopPropagation();
                            deleteProjectConfirm(p.id, p.name);
                        });
                        
                        projectList.appendChild(item);
                    });
                    
                    if (!activeProjectId && projects.length > 0) {
                        const firstReady = projects.find(p => p.status === 'ready');
                        if (firstReady) {
                            selectProject(firstReady.id);
                        } else {
                            selectProject(projects[0].id);
                        }
                    } else if (activeProjectId) {
                        const currProj = projects.find(p => p.id === activeProjectId);
                        if (currProj) {
                            if (currProj.status === 'ready' && (!transcriptionData || transcriptionData.segments.length === 0)) {
                                selectProject(activeProjectId);
                            }
                        }
                    }
                })
                .catch(err => {
                    showDebug("Failed to list projects: " + err.message);
                });
        }

        // Active Project Selection
        function selectProject(projectId) {
            if (pollingInterval) {
                clearInterval(pollingInterval);
                pollingInterval = null;
            }
            
            stopLockedSequence();
            
            activeProjectId = projectId;
            
            loadProjectsListOnly();
            
            updateStateBar(`Loading project ${projectId}...`);
            
            fetch(`/get-project?id=${projectId}`)
                .then(r => {
                    if (!r.ok) throw new Error("Could not retrieve project metadata");
                    return r.json();
                })
                .then(data => {
                    projectInfo = data.info;
                    clips = data.plan || [];
                    transcriptionData = data.transcription;
                    compiledVideos = data.compiled_videos || [];
                    clipStatuses = data.clip_statuses || {};
                    
                    // Initialize Undo stack and baseline save state
                    undoStack = [];
                    lastSavedStateString = JSON.stringify(clips);
                    updateUndoButtonState();
                    
                    // Show clips utility toolbar and configure snapshot button
                    clipsToolbar.style.display = 'flex';
                    restoreSnapshotBtn.disabled = !data.has_snapshot;
                    
                    activeProjectBadge.textContent = projectInfo.name;
                    activeProjectTitleHeader.textContent = `${projectInfo.name.toUpperCase()} CLIP PLAN`;
                    nowPlayingTitle.textContent = `${projectInfo.name} (${projectInfo.audio_filename})`;
                    
                    if (projectInfo.status === 'transcribing') {
                        renderTranscribingSpinner();
                        clips = [];
                        renderClips();
                        audioElement.src = '';
                        
                        pollingInterval = setInterval(() => {
                            pollProjectStatus(projectId);
                        }, 4000);
                        
                        updateStateBar("Transcribing in background...");
                    } else if (projectInfo.status === 'error') {
                        renderErrorState(projectInfo.error_message || "Unknown Whisper transcription error.");
                        clips = [];
                        renderClips();
                        audioElement.src = '';
                        updateStateBar("Ready (error status)");
                    } else {
                        renderTranscription();
                        renderClips();
                        
                        audioElement.src = `/project-audio?id=${projectId}`;
                        updateStateBar("Ready");
                    }
                })
                .catch(err => {
                    showDebug("Failed loading project details: " + err.message);
                    updateStateBar("Ready");
                });
        }

        function loadProjectsListOnly() {
            fetch('/list-projects')
                .then(r => r.json())
                .then(projects => {
                    projectList.innerHTML = '';
                    projects.forEach(p => {
                        const item = document.createElement('div');
                        item.className = `project-nav-item ${activeProjectId === p.id ? 'active' : ''}`;
                        
                        let statusText = 'Ready';
                        if (p.status === 'transcribing') statusText = 'Transcribing...';
                        if (p.status === 'error') statusText = 'Error';
                        
                        item.innerHTML = `
                            <div class="project-nav-content">
                                <span class="project-nav-name">${p.name}</span>
                                <span class="project-status-badge ${p.status}">${statusText}</span>
                            </div>
                            <div class="project-nav-actions" onclick="event.stopPropagation();">
                                <button class="project-action-btn rename-proj-btn" data-id="${p.id}" title="Rename Project">✏️</button>
                                <button class="project-action-btn duplicate-proj-btn" data-id="${p.id}" title="Duplicate Project">👥</button>
                                <button class="project-action-btn delete-proj-btn" data-id="${p.id}" title="Delete Project">🗑</button>
                            </div>
                        `;
                        
                        item.querySelector('.project-nav-content').addEventListener('click', () => {
                            selectProject(p.id);
                        });
                        
                        item.querySelector('.rename-proj-btn').addEventListener('click', (e) => {
                            e.stopPropagation();
                            renameProjectPrompt(p.id, p.name);
                        });
                        
                        item.querySelector('.duplicate-proj-btn').addEventListener('click', (e) => {
                            e.stopPropagation();
                            duplicateProjectPrompt(p.id, p.name);
                        });
                        
                        item.querySelector('.delete-proj-btn').addEventListener('click', (e) => {
                            e.stopPropagation();
                            deleteProjectConfirm(p.id, p.name);
                        });
                        
                        projectList.appendChild(item);
                    });
                });
        }

        function pollProjectStatus(projectId) {
            fetch(`/get-project?id=${projectId}`)
                .then(r => r.json())
                .then(data => {
                    if (data.info.status === 'ready') {
                        clearInterval(pollingInterval);
                        pollingInterval = null;
                        selectProject(projectId);
                        showDebug(`Whisper transcription completed for ${data.info.name}!`, false);
                    } else if (data.info.status === 'error') {
                        clearInterval(pollingInterval);
                        pollingInterval = null;
                        selectProject(projectId);
                        showDebug(`Transcription failed for ${data.info.name}.`, true);
                    }
                })
                .catch(err => {
                    console.warn("Polling status error: ", err);
                });
        }

        function renderTranscribingSpinner() {
            transcriptContainer.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="animation: pulse-opacity 1.2s infinite ease-in-out;">
                        <path d="M12 6v6m0 0v6m0-6h6m-6 0H6" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    <h3 style="margin-top: 1rem; color: var(--text-main);">Transcribing Media...</h3>
                    <p style="margin-top: 0.5rem; max-width: 320px;">OpenAI Whisper is currently transcribing the audio file in the background. The transcript will load automatically once complete.</p>
                </div>
            `;
            segmentCount.textContent = '0 words loaded';
        }

        function renderErrorState(errText) {
            transcriptContainer.innerHTML = `
                <div class="empty-state" style="color: var(--danger);">
                    <svg viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="1.5">
                        <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    <h3 style="margin-top: 1rem;">Transcription Failed</h3>
                    <p style="margin-top: 0.5rem; color: var(--text-muted); max-width: 320px;">${errText}</p>
                </div>
            `;
            segmentCount.textContent = '0 words loaded';
        }

        // Project Creation Modal Control
        newProjectBtn.addEventListener('click', () => {
            updateStateBar("Loading audio files...");
            fetch('/list-workspace-audio')
                .then(r => r.json())
                .then(files => {
                    newProjectAudioSelect.innerHTML = '';
                    if (files.length === 0) {
                        newProjectAudioSelect.innerHTML = `<option value="">No audio files found in root (.mp3, .m4a, .wav)</option>`;
                    } else {
                        files.forEach(f => {
                            const opt = document.createElement('option');
                            opt.value = f;
                            opt.textContent = f;
                            newProjectAudioSelect.appendChild(opt);
                        });
                    }
                    projectModalOverlay.classList.add('active');
                    updateStateBar("Ready");
                })
                .catch(err => {
                    showDebug("Failed to list workspace audio: " + err.message);
                });
        });

        closeProjectModalBtn.addEventListener('click', hideProjectModal);
        cancelProjectBtn.addEventListener('click', hideProjectModal);

        function hideProjectModal() {
            projectModalOverlay.classList.remove('active');
            newProjectNameInput.value = '';
        }

        saveProjectBtn.addEventListener('click', () => {
            const name = newProjectNameInput.value.trim();
            const audioSource = newProjectAudioSelect.value;
            
            if (!name) {
                alert("Please enter a project name.");
                return;
            }
            if (!audioSource) {
                alert("Please select a workspace audio file.");
                return;
            }
            
            updateStateBar("Creating project...");
            saveProjectBtn.disabled = true;
            saveProjectBtn.innerHTML = '⏳ Creating...';
            
            fetch('/create-project', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, audio_source: audioSource })
            })
            .then(res => {
                saveProjectBtn.disabled = false;
                saveProjectBtn.innerHTML = 'Create & Transcribe';
                if (!res.ok) return res.text().then(text => { throw new Error(text) });
                return res.json();
            })
            .then(data => {
                hideProjectModal();
                activeProjectId = data.project_id;
                loadProjectsList();
                showDebug(`Project "${name}" successfully created! Starting Whisper...`, false);
            })
            .catch(err => {
                saveProjectBtn.disabled = false;
                saveProjectBtn.innerHTML = 'Create & Transcribe';
                showDebug("Failed to create project: " + err.message);
            });
        });

        // Audio Player Controls
        playBtn.addEventListener('click', function() {
            if (audioElement.paused) {
                audioElement.play();
                playBtn.textContent = '⏸';
            } else {
                audioElement.pause();
                playBtn.textContent = '▶';
            }
        });

        audioElement.addEventListener('timeupdate', function() {
            if (audioElement.duration) {
                playerSlider.value = (audioElement.currentTime / audioElement.duration) * 100;
                currTime.textContent = formatTime(audioElement.currentTime);
            }
        });

        audioElement.addEventListener('loadedmetadata', function() {
            totTime.textContent = formatTime(audioElement.duration);
        });

        audioElement.addEventListener('loadstart', function() {
            const src = audioElement.getAttribute('src') || audioElement.src;
            if (src && src !== "" && !src.endsWith('#') && !src.endsWith('curator.html')) {
                playerDownloadBtn.href = src;
                playerDownloadBtn.style.display = 'inline-flex';
                let filename = "audio_clip.mp3";
                if (src.includes("combined_")) {
                    filename = `combined_${activeProjectId}.mp3`;
                } else if (src.includes("preview_")) {
                    filename = `preview_${activeProjectId}.mp3`;
                } else if (src.includes("project-audio")) {
                    filename = `${activeProjectId}_full.mp3`;
                }
                playerDownloadBtn.download = filename;
            } else {
                playerDownloadBtn.style.display = 'none';
            }
        });

        playerSlider.addEventListener('input', function() {
            if (audioElement.duration) {
                audioElement.currentTime = (playerSlider.value / 100) * audioElement.duration;
            }
        });

        function formatTime(secs) {
            const mins = Math.floor(secs / 60);
            const remainingSecs = Math.floor(secs % 60);
            return `${mins.toString().padStart(2, '0')}:${remainingSecs.toString().padStart(2, '0')}`;
        }

        // Render Word-by-Word Transcription
        function renderTranscription() {
            if (!transcriptionData) return;
            const segments = transcriptionData.segments || [];
            allWords = [];
            
            if (segments.length === 0) {
                transcriptContainer.innerHTML = '<div class="empty-state"><p>No segments found in file.</p></div>';
                return;
            }

            transcriptContainer.innerHTML = '';
            
            segments.forEach((seg, segIdx) => {
                const para = document.createElement('p');
                para.className = 'transcript-paragraph';
                
                const wordsList = seg.words || [];
                
                if (wordsList.length === 0) {
                    const roughWords = seg.text.trim().split(/\s+/);
                    const dur = seg.end - seg.start;
                    const step = dur / Math.max(1, roughWords.length);
                    roughWords.forEach((wordText, wIdx) => {
                        wordsList.push({
                            word: wordText,
                            start: seg.start + (wIdx * step),
                            end: seg.start + ((wIdx + 1) * step)
                        });
                    });
                }
                
                wordsList.forEach((wordObj) => {
                    const wordIdx = allWords.length;
                    allWords.push({
                        word: wordObj.word,
                        start: wordObj.start,
                        end: wordObj.end,
                        idx: wordIdx
                    });
                    
                    const wordSpan = document.createElement('span');
                    wordSpan.className = 'word';
                    wordSpan.textContent = wordObj.word + " ";
                    wordSpan.dataset.wordIdx = wordIdx;
                    
                    wordSpan.addEventListener('click', function(e) {
                        handleWordClick(wordIdx);
                    });
                    
                    para.appendChild(wordSpan);
                });
                
                transcriptContainer.appendChild(para);
            });
            
            segmentCount.textContent = `${allWords.length} words loaded`;
        }

        // Right-Click Context Menu Trigger on word elements
        transcriptContainer.addEventListener('contextmenu', function(e) {
            const wordEl = e.target.closest('.word');
            if (wordEl) {
                e.preventDefault();
                ctxWordIdx = parseInt(wordEl.dataset.wordIdx);
                
                contextMenu.style.left = `${e.pageX}px`;
                contextMenu.style.top = `${e.pageY}px`;
                contextMenu.style.display = 'block';
            }
        });

        // Hide context menu on click elsewhere
        document.addEventListener('click', function(e) {
            if (!e.target.closest('#contextMenu')) {
                contextMenu.style.display = 'none';
            }
        });

        document.getElementById('ctxSetStart').addEventListener('click', function() {
            if (ctxWordIdx !== null) {
                startWordIdx = ctxWordIdx;
                if (endWordIdx !== null && endWordIdx < startWordIdx) {
                    endWordIdx = null;
                }
                updateSelectionUI();
            }
            contextMenu.style.display = 'none';
        });

        document.getElementById('ctxSetEnd').addEventListener('click', function() {
            if (ctxWordIdx !== null) {
                if (startWordIdx === null) {
                    startWordIdx = ctxWordIdx;
                } else if (ctxWordIdx < startWordIdx) {
                    alert("End word cannot be before start word!");
                    return;
                } else {
                    endWordIdx = ctxWordIdx;
                }
                updateSelectionUI();
            }
            contextMenu.style.display = 'none';
        });

        document.getElementById('ctxClear').addEventListener('click', function() {
            startWordIdx = null;
            endWordIdx = null;
            updateSelectionUI();
            contextMenu.style.display = 'none';
        });

        // Search highlight functionality
        searchInput.addEventListener('input', function(e) {
            activeSearchQuery = e.target.value.toLowerCase().trim();
            const wordSpans = transcriptContainer.querySelectorAll('.word');
            
            wordSpans.forEach(span => {
                const text = span.textContent.toLowerCase();
                if (activeSearchQuery !== "" && text.includes(activeSearchQuery)) {
                    span.classList.add('search-match');
                } else {
                    span.classList.remove('search-match');
                }
            });
        });

        // Click Word Handler
        function handleWordClick(idx) {
            if (startWordIdx === null || (startWordIdx !== null && endWordIdx !== null)) {
                startWordIdx = idx;
                endWordIdx = null;
            } else {
                if (idx < startWordIdx) {
                    endWordIdx = startWordIdx;
                    startWordIdx = idx;
                } else {
                    endWordIdx = idx;
                }
            }
            updateSelectionUI();
        }

        // Toggle used highlights button
        toggleUsedBtn.addEventListener('click', function() {
            showUsedRanges = !showUsedRanges;
            if (showUsedRanges) {
                toggleUsedBtn.classList.add('btn-accent');
            } else {
                toggleUsedBtn.classList.remove('btn-accent');
            }
            updateUsedHighlights();
        });

        function updateUsedHighlights() {
            const wordSpans = transcriptContainer.querySelectorAll('.word');
            wordSpans.forEach(span => span.classList.remove('used-word'));
            
            if (!showUsedRanges) return;
            
            const ranges = [];
            clips.forEach(clip => {
                (clip.segments || []).forEach(seg => {
                    if (seg.type === 'audio') {
                        ranges.push({ start: seg.start, end: seg.end });
                    }
                });
            });
            
            wordSpans.forEach(span => {
                const idx = parseInt(span.dataset.wordIdx);
                if (idx >= 0 && idx < allWords.length) {
                    const word = allWords[idx];
                    const isUsed = ranges.some(r => word.start >= r.start && word.end <= r.end);
                    if (isUsed) {
                        span.classList.add('used-word');
                    }
                }
            });
        }

        // Segment selection and live adjustments!
        function selectSegmentForEditing(clipIdx, segIdx) {
            if (clips[clipIdx].locked) {
                console.log("Ignored segment selection: Clip is locked.");
                return;
            }
            
            editingSegmentRef = { clipIdx, segIdx };
            const seg = clips[clipIdx].segments[segIdx];
            
            document.querySelectorAll('.segment-row').forEach(row => {
                row.style.border = '1px solid rgba(255, 255, 255, 0.05)';
                row.style.backgroundColor = 'rgba(255, 255, 255, 0.02)';
            });
            
            const activeRow = document.querySelector(`.segment-row[data-clip="${clipIdx}"][data-seg="${segIdx}"]`);
            if (activeRow) {
                activeRow.style.border = '1px solid var(--primary)';
                activeRow.style.backgroundColor = 'rgba(99, 102, 241, 0.08)';
            }
            
            startWordIdx = findWordIdxByTime(seg.start, 'start');
            endWordIdx = findWordIdxByTime(seg.end, 'end');
            
            updateSelectionUIOnly();
            
            const startWordEl = transcriptContainer.querySelector(`[data-word-idx="${startWordIdx}"]`);
            if (startWordEl) {
                startWordEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            
            updateStateBar(`Editing Segment #${segIdx + 1} of Clip: "${clips[clipIdx].title}"`);
        }

        function updateSelectionUIOnly() {
            const wordSpans = transcriptContainer.querySelectorAll('.word');
            wordSpans.forEach((span) => {
                const idx = parseInt(span.dataset.wordIdx);
                span.className = 'word';
                
                if (activeSearchQuery !== "" && span.textContent.toLowerCase().includes(activeSearchQuery)) {
                    span.classList.add('search-match');
                }
                if (showUsedRanges) {
                    const word = allWords[idx];
                    const isUsed = clips.some(clip => 
                        (clip.segments || []).some(s => s.type === 'audio' && word.start >= s.start && word.end <= s.end)
                    );
                    if (isUsed) span.classList.add('used-word');
                }
                
                if (idx === startWordIdx && endWordIdx === null) {
                    span.classList.add('start-word');
                } else if (idx === startWordIdx) {
                    span.classList.add('start-word');
                } else if (idx === endWordIdx) {
                    span.classList.add('end-word');
                } else if (startWordIdx !== null && endWordIdx !== null && idx > startWordIdx && idx < endWordIdx) {
                    span.classList.add('in-range');
                }
            });

            if (startWordIdx !== null) {
                const startVal = allWords[startWordIdx].start;
                const endVal = endWordIdx !== null ? allWords[endWordIdx].end : allWords[startWordIdx].end;
                const durationVal = parseFloat((endVal - startVal).toFixed(2));
                
                selStart.textContent = startVal.toFixed(2);
                selEnd.textContent = endVal.toFixed(2);
                selDuration.textContent = durationVal.toFixed(2);
            }
        }

        function updateSelectionUI() {
            updateSelectionUIOnly();

            if (startWordIdx !== null) {
                const startVal = allWords[startWordIdx].start;
                const endVal = endWordIdx !== null ? allWords[endWordIdx].end : allWords[startWordIdx].end;
                const durationVal = parseFloat((endVal - startVal).toFixed(2));

                // If editing a segment, live update it!
                if (editingSegmentRef !== null) {
                    const { clipIdx, segIdx } = editingSegmentRef;
                    
                    if (clips[clipIdx].locked) {
                        return; // Lock guard
                    }
                    
                    let selectedText = "";
                    const endIdx = endWordIdx !== null ? endWordIdx : startWordIdx;
                    for (let i = startWordIdx; i <= endIdx; i++) {
                        selectedText += allWords[i].word + " ";
                    }
                    
                    clips[clipIdx].segments[segIdx].start = parseFloat(startVal.toFixed(2));
                    clips[clipIdx].segments[segIdx].end = parseFloat(endVal.toFixed(2));
                    clips[clipIdx].segments[segIdx].duration = durationVal;
                    clips[clipIdx].segments[segIdx].text = selectedText.trim();
                    
                    const activeRow = document.querySelector(`.segment-row[data-clip="${clipIdx}"][data-seg="${segIdx}"]`);
                    if (activeRow) {
                        const metaEl = activeRow.querySelector('.segment-meta');
                        const textEl = activeRow.querySelector('.segment-text');
                        if (metaEl) metaEl.textContent = `🎙 Audio Segment (${durationVal}s)`;
                        if (textEl) textEl.textContent = `"${selectedText.trim()}"`;
                    }
                    
                    const card = clipListContainer.querySelector(`.clip-card[data-index="${clipIdx}"]`);
                    if (card) {
                        const totalDuration = calculateClipDuration(clips[clipIdx]);
                        const durInput = card.querySelector('.clip-dur-input');
                        if (durInput) durInput.value = totalDuration.toFixed(2);
                    }
                    
                    updateUsedHighlights();
                    savePlanToServer();
                }

                // Play preview on audio element
                audioElement.currentTime = startVal;
                audioElement.play();
                playBtn.textContent = '⏸';
                
                if (window.activeAudioCheck) clearInterval(window.activeAudioCheck);
                window.activeAudioCheck = setInterval(() => {
                    if (audioElement.currentTime >= endVal || audioElement.paused) {
                        audioElement.pause();
                        playBtn.textContent = '▶';
                        clearInterval(window.activeAudioCheck);
                    }
                }, 100);
            } else {
                selStart.textContent = '--';
                selEnd.textContent = '--';
                selDuration.textContent = '0.00';
            }
        }

        // Helper to find closest word index by time
        function findWordIdxByTime(time, field='start') {
            let closestIdx = 0;
            let minDiff = Infinity;
            for (let i = 0; i < allWords.length; i++) {
                let diff = Math.abs(allWords[i][field] - time);
                if (diff < minDiff) {
                    minDiff = diff;
                    closestIdx = i;
                }
            }
            return closestIdx;
        }

        // Add Segment Logic
        function addAudioSegmentToClip(clipIdx) {
            if (clips[clipIdx].locked) return;
            
            if (startWordIdx === null) {
                alert("Please select an audio range from the transcript first.");
                return;
            }
            
            const startVal = allWords[startWordIdx].start;
            const endVal = endWordIdx !== null ? allWords[endWordIdx].end : allWords[startWordIdx].end;
            const durVal = parseFloat((endVal - startVal).toFixed(2));
            
            let selectedText = "";
            const endIdx = endWordIdx !== null ? endWordIdx : startWordIdx;
            for (let i = startWordIdx; i <= endIdx; i++) {
                selectedText += allWords[i].word + " ";
            }
            
            clips[clipIdx].segments.push({
                type: "audio",
                start: parseFloat(startVal.toFixed(2)),
                end: parseFloat(endVal.toFixed(2)),
                duration: durVal,
                text: selectedText.trim()
            });
            
            startWordIdx = null;
            endWordIdx = null;
            updateSelectionUI();
            
            renderClips();
            updateUsedHighlights();
            savePlanToServer();
        }

        function addMusicSegmentToClip(clipIdx) {
            if (clips[clipIdx].locked) return;
            
            clips[clipIdx].segments.push({
                type: "music",
                music_file: availableMusicFiles[0] || "none",
                duration: 4.5,
                crossfade: 0.3
            });
            
            renderClips();
            savePlanToServer();
        }

        // Remove Segment
        function removeSegment(clipIdx, segIdx) {
            if (clips[clipIdx].locked) return;
            
            clips[clipIdx].segments.splice(segIdx, 1);
            if (editingSegmentRef && editingSegmentRef.clipIdx === clipIdx && editingSegmentRef.segIdx === segIdx) {
                editingSegmentRef = null;
            }
            renderClips();
            updateUsedHighlights();
            savePlanToServer();
        }

        function updateSegmentField(clipIdx, segIdx, field, value) {
            if (clips[clipIdx].locked) return;
            
            clips[clipIdx].segments[segIdx][field] = value;
            savePlanToServer();
        }

        // Toggle card lock state
        function toggleClipLock(clipIdx, event) {
            event.stopPropagation();
            clips[clipIdx].locked = !clips[clipIdx].locked;
            
            if (clips[clipIdx].locked && editingSegmentRef && editingSegmentRef.clipIdx === clipIdx) {
                editingSegmentRef = null;
            }
            
            renderClips();
            savePlanToServer();
        }

        // Move Segment Up
        function moveSegmentUp(clipIdx, segIdx) {
            if (clips[clipIdx].locked) return;
            if (segIdx <= 0) return;
            
            const segs = clips[clipIdx].segments;
            const temp = segs[segIdx];
            segs[segIdx] = segs[segIdx - 1];
            segs[segIdx - 1] = temp;
            
            // Adjust active editing selection reference if active
            if (editingSegmentRef && editingSegmentRef.clipIdx === clipIdx) {
                if (editingSegmentRef.segIdx === segIdx) {
                    editingSegmentRef.segIdx = segIdx - 1;
                } else if (editingSegmentRef.segIdx === segIdx - 1) {
                    editingSegmentRef.segIdx = segIdx;
                }
            }
            
            renderClips();
            savePlanToServer();
        }

        // Move Segment Down
        function moveSegmentDown(clipIdx, segIdx) {
            if (clips[clipIdx].locked) return;
            const segs = clips[clipIdx].segments;
            if (segIdx >= segs.length - 1) return;
            
            const temp = segs[segIdx];
            segs[segIdx] = segs[segIdx + 1];
            segs[segIdx + 1] = temp;
            
            // Adjust active editing selection reference if active
            if (editingSegmentRef && editingSegmentRef.clipIdx === clipIdx) {
                if (editingSegmentRef.segIdx === segIdx) {
                    editingSegmentRef.segIdx = segIdx + 1;
                } else if (editingSegmentRef.segIdx === segIdx + 1) {
                    editingSegmentRef.segIdx = segIdx;
                }
            }
            
            renderClips();
            savePlanToServer();
        }

        // Copy Segment to Clipboard
        function copySegment(clipIdx, segIdx) {
            const seg = clips[clipIdx].segments[segIdx];
            if (!seg) return;
            
            segmentClipboard = JSON.parse(JSON.stringify(seg));
            
            const episodeNum = (projectInfo && projectInfo.name) ? (projectInfo.name.match(/\d+/)?.[0] || projectInfo.name) : "244";
            updateStateBar(`Copied segment (from Clip ${episodeNum}-${clips[clipIdx].num}) to clipboard`);
            
            // Re-render clips to show the newly enabled "Paste Segment" button
            renderClips();
        }

        // Paste Segment from Clipboard
        function pasteSegment(clipIdx) {
            if (clips[clipIdx].locked) return;
            if (!segmentClipboard) return;
            
            // Push deep copy of clipboard segment to the top (index 0)
            const copy = JSON.parse(JSON.stringify(segmentClipboard));
            clips[clipIdx].segments.unshift(copy);
            
            const episodeNum = (projectInfo && projectInfo.name) ? (projectInfo.name.match(/\d+/)?.[0] || projectInfo.name) : "244";
            updateStateBar(`Pasted segment to Clip ${episodeNum}-${clips[clipIdx].num}`);
            
            renderClips();
            updateUsedHighlights();
            savePlanToServer();
        }

        // Stop active locked sequence playback
        function stopLockedSequence() {
            if (activeLockedSequence !== null) {
                activeLockedSequence = null;
                sequencePlayIdx = -1;
                audioElement.pause();
                audioElement.src = `/project-audio?id=${activeProjectId}`;
                audioElement.onended = null;
                
                // Clear any border highlights on cards
                document.querySelectorAll('.clip-card').forEach(c => c.style.borderColor = '');
                
                // Update all card buttons to '▶ Audio'
                const cardPlayBtns = document.querySelectorAll('.btn-card-play');
                cardPlayBtns.forEach(btn => {
                    btn.innerHTML = '▶ Audio';
                });
                
                playBtn.textContent = '▶';
                activeClipPlayIdx = null;
                playLockedBtn.innerHTML = '▶ Play Locked';
                updateStateBar("Ready");
            }
        }

        // Play next step of locked sequence
        function playSequenceStep() {
            if (activeLockedSequence === null) return;
            if (sequencePlayIdx < 0 || sequencePlayIdx >= activeLockedSequence.length) {
                stopLockedSequence();
                return;
            }
            
            const clipIdx = activeLockedSequence[sequencePlayIdx];
            const clip = clips[clipIdx];
            
            // Check if clip actually has segments
            if (clip.segments.length === 0) {
                // If a locked clip has no segments, skip it and go to the next
                sequencePlayIdx++;
                playSequenceStep();
                return;
            }
            
            const btnEl = document.getElementById(`playCardBtn_${clipIdx}`);
            if (btnEl) {
                btnEl.innerHTML = '⏳ Compiling...';
            }
            
            updateStateBar(`Compiling preview ${sequencePlayIdx + 1}/${activeLockedSequence.length} for: "${clip.title}"...`);
            
            const cardEl = document.getElementById(`clipCard_${clipIdx}`);
            if (cardEl) {
                cardEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                document.querySelectorAll('.clip-card').forEach(c => c.style.borderColor = '');
                cardEl.style.borderColor = 'var(--primary)';
            }
            
            fetch(`/compile-project-preview?id=${activeProjectId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    clip_idx: clipIdx,
                    segments: clip.segments
                })
            })
            .then(res => {
                if (!res.ok) throw new Error("Compilation server error");
                return res.json();
            })
            .then(data => {
                if (activeLockedSequence === null) return;
                
                if (btnEl) {
                    btnEl.innerHTML = '⏸ Pause';
                }
                playBtn.textContent = '⏸';
                activeClipPlayIdx = clipIdx;
                
                audioElement.src = data.preview_url;
                audioElement.volume = 1.0;
                audioElement.play()
                    .then(() => {
                        updateStateBar(`Playing sequence (${sequencePlayIdx + 1}/${activeLockedSequence.length}): "${clip.title}"`);
                    })
                    .catch(err => {
                        showDebug("Failed to play preview file: " + err.message);
                    });
                
                audioElement.onended = () => {
                    if (activeLockedSequence === null) return;
                    if (btnEl) {
                        btnEl.innerHTML = '▶ Audio';
                    }
                    if (cardEl) cardEl.style.borderColor = '';
                    sequencePlayIdx++;
                    playSequenceStep();
                };
            })
            .catch(err => {
                if (btnEl) {
                    btnEl.innerHTML = '▶ Audio';
                }
                showDebug("FFmpeg sequence step failed: " + err.message);
                updateStateBar("Ready");
                stopLockedSequence();
            });
        }

        // Play Locked button listener
        playLockedBtn.addEventListener('click', () => {
            if (!activeProjectId) return;
            
            if (activeLockedSequence !== null) {
                stopLockedSequence();
            } else {
                const locked = clips.filter(c => c.locked);
                if (locked.length === 0) {
                    alert("No clips are locked yet. Toggle the lock icon on some cards first!");
                    return;
                }
                
                activeLockedSequence = locked.map(c => clips.indexOf(c));
                sequencePlayIdx = 0;
                playLockedBtn.innerHTML = '⏹ Stop Locked';
                playSequenceStep();
            }
        });

        // Compile and Play FFmpeg preview
        function playFFmpegPreview(clipIdx, btnEl, event) {
            event.stopPropagation();
            
            if (activeLockedSequence !== null) {
                stopLockedSequence();
            }
            
            if (activeClipPlayIdx === clipIdx && !audioElement.paused) {
                audioElement.pause();
                btnEl.innerHTML = '▶ Audio';
                playBtn.textContent = '▶';
                activeClipPlayIdx = null;
                updateStateBar("Ready");
                return;
            }
            
            const clip = clips[clipIdx];
            if (clip.segments.length === 0) {
                alert("This clip has no segments. Add some audio or music segments first.");
                return;
            }
            
            btnEl.innerHTML = '⏳ Compiling...';
            btnEl.disabled = true;
            updateStateBar(`Compiling preview for: "${clip.title}"...`);
            
            fetch(`/compile-project-preview?id=${activeProjectId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    clip_idx: clipIdx,
                    segments: clip.segments
                })
            })
            .then(res => {
                if (!res.ok) throw new Error("Compilation server error");
                return res.json();
            })
            .then(data => {
                btnEl.disabled = false;
                btnEl.innerHTML = '⏸ Pause';
                playBtn.textContent = '⏸';
                activeClipPlayIdx = clipIdx;
                
                audioElement.src = data.preview_url;
                audioElement.volume = 1.0;
                audioElement.play()
                    .then(() => {
                        updateStateBar(`Playing preview: "${clip.title}"`);
                    })
                    .catch(err => {
                        showDebug("Failed to play preview file: " + err.message);
                    });
                
                audioElement.onended = () => {
                    btnEl.innerHTML = '▶ Audio';
                    playBtn.textContent = '▶';
                    activeClipPlayIdx = null;
                    audioElement.src = `/project-audio?id=${activeProjectId}`;
                    updateStateBar("Ready");
                };
            })
            .catch(err => {
                btnEl.disabled = false;
                btnEl.innerHTML = '▶ Audio';
                showDebug("FFmpeg preview compilation failed: " + err.message);
                updateStateBar("Ready (compilation failed)");
            });
        }

        // Export Individual Clip File
        function exportClipAudio(clipIdx, btnEl, event) {
            event.stopPropagation();
            const clip = clips[clipIdx];
            if (clip.segments.length === 0) {
                alert("This clip has no segments to export.");
                return;
            }

            btnEl.innerHTML = '⏳ Exporting...';
            btnEl.disabled = true;
            updateStateBar(`Compiling final clip: "${clip.title}"...`);

            // Read settings from localStorage
            const format = localStorage.getItem('ddma-export-format') || 'audio';
            const res = localStorage.getItem('ddma-video-res') || '740x740';
            const bg = localStorage.getItem('ddma-video-bg') || 'black';

            fetch(`/export-project-clip?id=${activeProjectId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    clip_num: clip.num,
                    title: clip.title,
                    segments: clip.segments,
                    export_format: format,
                    resolution: res,
                    bg_color: bg
                })
            })
            .then(res => {
                if (!res.ok) throw new Error("Export compilation failed");
                return res.json();
            })
            .then(data => {
                btnEl.disabled = false;
                btnEl.innerHTML = '📤 Exported';
                updateStateBar(`Ready`);
                showDebug(`Exported successfully to: ${data.filename}`, false);
                fetchCompiledVideos();
            })
            .catch(err => {
                btnEl.disabled = false;
                btnEl.innerHTML = '📤 Export Clip';
                showDebug("Export clip failed: " + err.message);
                updateStateBar("Ready (export failed)");
            });
        }

        function exportToMosaic(clipIdx, btnEl) {
            const clip = clips[clipIdx];
            if (!activeProjectId) return;
            
            const apiKey = localStorage.getItem('ddma-mosaic-api-key') || '';
            const agentId = localStorage.getItem('ddma-mosaic-agent-id') || '';
            
            if (!apiKey || !agentId) {
                alert("Mosaic API Key and Agent ID must be configured in System Settings first.");
                settingsBtn.click();
                return;
            }
            
            const statusInfo = clipStatuses[clip.num] || { has_audio: false, video_state: "none" };
            const hasExistingVideo = (statusInfo.video_state === 'compiled' || statusInfo.video_state === 'draft');
            
            let force = false;
            if (clip.mosaic_run_id) {
                const reuse = confirm(`A previous Mosaic run was detected for Clip ${clip.num}.\n\nClick [OK] to recover/download the previous render instantly.\nClick [Cancel] to trigger a brand-new run.`);
                if (!reuse) {
                    force = true;
                    if (hasExistingVideo) {
                        const confirmOverwrite = confirm(`WARNING: A compiled video already exists for Clip ${clip.num}.\n\nTriggering a brand-new run will delete the existing video file.\n\nAre you sure you want to overwrite it?`);
                        if (!confirmOverwrite) return;
                    }
                }
            } else if (hasExistingVideo) {
                const confirmOverwrite = confirm(`WARNING: A compiled video already exists for Clip ${clip.num}.\n\nTriggering a new Mosaic run will delete the existing video file.\n\nAre you sure you want to overwrite it?`);
                if (!confirmOverwrite) return;
            }
            
            function triggerExport(customPrompt) {
                btnEl.disabled = true;
                btnEl.innerHTML = '⏳ Starting...';
                btnEl.style.backgroundImage = 'linear-gradient(135deg, #4b5563 0%, #374151 100%)';
                updateStateBar(`Mosaic: Initializing run for Clip ${clip.num}...`);
                
                fetch(`/export-to-mosaic?id=${activeProjectId}&num=${clip.num}&force=${force}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: customPrompt })
                })
                .then(res => {
                    if (!res.ok) {
                        return res.json().then(data => {
                            throw new Error(data.error || "Failed to start Mosaic pipeline.");
                        });
                    }
                    return res.json();
                })
                .then(data => {
                    fetchCompiledVideos();
                })
                .catch(err => {
                    btnEl.disabled = false;
                    btnEl.innerHTML = '🌌 Mosaic';
                    btnEl.style.backgroundImage = 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)';
                    showDebug("Mosaic failed: " + err.message, true);
                    updateStateBar("Ready (Mosaic start failed)");
                });
            }

            if (!clip.mosaic_run_id || force) {
                // Fetch default prompt from server
                btnEl.disabled = true;
                btnEl.innerHTML = '⏳ Loading Prompt...';
                updateStateBar(`Mosaic: Generating base prompt for Clip ${clip.num}...`);
                
                fetch(`/get-mosaic-prompt?id=${activeProjectId}&num=${clip.num}`)
                .then(res => {
                    if (!res.ok) throw new Error("Failed to get base prompt.");
                    return res.json();
                })
                .then(data => {
                    btnEl.disabled = false;
                    btnEl.innerHTML = '🌌 Mosaic';
                    btnEl.style.backgroundImage = 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)';
                    updateStateBar("Ready");
                    
                    if (data.success && data.prompt) {
                        mosaicPromptTextarea.value = data.prompt;
                        mosaicPromptModalOverlay.classList.add('active');
                        
                        // Override submit click listener by replacing the element
                        const newSubmitBtn = submitMosaicPromptBtn.cloneNode(true);
                        submitMosaicPromptBtn.parentNode.replaceChild(newSubmitBtn, submitMosaicPromptBtn);
                        
                        const activeSubmitBtn = document.getElementById('submitMosaicPromptBtn');
                        activeSubmitBtn.addEventListener('click', function() {
                            const customPromptText = mosaicPromptTextarea.value.trim();
                            mosaicPromptModalOverlay.classList.remove('active');
                            triggerExport(customPromptText);
                        });
                    } else {
                        alert("Could not load base prompt: " + (data.error || "unknown error"));
                    }
                })
                .catch(err => {
                    btnEl.disabled = false;
                    btnEl.innerHTML = '🌌 Mosaic';
                    btnEl.style.backgroundImage = 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)';
                    updateStateBar("Ready");
                    alert("Error fetching prompt: " + err.message);
                });
            } else {
                // Recover completed or active run
                triggerExport("");
            }
        }
        
        function remixClip(clipIdx, btnEl) {
            const clip = clips[clipIdx];
            if (!activeProjectId) return;
            
            const directive = prompt(
                `Are you sure you want to remix Clip ${clip.num}?\n\nThis will use Creative AI to autonomously recast the clip's segments, title, and bridge text based on preceding locked clips.\n\nOptionally enter steering instructions for Gemini (e.g. 'skip Newton, focus on the next topic'):`,
                ""
            );
            if (directive === null) return; // User cancelled
            
            btnEl.disabled = true;
            btnEl.innerHTML = '⏳ Remixing...';
            btnEl.classList.remove('btn-status-purple');
            btnEl.classList.add('btn-status-warning');
            updateStateBar(`Remixing: Recasting Clip ${clip.num}...`);
            
            fetch(`/remix-clip?id=${activeProjectId}&num=${clip.num}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ directive: directive.trim() })
            })
            .then(res => {
                if (!res.ok) {
                    return res.json().then(data => {
                        throw new Error(data.error || "Failed to remix clip.");
                    });
                }
                return res.json();
            })
            .then(data => {
                if (data.success) {
                    showDebug(`Clip ${clip.num} successfully remixed!`);
                    updateStateBar(`Clip ${clip.num} successfully remixed.`);
                    selectProject(activeProjectId);
                } else {
                    throw new Error(data.error || "Unknown remix error.");
                }
            })
            .catch(err => {
                console.error("Remix failed:", err);
                showDebug("Remix failed: " + err.message);
                updateStateBar("Ready (remix failed)");
                btnEl.disabled = false;
                btnEl.innerHTML = '🔄 Remix';
                btnEl.classList.remove('btn-status-warning');
                btnEl.classList.add('btn-status-purple');
            });
        }
        
        function playNotificationSound() {
            try {
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.type = 'sine';
                osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
                osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.15); // A5
                gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);
                osc.start();
                osc.stop(audioCtx.currentTime + 0.4);
            } catch (soundErr) {
                console.warn("Could not play notification sound:", soundErr);
            }
        }

        function fetchCompiledVideos() {
            if (!activeProjectId) return;
            fetch(`/get-project?id=${activeProjectId}`)
                .then(r => r.json())
                .then(data => {
                    compiledVideos = data.compiled_videos || [];
                    const oldStatuses = clipStatuses || {};
                    clipStatuses = data.clip_statuses || {};
                    renderClips();
                    
                    // Track state transitions to play sound when compilation completes
                    if (!window.previouslyProcessingClips) {
                        window.previouslyProcessingClips = {};
                    }
                    
                    Object.keys(clipStatuses).forEach(num => {
                        const state = clipStatuses[num].video_state;
                        const wasProcessing = window.previouslyProcessingClips[num];
                        if (state === 'processing') {
                            window.previouslyProcessingClips[num] = true;
                        } else if (wasProcessing && state !== 'processing') {
                            delete window.previouslyProcessingClips[num];
                            if (state === 'compiled' || state === 'draft') {
                                playNotificationSound();
                                showDebug(`Clip ${num} processing completed successfully!`, false);
                            } else {
                                showDebug(`Clip ${num} processing completed with state: ${state}`, true);
                            }
                        }
                    });
                    
                    // Auto-poll if any clip is in processing/compiling state
                    const hasProcessing = Object.values(clipStatuses).some(status => status.video_state === 'processing');
                    if (hasProcessing) {
                        if (window.fetchCompiledVideosTimeout) {
                            clearTimeout(window.fetchCompiledVideosTimeout);
                        }
                        window.fetchCompiledVideosTimeout = setTimeout(fetchCompiledVideos, 3000);
                    }
                })
                .catch(err => {
                    console.warn("Error refreshing compiled videos and statuses:", err);
                });
        }

        // Update Undo button state in UI
        function updateUndoButtonState() {
            if (undoStack.length > 0) {
                undoBtn.disabled = false;
                undoCountLabel.textContent = `(${undoStack.length}/10)`;
            } else {
                undoBtn.disabled = true;
                undoCountLabel.textContent = "";
            }
        }

        // Save plan.json
        function savePlanToServer(isUndoable = true) {
            if (!activeProjectId) return;
            
            const currentPlanStr = JSON.stringify(clips);
            if (currentPlanStr !== lastSavedStateString) {
                if (isUndoable) {
                    // Push deep copy of previous state onto undo stack
                    undoStack.push(JSON.parse(lastSavedStateString));
                    if (undoStack.length > 10) {
                        undoStack.shift();
                    }
                    updateUndoButtonState();
                }
                lastSavedStateString = currentPlanStr;
            }

            fetch(`/save-project-plan?id=${activeProjectId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(clips, null, 4)
            })
            .then(res => {
                if (!res.ok) console.error("Auto-save failed");
            })
            .catch(err => {
                console.warn("Auto-save failed: ", err.message);
            });
        }

        // Add New Clip card
        newClipBtn.addEventListener('click', () => {
            if (!activeProjectId) return;
            clips.push({
                num: clips.length + 1,
                title: `New Clip #${clips.length + 1}`,
                locked: false,
                segments: []
            });
            renderClips();
            savePlanToServer();
        });

        // Collapse All
        collapseAllBtn.addEventListener('click', () => {
            if (!activeProjectId) return;
            clips.forEach((_, idx) => {
                localStorage.setItem(`ddma-collapsed-${activeProjectId}-${idx}`, 'true');
            });
            renderClips();
        });

        // Expand All
        expandAllBtn.addEventListener('click', () => {
            if (!activeProjectId) return;
            clips.forEach((_, idx) => {
                localStorage.removeItem(`ddma-collapsed-${activeProjectId}-${idx}`);
            });
            renderClips();
        });

        // Toggle Show Hidden Clips
        toggleShowHiddenBtn.addEventListener('click', () => {
            showHiddenClips = !showHiddenClips;
            if (showHiddenClips) {
                toggleShowHiddenBtn.textContent = '👁️ Hide Hidden';
                toggleShowHiddenBtn.style.backgroundImage = 'linear-gradient(135deg, #a855f7 0%, #d946ef 100%)';
            } else {
                toggleShowHiddenBtn.textContent = '👁️ Show Hidden';
                toggleShowHiddenBtn.style.backgroundImage = '';
            }
            renderClips();
        });

        // Undo button listener
        undoBtn.addEventListener('click', () => {
            if (undoStack.length === 0) return;
            
            // Peek at the previous state first before popping it
            const prevState = undoStack[undoStack.length - 1];
            
            // Check if undo would change any currently locked clips
            for (let i = 0; i < clips.length; i++) {
                const currClip = clips[i];
                if (currClip.locked) {
                    const prevClip = prevState.find(c => c.num === currClip.num);
                    if (!prevClip) {
                        alert(`Cannot undo: Clip #${currClip.num} ("${currClip.title}") is currently locked. Please unlock it first.`);
                        return;
                    } else {
                        const currContent = JSON.stringify({ title: currClip.title, segments: currClip.segments });
                        const prevContent = JSON.stringify({ title: prevClip.title, segments: prevClip.segments });
                        if (currContent !== prevContent) {
                            alert(`Cannot undo: Clip #${currClip.num} ("${currClip.title}") is currently locked. Please unlock it first.`);
                            return;
                        }
                    }
                }
            }
            
            const prevStatePopped = undoStack.pop();
            clips = prevStatePopped;
            renderClips();
            updateUsedHighlights();
            savePlanToServer(false); // save changes without pushing to undo stack again
            updateUndoButtonState();
            updateStateBar("Undo successful");
        });

        // Take Snapshot button listener
        saveSnapshotBtn.addEventListener('click', () => {
            if (!activeProjectId) return;
            saveSnapshotBtn.disabled = true;
            saveSnapshotBtn.innerHTML = '⏳ Saving...';
            
            fetch(`/save-project-snapshot?id=${activeProjectId}`, { method: 'POST' })
                .then(r => {
                    if (!r.ok) throw new Error("Could not save snapshot");
                    return r.json();
                })
                .then(data => {
                    saveSnapshotBtn.disabled = false;
                    saveSnapshotBtn.innerHTML = '📸 Take Snapshot';
                    restoreSnapshotBtn.disabled = false;
                    updateStateBar("Snapshot saved successfully!");
                    showDebug("Snapshot saved in projects/" + activeProjectId + "/plan_snapshot.json", false);
                })
                .catch(err => {
                    saveSnapshotBtn.disabled = false;
                    saveSnapshotBtn.innerHTML = '📸 Take Snapshot';
                    updateStateBar("Snapshot failed");
                    showDebug("Snapshot failed: " + err.message);
                });
        });

        // Restore Snapshot button listener
        restoreSnapshotBtn.addEventListener('click', () => {
            if (!activeProjectId) return;
            if (!confirm("Are you sure you want to restore the snapshot? This will overwrite your current active plan. (You will still be able to Undo this restore).")) return;
            
            restoreSnapshotBtn.disabled = true;
            restoreSnapshotBtn.innerHTML = '⏳ Restoring...';
            
            // Push current state to undo stack before overwriting
            undoStack.push(JSON.parse(JSON.stringify(clips)));
            if (undoStack.length > 10) {
                undoStack.shift();
            }
            updateUndoButtonState();
            
            fetch(`/restore-project-snapshot?id=${activeProjectId}`, { method: 'POST' })
                .then(r => {
                    if (!r.ok) throw new Error("Could not restore snapshot");
                    return r.json();
                })
                .then(data => {
                    restoreSnapshotBtn.disabled = false;
                    restoreSnapshotBtn.innerHTML = '⏪ Restore Snapshot';
                    
                    clips = data.plan || [];
                    lastSavedStateString = JSON.stringify(clips);
                    renderClips();
                    updateUsedHighlights();
                    
                    updateStateBar("Snapshot restored!");
                    showDebug("Restored from plan_snapshot.json", false);
                })
                .catch(err => {
                    restoreSnapshotBtn.disabled = false;
                    restoreSnapshotBtn.innerHTML = '⏪ Restore Snapshot';
                    updateStateBar("Restore snapshot failed");
                    showDebug("Restore snapshot failed: " + err.message);
                });
        });

        // Render planned clips list
        function renderClips() {
            const savedScrollTop = clipListContainer.scrollTop;
            if (!activeProjectId) {
                planEmptyState.style.display = 'flex';
                planEmptyState.innerHTML = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    <p>Select or create a project on the left, then click "New Clip" to build segments.</p>
                `;
                const cards = clipListContainer.querySelectorAll('.clip-card');
                cards.forEach(c => c.remove());
                return;
            }
            
            if (clips.length === 0) {
                planEmptyState.style.display = 'flex';
                planEmptyState.innerHTML = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    <p>No clips planned yet. Click "New Clip" at the top to create a card.</p>
                `;
                const cards = clipListContainer.querySelectorAll('.clip-card');
                cards.forEach(c => c.remove());
                return;
            }

            planEmptyState.style.display = 'none';
            const cards = clipListContainer.querySelectorAll('.clip-card');
            cards.forEach(c => c.remove());

            const episodeNum = (projectInfo && projectInfo.name) ? (projectInfo.name.match(/\d+/)?.[0] || projectInfo.name) : "244";

            clips.forEach((clip, index) => {
                clip.num = index + 1;
                
                if (clip.hidden && !showHiddenClips) {
                    return;
                }
                
                const card = document.createElement('div');
                card.dataset.index = index;
                
                if (clip.hidden) {
                    card.className = `clip-card hidden-state collapsed`;
                    card.style.opacity = '0.5';
                    card.style.border = '1px dashed var(--border-color)';
                    card.innerHTML = `
                        <div class="clip-card-header" style="padding: 0.5rem 0.8rem;">
                            <div class="clip-card-title-container" style="display: flex; align-items: center; gap: 0.5rem; flex-grow: 1;">
                                <span class="clip-num-badge" style="background-color: var(--text-muted); color: white; padding: 0.15rem 0.35rem; border-radius: 4px; font-weight: bold; font-size: 0.75rem; font-family: var(--font-mono); white-space: nowrap;">${episodeNum}-${clip.num}</span>
                                <span style="font-size: 0.8rem; font-weight: bold; color: var(--text-muted); font-style: italic;">(Hidden) ${clip.title || 'Untitled Clip'}</span>
                            </div>
                            <div class="clip-card-actions" style="display: flex; gap: 0.4rem; align-items: center;" onclick="event.stopPropagation();">
                                <button class="btn btn-secondary btn-mini restore-clip" data-index="${index}" style="font-weight:600; padding: 0.2rem 0.4rem; font-size: 0.7rem;" title="Restore clip to active plan">👁️ Unhide</button>
                                <button class="icon-btn icon-btn-danger remove-clip" data-index="${index}" style="font-size: 0.75rem; padding: 0.15rem 0.35rem;" title="Permanently delete this clip from project plan">🗑️</button>
                            </div>
                        </div>
                    `;
                    clipListContainer.appendChild(card);
                    
                    card.querySelector('.restore-clip').addEventListener('click', function(e) {
                        e.stopPropagation();
                        clip.hidden = false;
                        renderClips();
                        savePlanToServer();
                    });
                    
                    card.querySelector('.remove-clip').addEventListener('click', function(e) {
                        e.stopPropagation();
                        const confirmDelete = confirm(`Are you sure you want to permanently delete Clip ${clip.num}?\n\nThis action cannot be undone.`);
                        if (!confirmDelete) return;
                        clips.splice(index, 1);
                        renderClips();
                        savePlanToServer();
                    });
                    return;
                }
                
                const isLocked = clip.locked || false;
                
                const isCollapsed = localStorage.getItem(`ddma-collapsed-${activeProjectId}-${index}`) === 'true';
                const caretText = isCollapsed ? '▶' : '▼';
                
                card.className = `clip-card ${isLocked ? 'locked' : ''} ${isCollapsed ? 'collapsed' : ''}`;
                card.draggable = !isLocked;
                
                const totalDuration = calculateClipDuration(clip);
                
                // Prepend Intro Card HTML
                const introSubtext = (clip.num === 1) ? `EPISODE ${episodeNum}` : `EPISODE ${episodeNum} • PART ${clip.num}`;
                const introTitleText = (clip.num === 1) ? ((projectInfo && projectInfo.title) ? projectInfo.title : "Life, Death and the Lysosome") : (clip.title ? clip.title : `Part ${clip.num}`);
                let introCardHtml = `
                    <div class="segment-row segment-row-intro" style="border-left: 3px solid #06b6d4; padding: 0.4rem 0.6rem; margin-bottom: 0.4rem; background: rgba(6, 182, 212, 0.02); border-radius: 4px; border-top: 1px solid rgba(6, 182, 212, 0.1); border-bottom: 1px solid rgba(6, 182, 212, 0.1); border-right: 1px solid rgba(6, 182, 212, 0.1);">
                        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                            <span style="font-size: 0.75rem; font-weight: 700; color: #06b6d4; display: flex; align-items: center; gap: 0.25rem;">🎬 Intro Clip (Title Card)</span>
                            <span style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">Duration: 2.0s</span>
                        </div>
                        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem; display: flex; flex-direction: column; gap: 0.1rem;">
                            <div><strong style="color: var(--text-main);">Layout Text:</strong> ${introSubtext}</div>
                            <div><strong style="color: var(--text-main);">Title Text:</strong> "${introTitleText}"</div>
                        </div>
                    </div>
                `;

                let segmentsHtml = introCardHtml;
                if (clip.segments.length === 0) {
                    segmentsHtml = `<div style="font-size: 0.8rem; color: var(--text-muted); font-style: italic; padding: 0.4rem 0;">No segments added yet. Select text on right and click "+ Add Audio" below.</div>`;
                } else {
                    clip.segments.forEach((seg, segIdx) => {
                        const isEditing = editingSegmentRef && editingSegmentRef.clipIdx === index && editingSegmentRef.segIdx === segIdx;
                        const rowStyle = isEditing ? 'border: 1px solid var(--primary); background-color: rgba(99, 102, 241, 0.08);' : '';
                        
                        let segmentActionsHtml = "";
                        if (!isLocked) {
                            const isFirst = segIdx === 0;
                            const isLast = segIdx === clip.segments.length - 1;
                            segmentActionsHtml = `
                                <div class="segment-actions-group" style="display: flex; gap: 0.2rem; align-items: center; justify-content: flex-end;" onclick="event.stopPropagation();">
                                    <button class="icon-btn move-seg-up" data-clip="${index}" data-seg="${segIdx}" title="Move Up" ${isFirst ? 'style="display:none;"' : ''}>🔼</button>
                                    <button class="icon-btn move-seg-down" data-clip="${index}" data-seg="${segIdx}" title="Move Down" ${isLast ? 'style="display:none;"' : ''}>🔽</button>
                                    <button class="icon-btn copy-seg-btn" data-clip="${index}" data-seg="${segIdx}" title="Copy Segment">📋</button>
                                    <button class="icon-btn remove-seg" data-clip="${index}" data-seg="${segIdx}" title="Remove Segment">✖</button>
                                </div>
                            `;
                        } else {
                            segmentActionsHtml = `
                                <div class="segment-actions-group" style="display: flex; gap: 0.2rem; align-items: center; justify-content: flex-end;" onclick="event.stopPropagation();">
                                    <button class="icon-btn copy-seg-btn" data-clip="${index}" data-seg="${segIdx}" title="Copy Segment">📋</button>
                                </div>
                            `;
                        }
                        
                        if (seg.type === "audio") {
                            let audioEditorHtml = "";
                            if (!isLocked) {
                                audioEditorHtml = `
                                    <div class="music-editor-row" style="margin-top: 0.2rem;" onclick="event.stopPropagation();">
                                        <div class="music-editor-field">
                                            <label>Duration (s):</label>
                                            <input type="number" class="audio-duration" step="any" min="0" style="width: 55px;" value="${seg.duration.toFixed(2)}" data-clip="${index}" data-seg="${segIdx}">
                                        </div>
                                        <div class="music-editor-field">
                                            <label>Volume:</label>
                                            <input type="number" class="audio-volume" step="any" min="0" max="2" style="width: 55px;" value="${seg.volume !== undefined ? seg.volume : 1.00}" data-clip="${index}" data-seg="${segIdx}">
                                        </div>
                                        <div class="music-editor-field">
                                            <label>Crossfade (s):</label>
                                            <input type="number" class="audio-crossfade" step="any" min="0" style="width: 55px;" value="${seg.crossfade !== undefined ? seg.crossfade : 0.0}" data-clip="${index}" data-seg="${segIdx}">
                                        </div>
                                    </div>
                                `;
                            }
                            segmentsHtml += `
                                <div class="segment-row audio-seg" data-clip="${index}" data-seg="${segIdx}" style="${rowStyle}">
                                    <div class="segment-info">
                                        <span class="segment-meta audio-meta">🎙 Audio Segment (${seg.duration.toFixed(2)}s)</span>
                                        <span class="segment-text">"${seg.text}"</span>
                                        ${audioEditorHtml}
                                    </div>
                                    ${segmentActionsHtml}
                                </div>
                            `;
                        } else if (seg.type === "music") {
                            let musicOptionsHtml = `<option value="none">Digital Silence</option>`;
                            availableMusicFiles.forEach(f => {
                                const isSelected = seg.music_file === f ? 'selected' : '';
                                musicOptionsHtml += `<option value="${f}" ${isSelected}>${f}</option>`;
                            });
                            
                            segmentsHtml += `
                                <div class="segment-row" data-clip="${index}" data-seg="${segIdx}">
                                    <div class="segment-info">
                                        <span class="segment-meta music-meta">🎵 Music Segment (${seg.duration}s)</span>
                                        <div class="music-editor-row" onclick="event.stopPropagation();">
                                            <div class="music-editor-field">
                                                <label>Sting:</label>
                                                <select class="music-select" data-clip="${index}" data-seg="${segIdx}" ${isLocked ? 'disabled' : ''}>
                                                    ${musicOptionsHtml}
                                                </select>
                                            </div>
                                            <div class="music-editor-field">
                                                <label>Duration (s):</label>
                                                <input type="number" class="music-duration" step="any" min="0" style="width: 55px;" value="${seg.duration}" data-clip="${index}" data-seg="${segIdx}" ${isLocked ? 'disabled' : ''}>
                                            </div>
                                            <div class="music-editor-field">
                                                <label>Volume:</label>
                                                <input type="number" class="music-volume" step="any" min="0" max="2" style="width: 55px;" value="${seg.volume !== undefined ? seg.volume : 1.00}" data-clip="${index}" data-seg="${segIdx}" ${isLocked ? 'disabled' : ''}>
                                            </div>
                                            <div class="music-editor-field">
                                                <label>Crossfade (s):</label>
                                                <input type="number" class="music-crossfade" step="any" min="0" style="width: 55px;" value="${seg.crossfade !== undefined ? seg.crossfade : 0.0}" data-clip="${index}" data-seg="${segIdx}" ${isLocked ? 'disabled' : ''}>
                                            </div>
                                        </div>
                                    </div>
                                    ${segmentActionsHtml}
                                </div>
                            `;
                        }
                    });
                }

                // Append Outro Card HTML
                const isLastClip = (index === clips.length - 1);
                let outroCardHtml = "";
                if (isLastClip) {
                    outroCardHtml = `
                        <div class="segment-row segment-row-outro" style="display: flex; flex-direction: column; align-items: stretch; border-left: 3px solid #6b7280; padding: 0.4rem 0.6rem; margin-top: 0.4rem; background: rgba(107, 114, 128, 0.02); border-radius: 4px; border-top: 1px solid rgba(107, 114, 128, 0.1); border-bottom: 1px solid rgba(107, 114, 128, 0.1); border-right: 1px solid rgba(107, 114, 128, 0.1); opacity: 0.6; gap: 0.2rem; cursor: default;">
                            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                                <span style="font-size: 0.75rem; font-weight: 700; color: #6b7280; display: flex; align-items: center; gap: 0.25rem;">🎬 Outro Clip (No Bridge)</span>
                                <span style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">Last Clip</span>
                            </div>
                            <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem; font-style: italic;">
                                No outro transition card needed for the last clip.
                            </div>
                        </div>
                    `;
                } else {
                    const bridgeTextVal = clip.bridge_text ? (Array.isArray(clip.bridge_text) ? clip.bridge_text.join(" ") : clip.bridge_text) : "";
                    outroCardHtml = `
                        <div class="segment-row segment-row-outro" style="display: flex; flex-direction: column; align-items: stretch; border-left: 3px solid #10b981; padding: 0.4rem 0.6rem; margin-top: 0.4rem; background: rgba(16, 185, 129, 0.02); border-radius: 4px; border-top: 1px solid rgba(16, 185, 129, 0.1); border-bottom: 1px solid rgba(16, 185, 129, 0.1); border-right: 1px solid rgba(16, 185, 129, 0.1); gap: 0.4rem; cursor: default;">
                            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                                <span style="font-size: 0.75rem; font-weight: 700; color: #10b981; display: flex; align-items: center; gap: 0.25rem;">🎬 Outro Clip (Bridge Card)</span>
                                <span style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">Duration: 5.0s</span>
                            </div>
                            <div style="margin-top: 0.1rem; width: 100%;" onclick="event.stopPropagation();">
                                <label style="font-size: 0.7rem; color: var(--text-muted); display: block; margin-bottom: 0.15rem; font-weight: 600;">Curiosity Question (editable):</label>
                                <input type="text" class="outro-bridge-text-input" style="width: 100%; font-size: 0.75rem; background-color: var(--bg-color); border: 1px solid var(--border-color); color: var(--text-main); padding: 0.25rem 0.4rem; border-radius: 4px; outline: none; box-sizing: border-box;" placeholder="Enter curiosity-provoking question for the next clip..." value="${bridgeTextVal.replace(/"/g, '&quot;')}" data-index="${index}" ${isLocked ? 'disabled' : ''}>
                            </div>
                        </div>
                    `;
                }
                segmentsHtml += outroCardHtml;
                
                const lockBtnIcon = isLocked ? '🔒 Locked' : '🔓 Unlocked';
                const deleteCardBtnHtml = isLocked ? '' : `<button class="icon-btn icon-btn-danger remove-clip" data-index="${index}">🗑</button>`;
                const adderControlsHtml = isLocked ? '' : `
                    <div class="segment-adder-btns">
                        <button class="btn btn-secondary btn-mini add-audio-btn" data-index="${index}">➕ Add Audio</button>
                        <button class="btn btn-secondary btn-mini add-music-btn" data-index="${index}">🎵 Add Music</button>
                        <button class="btn btn-secondary btn-mini paste-seg-btn" data-index="${index}" ${segmentClipboard ? '' : 'disabled style="opacity: 0.5; cursor: not-allowed;"'}>📋 Paste Segment</button>
                    </div>
                `;
                
                // Resolve Status Classes for buttons
                const statusInfo = clipStatuses[clip.num] || { has_audio: false, video_state: "none" };
                const matchingVideo = compiledVideos.find(v => v.num === clip.num);
                
                // 1. Intro status: green if title is customized, yellow if default/empty
                const isIntroCustom = clip.title && clip.title.trim() !== "" && !clip.title.match(/^New Clip #\d+$/i);
                const introStatusClass = isIntroCustom ? "btn-status-success" : "btn-status-warning";
                
                // 2. Outro status: gray/disabled if last clip, green if has question, yellow if empty question
                let outroStatusClass = "btn-status-warning";
                let outroBtnDisabled = "";
                if (isLastClip) {
                    outroStatusClass = "btn-status-gray";
                    outroBtnDisabled = "disabled style='opacity: 0.5; cursor: not-allowed;'";
                } else {
                    const hasOutroQuestion = clip.bridge_text && (Array.isArray(clip.bridge_text) ? clip.bridge_text.length > 0 && clip.bridge_text[0].trim() !== "" : clip.bridge_text.trim() !== "");
                    outroStatusClass = hasOutroQuestion ? "btn-status-success" : "btn-status-warning";
                }
                
                // 3. Audio status: green if audio exists on disk, gray/default if not
                const audioStatusClass = statusInfo.has_audio ? "btn-status-success" : "btn-status-gray";
                
                // 4. Video status: green if compiled with intro, yellow if draft raw Mosaic, gray if no video
                let videoStatusClass = "btn-status-gray";
                if (statusInfo.video_state === 'compiled') {
                    videoStatusClass = "btn-status-success";
                } else if (statusInfo.video_state === 'draft') {
                    videoStatusClass = "btn-status-warning";
                }
                
                // 5. Mosaic status: green if Mosaic exists, purple if not
                const mosaicStatusClass = statusInfo.video_state === 'compiled' ? "btn-status-success" : "btn-status-purple";
                
                let videoBtnHtml = "";
                if (statusInfo.video_state === 'processing') {
                    videoBtnHtml = `<button class="btn btn-mini btn-card-video btn-status-gray" style="font-weight:600; opacity: 0.5; cursor: not-allowed;" disabled title="Video is currently compiling/processing...">⏳ Processing</button>`;
                } else if (statusInfo.video_state !== 'none') {
                    videoBtnHtml = `<button class="btn btn-mini btn-card-video ${videoStatusClass}" id="playVideoBtn_${index}" style="font-weight:600;" title="Play compiled MP4 video">📹 Video</button>`;
                } else {
                    videoBtnHtml = `<button class="btn btn-mini btn-card-video ${videoStatusClass}" style="font-weight:600; opacity: 0.4; cursor: not-allowed;" disabled title="Video not generated yet">📹 Video</button>`;
                }
                
                let mosaicBtnHtml = "";
                if (isLocked) {
                    if (statusInfo.video_state === 'processing') {
                        const pct = statusInfo.progress !== undefined ? statusInfo.progress : 0;
                        mosaicBtnHtml = `<button class="btn btn-mini btn-card-mosaic btn-status-warning" id="mosaicCardBtn_${index}" style="font-weight: 600; opacity: 0.8; cursor: not-allowed;" disabled title="Mosaic generation in progress...">⏳ ${pct}%</button>`;
                    } else {
                        mosaicBtnHtml = `<button class="btn btn-mini btn-card-mosaic ${mosaicStatusClass}" id="mosaicCardBtn_${index}" style="font-weight: 600;" title="Send draft video to Mosaic API for overlaying infographics and visual graphics">🌌 Mosaic</button>`;
                    }
                } else {
                    mosaicBtnHtml = `<button class="btn btn-mini btn-card-mosaic btn-status-gray" style="font-weight: 600; opacity: 0.4; cursor: not-allowed;" disabled title="Lock clip first to enable Mosaic">🌌 Mosaic</button>`;
                }
                
                card.innerHTML = `
                    <div class="clip-card-header">
                        <div class="clip-card-title-container">
                            <div style="display: flex; align-items: center; width: 100%; gap: 0.4rem;">
                                <span class="clip-collapse-caret" style="cursor: pointer; font-size: 0.85rem; user-select: none; margin-right: 0.2rem; font-family: var(--font-mono); color: var(--text-muted);" data-index="${index}">${caretText}</span>
                                <span class="clip-num-badge" style="background-color: var(--primary); color: white; padding: 0.15rem 0.35rem; border-radius: 4px; font-weight: bold; font-size: 0.75rem; font-family: var(--font-mono); white-space: nowrap;">${episodeNum}-${clip.num}</span>
                                <input type="text" class="clip-card-title" placeholder="Enter title description..." value="${clip.title}" data-index="${index}" ${isLocked ? 'disabled' : ''}>
                            </div>
                            
                            <!-- Clip Level Settings (Duration, Volume, Crossfade) -->
                            <div class="music-editor-row" style="margin-top: 0.4rem; padding: 0.3rem 0.5rem; background: rgba(255,255,255,0.02); border-radius: 4px; display: inline-flex; align-self: flex-start;" onclick="event.stopPropagation();">
                                <div class="music-editor-field">
                                    <label style="font-size: 0.7rem; color: var(--text-muted);">Duration (s):</label>
                                    <input type="text" class="clip-dur-input" style="width: 55px; background: transparent; border: none; color: var(--text-muted); font-size: 0.75rem; font-family: var(--font-mono); padding: 0;" value="${formatTime(totalDuration)}" disabled>
                                </div>
                                <div class="music-editor-field">
                                    <label style="font-size: 0.7rem;">Volume:</label>
                                    <input type="number" class="clip-volume" step="any" min="0" max="2" style="width: 55px;" value="${clip.volume !== undefined ? clip.volume : 1.00}" data-index="${index}">
                                </div>
                                <div class="music-editor-field">
                                    <label style="font-size: 0.7rem;">Crossfade (s):</label>
                                    <input type="number" class="clip-crossfade" step="any" min="0" style="width: 55px;" value="${clip.crossfade !== undefined ? clip.crossfade : 0.0}" data-index="${index}">
                                </div>
                                <div class="music-editor-field" style="display: flex; align-items: center; gap: 0.25rem; margin-left: 0.4rem;">
                                    <input type="checkbox" class="clip-audio-only-checkbox" id="clipAudioOnly_${index}" data-index="${index}" ${clip.audio_only ? 'checked' : ''} ${isLocked ? 'disabled' : ''} style="cursor: pointer; margin-top: 2px;">
                                    <label for="clipAudioOnly_${index}" style="font-size: 0.7rem; cursor: pointer; user-select: none; font-weight: 600; color: var(--text-muted); white-space: nowrap;">Audio Only</label>
                                </div>
                            </div>
                        </div>

                        <div class="clip-card-actions">
                            <button class="btn btn-secondary btn-mini btn-card-intro ${introStatusClass}" id="introCardBtn_${index}" style="font-weight:600;" title="Preview Intro Clip (Title Card + Music)">🎬 Intro</button>
                            <button class="btn btn-secondary btn-mini btn-card-outro ${outroStatusClass}" id="outroCardBtn_${index}" style="font-weight:600;" ${outroBtnDisabled} title="Preview Outro Clip (Bridge Card Question + Fadeout)">🎬 Outro</button>
                            <button class="btn-card-play ${audioStatusClass}" id="playCardBtn_${index}">▶ Audio</button>
                            ${videoBtnHtml}
                            
                            <div class="actions-separator"></div>
                            
                            ${mosaicBtnHtml}
                            <button class="btn btn-mini btn-card-remix btn-status-purple" id="remixCardBtn_${index}" style="font-weight:600;" ${isLocked ? 'disabled style="opacity: 0.4; cursor: not-allowed;"' : ''} title="Recast this clip using Creative AI based on preceding locked clips">🔄 Remix</button>
                            <button class="btn btn-secondary btn-mini lock-clip" id="lockCardBtn_${index}" style="font-weight:600;">${lockBtnIcon}</button>
                            ${deleteCardBtnHtml}
                        </div>
                    </div>
                    
                    <div class="segments-container">
                        ${segmentsHtml}
                    </div>
                    
                    <div class="card-controls">
                        ${adderControlsHtml}
                        <span style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono); margin-left: auto;">ID: ${episodeNum}-${clip.num}</span>
                    </div>
                `;

                card.querySelector('.clip-card-title').addEventListener('change', function(e) {
                    clips[index].title = e.target.value.trim();
                    savePlanToServer();
                });

                card.querySelector('.clip-collapse-caret').addEventListener('click', function(e) {
                    e.stopPropagation();
                    const idx = parseInt(this.dataset.index);
                    const isCollapsedNow = card.classList.toggle('collapsed');
                    if (isCollapsedNow) {
                        this.textContent = '▶';
                        localStorage.setItem(`ddma-collapsed-${activeProjectId}-${idx}`, 'true');
                    } else {
                        this.textContent = '▼';
                        localStorage.removeItem(`ddma-collapsed-${activeProjectId}-${idx}`);
                    }
                });

                card.querySelector('.clip-volume').addEventListener('change', function(e) {
                    const val = parseFloat(e.target.value);
                    clips[index].volume = isNaN(val) ? 1.00 : val;
                    savePlanToServer();
                });

                card.querySelector('.clip-crossfade').addEventListener('change', function(e) {
                    const val = parseFloat(e.target.value);
                    clips[index].crossfade = isNaN(val) ? 0.0 : val;
                    savePlanToServer();
                });

                const audioOnlyCheck = card.querySelector('.clip-audio-only-checkbox');
                if (audioOnlyCheck) {
                    audioOnlyCheck.addEventListener('change', function(e) {
                        clips[index].audio_only = this.checked;
                        savePlanToServer();
                    });
                }

                card.querySelector(`#lockCardBtn_${index}`).addEventListener('click', function(e) {
                    toggleClipLock(index, e);
                });

                card.querySelector(`#playCardBtn_${index}`).addEventListener('click', function(e) {
                    playFFmpegPreview(index, this, e);
                });

                card.querySelector(`#introCardBtn_${index}`).addEventListener('click', function(e) {
                    e.stopPropagation();
                    const btn = this;
                    btn.innerHTML = '⏳ Rendering...';
                    btn.disabled = true;
                    updateStateBar("Rendering 2-second intro title card clip...");
                    
                    fetch(`/get-clip-intro?id=${activeProjectId}&num=${clip.num}`, {
                        method: 'POST'
                    })
                    .then(res => {
                        if (!res.ok) return res.json().then(data => { throw new Error(data.error || "Server error"); });
                        return res.json();
                    })
                    .then(data => {
                        audioElement.pause();
                        playBtn.textContent = '▶';
                        
                        previewVideoPlayer.src = data.preview_url;
                        videoModalTitle.textContent = `INTRO PREVIEW - Part ${clip.num}: ${clip.title}`;
                        videoModalSubtitle.textContent = `previews/intro_${activeProjectId}_${clip.num}.mp4`;
                        downloadVideoBtn.href = data.preview_url;
                        videoModalOverlay.classList.add('active');
                        previewVideoPlayer.play();
                        
                        updateStateBar("Playing intro card preview");
                    })
                    .catch(err => {
                        alert("Error rendering intro: " + err.message);
                        updateStateBar("Ready");
                    })
                    .finally(() => {
                        btn.innerHTML = '🎬 Intro';
                        btn.disabled = false;
                    });
                });

                card.querySelector(`#outroCardBtn_${index}`).addEventListener('click', function(e) {
                    e.stopPropagation();
                    const btn = this;
                    btn.innerHTML = '⏳ Rendering...';
                    btn.disabled = true;
                    updateStateBar("Rendering 5-second outro bridge card clip...");
                    
                    fetch(`/get-clip-outro?id=${activeProjectId}&num=${clip.num}`, {
                        method: 'POST'
                    })
                    .then(res => {
                        if (!res.ok) return res.json().then(data => { throw new Error(data.error || "Server error"); });
                        return res.json();
                    })
                    .then(data => {
                        audioElement.pause();
                        playBtn.textContent = '▶';
                        
                        previewVideoPlayer.src = data.preview_url;
                        videoModalTitle.textContent = `OUTRO PREVIEW (Bridge Card) - Part ${clip.num}`;
                        videoModalSubtitle.textContent = `previews/outro_${activeProjectId}_${clip.num}.mp4`;
                        downloadVideoBtn.href = data.preview_url;
                        videoModalOverlay.classList.add('active');
                        previewVideoPlayer.play();
                        
                        updateStateBar("Playing outro bridge preview");
                    })
                    .catch(err => {
                        alert("Error rendering outro: " + err.message);
                        updateStateBar("Ready");
                    })
                    .finally(() => {
                        btn.innerHTML = '🎬 Outro';
                        btn.disabled = false;
                    });
                });

                card.querySelector('.outro-bridge-text-input')?.addEventListener('change', function(e) {
                    const idx = parseInt(e.target.dataset.index);
                    const val = e.target.value.trim();
                    clips[idx].bridge_text = val ? [val] : [];
                    savePlanToServer();
                });

                if (matchingVideo && statusInfo.video_state !== 'processing') {
                    card.querySelector(`#playVideoBtn_${index}`).addEventListener('click', function(e) {
                        e.stopPropagation();
                        // Pause the audio player
                        audioElement.pause();
                        playBtn.textContent = '▶';
                        
                        // Setup and show video modal
                        previewVideoPlayer.src = matchingVideo.url;
                        videoModalTitle.textContent = `VIDEO PREVIEW - Part ${clip.num}: ${clip.title}`;
                        videoModalSubtitle.textContent = `clips/${matchingVideo.filename}`;
                        downloadVideoBtn.href = matchingVideo.url;
                        videoModalOverlay.classList.add('active');
                        previewVideoPlayer.play();
                    });
                }
                
                if (isLocked) {
                    card.querySelector(`#mosaicCardBtn_${index}`).addEventListener('click', function(e) {
                        e.stopPropagation();
                        exportToMosaic(index, this);
                    });
                }
                
                if (!isLocked) {
                    card.querySelector(`#remixCardBtn_${index}`).addEventListener('click', function(e) {
                        e.stopPropagation();
                        remixClip(index, this);
                    });
                }

                if (!isLocked) {
                    card.querySelector('.add-audio-btn').addEventListener('click', function(e) {
                        e.stopPropagation();
                        addAudioSegmentToClip(index);
                    });

                    card.querySelector('.add-music-btn').addEventListener('click', function(e) {
                        e.stopPropagation();
                        addMusicSegmentToClip(index);
                    });

                    card.querySelector('.paste-seg-btn').addEventListener('click', function(e) {
                        e.stopPropagation();
                        pasteSegment(index);
                    });
                }

                card.querySelectorAll('.segment-row.audio-seg').forEach(el => {
                    el.addEventListener('click', function(e) {
                        if (e.target.tagName === 'BUTTON') return;
                        const clipIdx = parseInt(this.dataset.clip);
                        const segIdx = parseInt(this.dataset.seg);
                        selectSegmentForEditing(clipIdx, segIdx);
                    });
                });

                if (!isLocked) {
                    card.querySelectorAll('.music-select').forEach(el => {
                        el.addEventListener('change', function() {
                            const clipIdx = parseInt(this.dataset.clip);
                            const segIdx = parseInt(this.dataset.seg);
                            updateSegmentField(clipIdx, segIdx, 'music_file', this.value);
                        });
                    });

                    card.querySelectorAll('.music-duration').forEach(el => {
                        el.addEventListener('input', function() {
                            const clipIdx = parseInt(this.dataset.clip);
                            const segIdx = parseInt(this.dataset.seg);
                            const newDur = parseFloat(this.value) || 0.0;
                            clips[clipIdx].segments[segIdx].duration = newDur;
                            
                            const segmentRow = this.closest('.segment-row');
                            if (segmentRow) {
                                const metaEl = segmentRow.querySelector('.music-meta');
                                if (metaEl) {
                                    metaEl.textContent = `🎵 Music Segment (${newDur}s)`;
                                }
                            }
                            const totalDuration = calculateClipDuration(clips[clipIdx]);
                            const clipDurInput = card.querySelector('.clip-dur-input');
                            if (clipDurInput) {
                                clipDurInput.value = totalDuration.toFixed(2);
                            }
                            savePlanToServer();
                        });
                        el.addEventListener('change', function() {
                            renderClips();
                        });
                    });

                    card.querySelectorAll('.music-volume').forEach(el => {
                        el.addEventListener('change', function() {
                            const clipIdx = parseInt(this.dataset.clip);
                            const segIdx = parseInt(this.dataset.seg);
                            updateSegmentField(clipIdx, segIdx, 'volume', parseFloat(this.value) || 1.00);
                            renderClips();
                        });
                    });

                    card.querySelectorAll('.music-crossfade').forEach(el => {
                        el.addEventListener('input', function() {
                            const clipIdx = parseInt(this.dataset.clip);
                            const segIdx = parseInt(this.dataset.seg);
                            const newCf = parseFloat(this.value) || 0.0;
                            clips[clipIdx].segments[segIdx].crossfade = newCf;
                            
                            const totalDuration = calculateClipDuration(clips[clipIdx]);
                            const clipDurInput = card.querySelector('.clip-dur-input');
                            if (clipDurInput) {
                                clipDurInput.value = totalDuration.toFixed(2);
                            }
                            savePlanToServer();
                        });
                        el.addEventListener('change', function() {
                            renderClips();
                        });
                    });

                    card.querySelectorAll('.audio-duration').forEach(el => {
                        el.addEventListener('input', function() {
                            const clipIdx = parseInt(this.dataset.clip);
                            const segIdx = parseInt(this.dataset.seg);
                            const newDur = parseFloat(this.value) || 0.0;
                            const seg = clips[clipIdx].segments[segIdx];
                            seg.duration = newDur;
                            seg.end = parseFloat((seg.start + newDur).toFixed(2));
                            
                            const segmentRow = this.closest('.segment-row');
                            if (segmentRow) {
                                const metaEl = segmentRow.querySelector('.audio-meta');
                                if (metaEl) {
                                    metaEl.textContent = `🎙 Audio Segment (${newDur.toFixed(2)}s)`;
                                }
                            }
                            const totalDuration = calculateClipDuration(clips[clipIdx]);
                            const clipDurInput = card.querySelector('.clip-dur-input');
                            if (clipDurInput) {
                                clipDurInput.value = totalDuration.toFixed(2);
                            }
                            savePlanToServer();
                        });
                        el.addEventListener('change', function() {
                            renderClips();
                        });
                    });

                    card.querySelectorAll('.audio-volume').forEach(el => {
                        el.addEventListener('change', function() {
                            const clipIdx = parseInt(this.dataset.clip);
                            const segIdx = parseInt(this.dataset.seg);
                            updateSegmentField(clipIdx, segIdx, 'volume', parseFloat(this.value) || 1.00);
                            renderClips();
                        });
                    });

                    card.querySelectorAll('.audio-crossfade').forEach(el => {
                        el.addEventListener('input', function() {
                            const clipIdx = parseInt(this.dataset.clip);
                            const segIdx = parseInt(this.dataset.seg);
                            const newCf = parseFloat(this.value) || 0.0;
                            clips[clipIdx].segments[segIdx].crossfade = newCf;
                            
                            const totalDuration = calculateClipDuration(clips[clipIdx]);
                            const clipDurInput = card.querySelector('.clip-dur-input');
                            if (clipDurInput) {
                                clipDurInput.value = totalDuration.toFixed(2);
                            }
                            savePlanToServer();
                        });
                        el.addEventListener('change', function() {
                            renderClips();
                        });
                    });

                    card.querySelectorAll('.move-seg-up').forEach(el => {
                        el.addEventListener('click', function(e) {
                            e.stopPropagation();
                            const clipIdx = parseInt(this.dataset.clip);
                            const segIdx = parseInt(this.dataset.seg);
                            moveSegmentUp(clipIdx, segIdx);
                        });
                    });

                    card.querySelectorAll('.move-seg-down').forEach(el => {
                        el.addEventListener('click', function(e) {
                            e.stopPropagation();
                            const clipIdx = parseInt(this.dataset.clip);
                            const segIdx = parseInt(this.dataset.seg);
                            moveSegmentDown(clipIdx, segIdx);
                        });
                    });

                    card.querySelectorAll('.remove-seg').forEach(el => {
                        el.addEventListener('click', function(e) {
                            e.stopPropagation();
                            const clipIdx = parseInt(this.dataset.clip);
                            const segIdx = parseInt(this.dataset.seg);
                            removeSegment(clipIdx, segIdx);
                        });
                    });

                    card.querySelector('.remove-clip').addEventListener('click', function(e) {
                        e.stopPropagation();
                        const confirmHide = confirm(`Are you sure you want to hide Clip ${clip.num}?\n\nThis will remove it from view but preserve its segments. You can toggle hidden clips anytime using the 'Show Hidden' button at the top.`);
                        if (!confirmHide) return;
                        clip.hidden = true;
                        clip.locked = false; // unlock it just in case
                        renderClips();
                        savePlanToServer();
                    });
                }

                card.querySelectorAll('.copy-seg-btn').forEach(el => {
                    el.addEventListener('click', function(e) {
                        e.stopPropagation();
                        const clipIdx = parseInt(this.dataset.clip);
                        const segIdx = parseInt(this.dataset.seg);
                        copySegment(clipIdx, segIdx);
                    });
                });

                if (!isLocked) {
                    card.addEventListener('dragstart', function(e) {
                        dragSrcCardIdx = index;
                        e.dataTransfer.effectAllowed = 'move';
                    });

                    card.addEventListener('dragover', function(e) {
                        e.preventDefault();
                    });

                    card.addEventListener('drop', function(e) {
                        e.preventDefault();
                        if (dragSrcCardIdx !== null && dragSrcCardIdx !== index) {
                            if (clips[index].locked) {
                                alert("Cannot drop here: target clip is locked.");
                                return;
                            }
                            const temp = clips[dragSrcCardIdx];
                            clips.splice(dragSrcCardIdx, 1);
                            clips.splice(index, 0, temp);
                            renderClips();
                            savePlanToServer();
                        }
                        dragSrcCardIdx = null;
                    });
                }

                clipListContainer.appendChild(card);
            });
            
            // Restore scroll position to prevent jumping
            clipListContainer.scrollTop = savedScrollTop;

        }

        // Combine Audio
        exportBtn.addEventListener('click', function() {
            const lockedClips = clips.filter(c => c.locked);
            if (lockedClips.length === 0) {
                alert("Please lock at least one clip card first. Only locked clips will be combined.");
                return;
            }
            
            exportBtn.innerHTML = '⏳ Combining...';
            exportBtn.disabled = true;
            updateStateBar("Compiling and combining locked clips...");
            
            // Call the combine-project-audio endpoint
            fetch(`/combine-project-audio?id=${activeProjectId}`, {
                method: 'POST'
            })
            .then(res => {
                if (!res.ok) {
                    return res.text().then(text => { throw new Error(text); });
                }
                return res.json();
            })
            .then(data => {
                if (data.success) {
                    lastCombinedUrl = data.combined_url;
                    
                    // Stop any active locked sequences or previews
                    if (activeLockedSequence !== null) {
                        stopLockedSequence();
                    }
                    
                    // Load and play in the main bottom player bar
                    audioElement.src = data.combined_url;
                    audioElement.volume = 1.0;
                    audioElement.play()
                        .then(() => {
                            nowPlayingTitle.textContent = `🔗 Combined Preview (${lockedClips.length} Locked Clips)`;
                            updateStateBar(`Playing combined audio preview (${lockedClips.length} clips locked)`);
                            playBtn.textContent = '⏸';
                        })
                        .catch(err => {
                            showDebug("Failed to play combined audio: " + err.message);
                        });
                } else {
                    throw new Error("Invalid response.");
                }
            })
            .catch(err => {
                showDebug("Error combining audio: " + err.message, true);
                updateStateBar("Ready");
            })
            .finally(() => {
                exportBtn.innerHTML = '🔗 Combine Audio';
                exportBtn.disabled = false;
            });
        });



        // Open Export Plan Modal
        openExportModalBtn.addEventListener('click', function() {
            if (clips.length === 0) {
                alert("Please add some clips to the plan first.");
                return;
            }
            
            exportModalOverlay.classList.remove('minimized');
            exportModalOverlay.classList.add('active');
            combineModalHeaderTitle.textContent = "COMBINED AUDIO PREVIEW";
            minimizeModalBtn.textContent = "🗕";
            combineLoadingState.style.display = 'none';
            combinePlayerState.style.display = 'flex';
            planJsonSection.style.display = 'none';
            showPlanJsonBtn.textContent = "📋 View Plan JSON";
            
            combinedAudioPlayer.src = lastCombinedUrl || "";
            downloadCombinedAudioBtn.href = lastCombinedUrl || "#";
            exportTextarea.value = JSON.stringify(clips, null, 4);
        });

        minimizeModalBtn.addEventListener('click', function() {
            if (exportModalOverlay.classList.contains('minimized')) {
                exportModalOverlay.classList.remove('minimized');
                combineModalHeaderTitle.textContent = "COMBINED AUDIO PREVIEW";
                minimizeModalBtn.textContent = "🗕";
                minimizeModalBtn.title = "Minimize player to bottom-right";
            } else {
                exportModalOverlay.classList.add('minimized');
                combineModalHeaderTitle.textContent = "🎧 Combined Preview";
                minimizeModalBtn.textContent = "⛶";
                minimizeModalBtn.title = "Restore player to center";
            }
        });

        closeModalBtn.addEventListener('click', function() {
            exportModalOverlay.classList.remove('active');
            exportModalOverlay.classList.remove('minimized');
            combinedAudioPlayer.pause();
            combinedAudioPlayer.src = "";
        });

        closeVideoModalBtn.addEventListener('click', function() {
            videoModalOverlay.classList.remove('active');
            previewVideoPlayer.pause();
            previewVideoPlayer.src = "";
        });

        closeMosaicPromptModalBtn.addEventListener('click', function() {
            mosaicPromptModalOverlay.classList.remove('active');
        });
        cancelMosaicPromptBtn.addEventListener('click', function() {
            mosaicPromptModalOverlay.classList.remove('active');
        });
        mosaicPromptModalOverlay.addEventListener('click', function(e) {
            if (e.target === mosaicPromptModalOverlay) {
                mosaicPromptModalOverlay.classList.remove('active');
            }
        });

        videoModalOverlay.addEventListener('click', function(e) {
            if (e.target === videoModalOverlay) {
                videoModalOverlay.classList.remove('active');
                previewVideoPlayer.pause();
                previewVideoPlayer.src = "";
            }
        });

        showPlanJsonBtn.addEventListener('click', function() {
            if (planJsonSection.style.display === 'none') {
                planJsonSection.style.display = 'flex';
                this.textContent = "📋 Hide Plan JSON";
            } else {
                planJsonSection.style.display = 'none';
                this.textContent = "📋 View Plan JSON";
            }
        });

        copyJsonBtn.addEventListener('click', function() {
            exportTextarea.select();
            document.execCommand('copy');
            alert("JSON plan copied to clipboard!");
        });

        downloadPlanBtn.addEventListener('click', function() {
            savePlanToServer();
            alert("Successfully saved plan to plan.json!");
            exportModalOverlay.classList.remove('active');
        });
    
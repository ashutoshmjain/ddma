import http.server
import socketserver
import webbrowser
import threading
import time
import sys
import os
import re
import json
import shutil
import subprocess
from urllib.parse import urlparse, parse_qs

PORT = 8000

# Background thread helper for running Whisper transcription
def run_transcribe(project_id, audio_path, out_json_path, info_path):
    try:
        print(f"[{project_id}] Background Whisper transcription started on {audio_path}")
        python_exe = r"C:\Users\ashut\AppData\Local\Programs\Python\Python312\python.exe"
        cmd = [
            python_exe,
            "ddma.py",
            "transcribe",
            "--audio", audio_path,
            "--out", out_json_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            print(f"[{project_id}] Background Whisper transcription completed successfully.")
            # Update status to ready
            if os.path.exists(info_path):
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                info["status"] = "ready"
                with open(info_path, "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=4)
        else:
            raise Exception(res.stderr or "Whisper exited with non-zero code.")
    except Exception as e:
        print(f"[{project_id}] Background Whisper transcription error: {e}")
        # Update status to error
        try:
            if os.path.exists(info_path):
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                info["status"] = "error"
                info["error_message"] = str(e)
                with open(info_path, "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=4)
        except:
            pass


# Migration Helper for Legacy Root files
def migrate_legacy_files():
    # Clean up any leftover trash folders from previous sessions
    try:
        if os.path.exists("projects"):
            for folder in os.listdir("projects"):
                if folder.startswith(".trash_"):
                    trash_path = os.path.join("projects", folder)
                    try:
                        shutil.rmtree(trash_path)
                    except:
                        pass
    except:
        pass

    # If legacy files exist in root and we don't have episode_244 project, migrate them automatically
    os.makedirs("projects", exist_ok=True)
    legacy_project_dir = os.path.join("projects", "episode_244")
    
    if not os.path.exists(legacy_project_dir):
        has_legacy = os.path.exists("transcription.json") and os.path.exists("plan.json") and os.path.exists("244.m4a")
        if has_legacy:
            print("Detected legacy root files for Episode 244. Auto-migrating to multi-project layout...")
            try:
                os.makedirs(legacy_project_dir, exist_ok=True)
                # Copy files into project folder
                shutil.copy2("transcription.json", os.path.join(legacy_project_dir, "transcription.json"))
                shutil.copy2("plan.json", os.path.join(legacy_project_dir, "plan.json"))
                shutil.copy2("244.m4a", os.path.join(legacy_project_dir, "audio.m4a"))
                
                # Write metadata
                info = {
                    "id": "episode_244",
                    "name": "Episode 244",
                    "audio_filename": "audio.m4a",
                    "status": "ready"
                }
                with open(os.path.join(legacy_project_dir, "project_info.json"), "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=4)
                print("Episode 244 successfully migrated to projects/episode_244/")
            except Exception as e:
                print(f"Warning: Failed to migrate legacy files: {e}")


class RangeHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def compile_segments(self, segments, output_path, audio_source_path):
        temp_files = []
        try:
            for idx, seg in enumerate(segments):
                temp_file = f"temp_preview_{idx}.wav"
                temp_files.append(temp_file)
                
                if seg["type"] == "audio":
                    # Slice audio segment from project audio source
                    start = seg["start"]
                    end = seg["end"]
                    volume = seg.get("volume", 1.0)
                    cmd = [
                        "ffmpeg", "-y",
                        "-ss", str(start),
                        "-to", str(end),
                        "-i", audio_source_path,
                        "-ar", "48000",
                        "-ac", "2",
                        "-af", f"volume={volume}",
                        temp_file
                    ]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if res.returncode != 0:
                        raise Exception(f"FFmpeg error slicing audio: {res.stderr.decode('utf-8')}")
                elif seg["type"] == "music":
                    # Slice music segment
                    music_file = seg["music_file"]
                    duration = seg["duration"]
                    music_path = os.path.join("music", music_file)
                    
                    if not os.path.exists(music_path) or music_file == "none":
                        # Generate digital silence
                        cmd = [
                            "ffmpeg", "-y",
                            "-f", "lavfi",
                            "-i", f"anullsrc=r=48000:cl=stereo:d={duration}",
                            temp_file
                        ]
                    else:
                        # Slice music and scale volume down
                        volume = seg.get("volume", 1.0)
                        cmd = [
                            "ffmpeg", "-y",
                            "-i", music_path,
                            "-t", str(duration),
                            "-ar", "48000",
                            "-ac", "2",
                            "-af", f"volume={volume}",
                            temp_file
                        ]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if res.returncode != 0:
                        raise Exception(f"FFmpeg error slicing music: {res.stderr.decode('utf-8')}")
            
            # Concatenate them
            if len(temp_files) == 0:
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "lavfi",
                    "-i", "anullsrc=r=48000:cl=stereo:d=1.0",
                    "-c:a", "libmp3lame",
                    "-b:a", "128k",
                    output_path
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            elif len(temp_files) == 1:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", temp_files[0],
                    "-c:a", "libmp3lame",
                    "-b:a", "128k",
                    output_path
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode != 0:
                    raise Exception(f"FFmpeg error encoding preview: {res.stderr.decode('utf-8')}")
            else:
                # Check if there are any crossfades > 0
                has_crossfade = False
                crossfades = []
                for idx, seg in enumerate(segments[:-1]):
                    cf = float(seg.get("crossfade", 0.0))
                    crossfades.append(cf)
                    if cf > 0:
                        has_crossfade = True
                
                cmd = ["ffmpeg", "-y"]
                for tf in temp_files:
                    cmd += ["-i", tf]
                
                if not has_crossfade:
                    filter_complex = "".join(f"[{i}:a]" for i in range(len(temp_files)))
                    filter_complex += f"concat=n={len(temp_files)}:v=0:a=1[out]"
                else:
                    # Construct chained acrossfade filters
                    filter_parts = []
                    current_src = "[0:a]"
                    for i in range(len(temp_files) - 1):
                        cf_dur = crossfades[i]
                        # Use acrossfade with duration or tiny samples if 0
                        if cf_dur > 0:
                            fade_opts = f"d={cf_dur}"
                        else:
                            fade_opts = "ns=1"
                        
                        next_dest = f"[a{i+1}]" if i < len(temp_files) - 2 else "[out]"
                        filter_parts.append(f"{current_src}[{i+1}:a]acrossfade={fade_opts}:c1=tri:c2=tri{next_dest}")
                        current_src = f"[a{i+1}]"
                    
                    filter_complex = ";".join(filter_parts)
                
                cmd += [
                    "-filter_complex", filter_complex,
                    "-map", "[out]",
                    "-c:a", "libmp3lame",
                    "-b:a", "128k",
                    output_path
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode != 0:
                    raise Exception(f"FFmpeg error concatenating preview: {res.stderr.decode('utf-8')}")
        finally:
            # Clean up temporary files
            for tf in temp_files:
                if os.path.exists(tf):
                    try:
                        os.remove(tf)
                    except:
                        pass

    def do_POST(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        
        if parsed_url.path == '/save-project-plan':
            project_id = params.get('id', [None])[0]
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                if not project_id:
                    raise Exception("Missing project id parameter.")
                
                project_dir = os.path.join("projects", project_id)
                if not os.path.exists(project_dir):
                    raise Exception(f"Project directory {project_id} not found.")
                
                json_data = json.loads(post_data.decode('utf-8'))
                
                # Save to project's plan.json
                with open(os.path.join(project_dir, 'plan.json'), 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=4)
                
                # Sync to root plan.json
                with open('plan.json', 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=4)
                    
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b"Success")
                return
            except Exception as e:
                print(f"Error saving plan for {project_id}: {e}")
                self.send_error(500, f"Error saving plan: {e}")
                return
                
        elif parsed_url.path == '/save-project-snapshot':
            project_id = params.get('id', [None])[0]
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                
                project_dir = os.path.join("projects", project_id)
                plan_path = os.path.join(project_dir, "plan.json")
                snapshot_path = os.path.join(project_dir, "plan_snapshot.json")
                
                if os.path.exists(plan_path):
                    shutil.copy2(plan_path, snapshot_path)
                else:
                    with open(snapshot_path, "w", encoding="utf-8") as f:
                        json.dump([], f)
                        
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                return
            except Exception as e:
                self.send_error(500, f"Error saving snapshot: {e}")
                return
                
        elif parsed_url.path == '/restore-project-snapshot':
            project_id = params.get('id', [None])[0]
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                
                project_dir = os.path.join("projects", project_id)
                plan_path = os.path.join(project_dir, "plan.json")
                snapshot_path = os.path.join(project_dir, "plan_snapshot.json")
                
                if not os.path.exists(snapshot_path):
                    raise Exception("No snapshot exists for this project.")
                    
                shutil.copy2(snapshot_path, plan_path)
                shutil.copy2(snapshot_path, "plan.json")
                
                # Load the restored plan
                with open(plan_path, "r", encoding="utf-8") as f:
                    restored_plan = json.load(f)
                    
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "plan": restored_plan}).encode('utf-8'))
                return
            except Exception as e:
                self.send_error(500, f"Error restoring snapshot: {e}")
                return
                
        elif parsed_url.path == '/save-settings':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                json_data = json.loads(post_data.decode('utf-8'))
                settings_path = "settings.json"
                with open(settings_path, "w", encoding="utf-8") as f:
                    json.dump(json_data, f, indent=4)
                    
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                return
            except Exception as e:
                self.send_error(500, f"Error saving settings: {e}")
                return
                
        elif parsed_url.path == '/create-project':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                json_data = json.loads(post_data.decode('utf-8'))
                project_name = json_data.get("name", "").strip()
                audio_source = json_data.get("audio_source", "").strip()
                
                if not project_name or not audio_source:
                    raise Exception("Project name and audio source are required.")
                
                # Sanitize project id
                project_id = re.sub(r'[^a-zA-Z0-9_-]', '_', project_name.lower().replace(" ", "_"))
                project_dir = os.path.join("projects", project_id)
                
                if os.path.exists(project_dir):
                    raise Exception("Project with this name already exists.")
                
                os.makedirs(project_dir, exist_ok=True)
                
                # Check if audio file exists in root
                if not os.path.exists(audio_source):
                    raise Exception(f"Source audio file {audio_source} not found.")
                
                # Copy audio to project directory
                ext = os.path.splitext(audio_source)[1]
                dest_audio_name = f"audio{ext}"
                dest_audio_path = os.path.join(project_dir, dest_audio_name)
                
                shutil.copy2(audio_source, dest_audio_path)
                
                # Create project info
                info_path = os.path.join(project_dir, "project_info.json")
                info = {
                    "id": project_id,
                    "name": project_name,
                    "audio_filename": dest_audio_name,
                    "status": "transcribing"
                }
                with open(info_path, "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=4)
                
                # Create empty plan.json
                with open(os.path.join(project_dir, "plan.json"), "w", encoding="utf-8") as f:
                    json.dump([], f, indent=4)
                
                # Kick off transcription thread
                out_json_path = os.path.join(project_dir, "transcription.json")
                t = threading.Thread(target=run_transcribe, args=(project_id, dest_audio_path, out_json_path, info_path), daemon=True)
                t.start()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "project_id": project_id}).encode('utf-8'))
                return
            except Exception as e:
                self.send_error(500, str(e))
                return

        elif parsed_url.path == '/delete-project':
            project_id = params.get('id', [None])[0]
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                project_dir = os.path.join("projects", project_id)
                if os.path.exists(project_dir):
                    # Delete project_info.json first to immediately hide it from selection lists
                    info_path = os.path.join(project_dir, "project_info.json")
                    if os.path.exists(info_path):
                        try:
                            os.remove(info_path)
                        except:
                            pass
                    
                    # Try to remove the directory tree
                    try:
                        shutil.rmtree(project_dir)
                    except Exception as rmtree_err:
                        print(f"shutil.rmtree failed on {project_dir} (possibly locked file): {rmtree_err}. Attempting fallback...")
                        # Fallback: Delete all individual files we can, rename directory to hide it
                        for root, dirs, files in os.walk(project_dir, topdown=False):
                            for name in files:
                                file_path = os.path.join(root, name)
                                try:
                                    os.remove(file_path)
                                except:
                                    pass
                        
                        # Rename parent folder to a hidden .trash folder so it's ignored and can be cleaned up later
                        trash_dir = os.path.join("projects", f".trash_{project_id}_{int(time.time())}")
                        try:
                            os.rename(project_dir, trash_dir)
                        except Exception as rename_err:
                            print(f"Failed to rename trash folder: {rename_err}")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                return
            except Exception as e:
                self.send_error(500, f"Error deleting project: {e}")
                return

        elif parsed_url.path == '/rename-project':
            project_id = params.get('id', [None])[0]
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                
                json_data = json.loads(post_data.decode('utf-8'))
                new_name = json_data.get("name", "").strip()
                if not new_name:
                    raise Exception("New name is required.")
                
                project_dir = os.path.join("projects", project_id)
                info_path = os.path.join(project_dir, "project_info.json")
                if os.path.exists(info_path):
                    with open(info_path, "r", encoding="utf-8") as f:
                        info = json.load(f)
                    info["name"] = new_name
                    with open(info_path, "w", encoding="utf-8") as f:
                        json.dump(info, f, indent=4)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                return
            except Exception as e:
                self.send_error(500, f"Error renaming project: {e}")
                return

        elif parsed_url.path == '/duplicate-project':
            project_id = params.get('id', [None])[0]
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                
                json_data = json.loads(post_data.decode('utf-8'))
                new_name = json_data.get("name", "").strip()
                if not new_name:
                    raise Exception("New project name is required.")
                
                new_id = re.sub(r'[^a-zA-Z0-9_-]', '_', new_name.lower().replace(" ", "_"))
                src_dir = os.path.join("projects", project_id)
                dst_dir = os.path.join("projects", new_id)
                
                if os.path.exists(dst_dir):
                    raise Exception("Project with this name/id already exists.")
                
                shutil.copytree(src_dir, dst_dir)
                
                # Update project_info.json in the copy
                info_path = os.path.join(dst_dir, "project_info.json")
                if os.path.exists(info_path):
                    with open(info_path, "r", encoding="utf-8") as f:
                        info = json.load(f)
                    info["id"] = new_id
                    info["name"] = new_name
                    with open(info_path, "w", encoding="utf-8") as f:
                        json.dump(info, f, indent=4)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "project_id": new_id}).encode('utf-8'))
                return
            except Exception as e:
                self.send_error(500, f"Error duplicating project: {e}")
                return

        elif parsed_url.path == '/compile-project-preview':
            project_id = params.get('id', [None])[0]
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                
                project_dir = os.path.join("projects", project_id)
                info_path = os.path.join(project_dir, "project_info.json")
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                
                audio_path = os.path.join(project_dir, info["audio_filename"])
                
                json_data = json.loads(post_data.decode('utf-8'))
                segments = json_data.get("segments", [])
                clip_idx = json_data.get("clip_idx", 0)
                
                os.makedirs("previews", exist_ok=True)
                output_path = f"previews/preview_{project_id}_{clip_idx}.mp3"
                
                # Perform compilation
                self.compile_segments(segments, output_path, audio_path)
                
                response_data = {
                    "preview_url": f"previews/preview_{project_id}_{clip_idx}.mp3?t={int(time.time() * 1000)}"
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                return
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_error(500, f"Compilation error: {e}")
                return

        elif parsed_url.path == '/export-project-clip':
            project_id = params.get('id', [None])[0]
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                
                project_dir = os.path.join("projects", project_id)
                info_path = os.path.join(project_dir, "project_info.json")
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                
                audio_path = os.path.join(project_dir, info["audio_filename"])
                
                json_data = json.loads(post_data.decode('utf-8'))
                segments = json_data.get("segments", [])
                clip_num = json_data.get("clip_num", 1)
                title = json_data.get("title", f"Clip-{clip_num}")
                export_format = json_data.get("export_format", "audio")
                resolution = json_data.get("resolution", "740x740")
                bg_color = json_data.get("bg_color", "black")
                
                os.makedirs("clips", exist_ok=True)
                
                # Clean title for filename
                clean_title = "".join(c if c.isalnum() or c in "._-" else "_" for c in title)
                
                # Extract prefix from project ID or default
                prefix = project_id.split("_")[-1] if "_" in project_id else project_id
                if not prefix.isdigit():
                    prefix = project_id
                    
                ext = ".mp4" if export_format == "video" else ".mp3"
                output_filename = f"{prefix}-{clip_num}-{clean_title}{ext}"
                output_path = os.path.join("clips", output_filename)
                
                if export_format == "video":
                    temp_audio = f"temp_export_audio_{project_id}_{clip_num}.mp3"
                    try:
                        # 1. Compile audio segments first to temp_audio
                        self.compile_segments(segments, temp_audio, audio_path)
                        
                        # 2. Mux temp_audio with solid color canvas
                        ffmpeg_color = bg_color.replace('#', '0x')
                        cmd = [
                            "ffmpeg", "-y",
                            "-f", "lavfi",
                            "-i", f"color=c={ffmpeg_color}:s={resolution}:r=25",
                            "-i", temp_audio,
                            "-c:v", "libx264",
                            "-tune", "stillimage",
                            "-c:a", "aac",
                            "-b:a", "192k",
                            "-pix_fmt", "yuv420p",
                            "-shortest",
                            output_path
                        ]
                        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if res.returncode != 0:
                            raise Exception(f"FFmpeg video muxing failed: {res.stderr.decode('utf-8')}")
                    finally:
                        if os.path.exists(temp_audio):
                            try:
                                os.remove(temp_audio)
                            except:
                                pass
                else:
                    # Compile segments directly to the production clips folder as mp3
                    self.compile_segments(segments, output_path, audio_path)
                
                response_data = {
                    "success": True,
                    "filename": f"clips/{output_filename}"
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                return
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_error(500, f"Export clip error: {e}")
                return
                
        elif parsed_url.path == '/upload-music':
            # Raw binary upload handler for globally shared music stings
            filename = self.headers.get('X-Filename')
            if not filename:
                self.send_error(400, "Missing X-Filename header.")
                return
            
            # Sanitize filename
            filename = re.sub(r'[^a-zA-Z0-9_\-\.\s\(\)]', '_', filename)
            music_dir = "music"
            os.makedirs(music_dir, exist_ok=True)
            dest_path = os.path.join(music_dir, filename)
            
            content_length = int(self.headers.get('Content-Length', 0))
            try:
                print(f"Uploading new global sting: {filename} ({content_length} bytes)")
                with open(dest_path, 'wb') as f:
                    remaining = content_length
                    chunk_size = 64 * 1024
                    while remaining > 0:
                        chunk = self.rfile.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        f.write(chunk)
                        remaining -= len(chunk)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "filename": filename}).encode('utf-8'))
                return
            except Exception as e:
                self.send_error(500, str(e))
                return
                
        elif parsed_url.path == '/delete-music':
            filename = params.get('file', [None])[0]
            if not filename:
                self.send_error(400, "Missing file parameter.")
                return
            
            filename = os.path.basename(filename) # Sanitize
            file_path = os.path.join("music", filename)
            
            try:
                if os.path.exists(file_path):
                    print(f"Deleting global sting: {filename}")
                    os.remove(file_path)
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                    return
                else:
                    self.send_error(404, "File not found.")
                    return
            except Exception as e:
                self.send_error(500, str(e))
                return

        self.send_error(404, "Not Found")

    def do_GET(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        
        if parsed_url.path == '/list-projects':
            projects_list = []
            projects_dir = "projects"
            if os.path.exists(projects_dir):
                for folder in sorted(os.listdir(projects_dir)):
                    info_path = os.path.join(projects_dir, folder, "project_info.json")
                    if os.path.exists(info_path):
                        try:
                            with open(info_path, "r", encoding="utf-8") as f:
                                projects_list.append(json.load(f))
                        except Exception as e:
                            print(f"Error reading info for project {folder}: {e}")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(projects_list).encode('utf-8'))
            return
            
        elif parsed_url.path == '/list-workspace-audio':
            files = []
            for f in sorted(os.listdir(".")):
                if f.lower().endswith((".mp3", ".wav", ".m4a")):
                    files.append(f)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(files).encode('utf-8'))
            return
            
        elif parsed_url.path == '/get-project':
            project_id = params.get('id', [None])[0]
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                
                project_dir = os.path.join("projects", project_id)
                info_path = os.path.join(project_dir, "project_info.json")
                plan_path = os.path.join(project_dir, "plan.json")
                trans_path = os.path.join(project_dir, "transcription.json")
                
                if not os.path.exists(project_dir):
                    raise Exception("Project directory not found.")
                
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                
                plan_data = []
                if os.path.exists(plan_path):
                    with open(plan_path, "r", encoding="utf-8") as f:
                        plan_data = json.load(f)
                    try:
                        shutil.copy2(plan_path, "plan.json")
                    except Exception as copy_err:
                        print(f"Error syncing project plan to root: {copy_err}")
                        
                trans_data = None
                if os.path.exists(trans_path):
                    with open(trans_path, "r", encoding="utf-8") as f:
                        trans_data = json.load(f)
                
                has_snapshot = os.path.exists(os.path.join(project_dir, "plan_snapshot.json"))
                
                payload = {
                    "info": info,
                    "plan": plan_data,
                    "transcription": trans_data,
                    "has_snapshot": has_snapshot
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode('utf-8'))
                return
            except Exception as e:
                self.send_error(500, str(e))
                return
                
        elif parsed_url.path == '/list-music':
            music_dir = "music"
            files = []
            if os.path.exists(music_dir):
                files = sorted([f for f in os.listdir(music_dir) if f.lower().endswith((".mp3", ".wav", ".m4a"))])
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(files).encode('utf-8'))
            return
            
        elif parsed_url.path == '/get-settings':
            try:
                settings_path = "settings.json"
                settings_data = {}
                if os.path.exists(settings_path):
                    with open(settings_path, "r", encoding="utf-8") as f:
                        settings_data = json.load(f)
                else:
                    settings_data = {
                        "theme": "midnight",
                        "export_format": "audio",
                        "resolution": "740x740",
                        "bg_color": "black"
                    }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(settings_data).encode('utf-8'))
                return
            except Exception as e:
                self.send_error(500, str(e))
                return
                
        elif parsed_url.path == '/project-audio':
            project_id = params.get('id', [None])[0]
            audio_file = None
            if project_id:
                project_dir = os.path.join("projects", project_id)
                if os.path.exists(project_dir):
                    for f in os.listdir(project_dir):
                        if f.startswith("audio."):
                            audio_file = os.path.join(project_dir, f)
                            break
            
            if audio_file and os.path.exists(audio_file):
                self.path = "/" + audio_file.replace("\\", "/")
                return super().do_GET()
            else:
                self.send_error(404, "Audio file not found for project.")
                return

        return super().do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def send_head(self):
        path = self.translate_path(self.path)
        if not os.path.exists(path) or os.path.isdir(path):
            return super().send_head()
            
        ctype = self.guess_type(path)
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(404, "File not found")
            return None
            
        range_header = self.headers.get('Range')
        if not range_header:
            return super().send_head()
            
        match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if not match:
            self.send_error(400, "Bad Request (invalid range)")
            f.close()
            return None
            
        size = os.path.getsize(path)
        start = int(match.group(1))
        end = match.group(2)
        end = int(end) if end else size - 1
        
        if start >= size or end >= size or start > end:
            self.send_error(416, "Requested Range Not Satisfiable")
            self.send_header('Content-Range', f'bytes */{size}')
            self.end_headers()
            f.close()
            return None
            
        self.send_response(206)
        self.send_header('Content-type', ctype)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Last-Modified', self.date_time_string(os.path.getmtime(path)))
        self.end_headers()
        
        f.seek(start)
        return f

    def copyfile(self, source, outputfile):
        range_header = self.headers.get('Range')
        if not range_header or self.path.endswith('.html') or self.path.endswith('.json'):
            super().copyfile(source, outputfile)
            return

        match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if not match:
            super().copyfile(source, outputfile)
            return

        size = os.path.getsize(self.translate_path(self.path))
        start = int(match.group(1))
        end = match.group(2)
        end = int(end) if end else size - 1

        length = end - start + 1
        buffer_size = 64 * 1024
        while length > 0:
            chunk = source.read(min(buffer_size, length))
            if not chunk:
                break
            outputfile.write(chunk)
            length -= len(chunk)

    def log_message(self, format, *args):
        pass

def start_server():
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), RangeHTTPRequestHandler) as httpd:
            print(f"Server started on http://localhost:{PORT}")
            httpd.serve_forever()
    except Exception as e:
        print(f"Server error: {e}")

def main():
    print("==================================================")
    print("      DDMA Clip Curator Launcher v2.0 (Multi-Proj)")
    print("==================================================")
    
    # Run legacy data migration to avoid losing 244 progress
    migrate_legacy_files()
    
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    
    time.sleep(0.5)
    
    url = f"http://localhost:{PORT}/curator.html"
    print(f"Opening browser at: {url}")
    
    webbrowser.open(url)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down curator server. Goodbye!")
        sys.exit(0)

if __name__ == "__main__":
    main()

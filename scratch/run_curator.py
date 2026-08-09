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
import requests
from urllib.parse import urlparse, parse_qs

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

def configure_gemini(api_key=None):
    if not HAS_GENAI:
        return False
    creds_path = "gemini-creds.json"
    if os.path.exists(creds_path):
        try:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(creds_path)
            genai.configure(credentials=creds)
            print("[Gemini] Configured successfully using service account JSON credentials.")
            return True
        except Exception as e:
            print(f"[Gemini] Warning: Failed to load service account credentials: {e}")
            
    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False

PORT = 8000

# Global tracker for background Mosaic runs
# Keys: (project_id, clip_num), Values: {"status": ..., "progress": ..., "error": ..., "run_id": ...}
mosaic_runs = {}

def auto_recompile_clip(project_id, clip_num):
    try:
        ep_num_match = re.search(r'\d+', str(project_id))
        ep_num = ep_num_match.group(0) if ep_num_match else "244"
        master_clip_path = os.path.join("clips", f"{ep_num}-{clip_num}.mp4")
        orig_clip_path = os.path.join("clips", f"{ep_num}-{clip_num}-original.mp4")
        if os.path.exists(master_clip_path) or os.path.exists(orig_clip_path):
            import sys
            plan_path = os.path.join("projects", project_id, "plan.json")
            print(f"[{project_id}][Clip {clip_num}] Auto re-compiling clip after title/bridge update...")
            subprocess.run([
                sys.executable, "ddma.py", "compile-clip",
                "--num", str(clip_num),
                "--plan-file", plan_path
            ], check=True)
            print(f"[{project_id}][Clip {clip_num}] Auto re-compilation complete!")
    except Exception as e:
        print(f"[{project_id}][Clip {clip_num}] Warning: Auto compile-clip failed: {e}")

# Background thread helper for executing the Mosaic API pipeline (upload, run, poll, download)
def run_mosaic_pipeline(project_id, clip_num, settings, prompt_content, segments, audio_path, run_id=None):
    job_key = (project_id, int(clip_num))
    mosaic_runs[job_key] = {"status": "starting", "progress": 0, "error": None, "run_id": run_id, "start_time": time.time()}
    
    try:
        api_key = settings.get("mosaic_api_key")
        agent_id = settings.get("mosaic_agent_id")
        mogr_node_id = settings.get("mosaic_mogr_node_id")
        captions_node_id = settings.get("mosaic_captions_node_id")
        
        if not api_key or not agent_id:
            raise Exception("Mosaic API Key and Agent ID must be configured in System Settings first.")
        
        headers = {"Authorization": f"Bearer {api_key}"}
        base_url = "https://api.mosaic.so"
        
        # 1. Locate local file
        ep_num_match = re.search(r'\d+', project_id)
        if not ep_num_match:
            raise Exception(f"Could not resolve episode number from project ID '{project_id}'")
        ep_num = ep_num_match.group(0)
        
        file_path = os.path.join("clips", f"{ep_num}-{clip_num}.mp4")

        if not run_id:
            # Force recompilation of the black draft video on a fresh Mosaic run so any audio changes are captured!
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as rm_err:
                    print(f"Warning: could not delete old clip file: {rm_err}")
                    
            backup_path = os.path.join("clips", f"{ep_num}-{clip_num}-original.mp4")
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except Exception as rm_err:
                    print(f"Warning: could not delete old backup file: {rm_err}")
                    
            # Step 1: Run complete Draft Video pipeline to prepare fresh baseline MP4 (audio + title/outro cards)
            mosaic_runs[job_key]["status"] = "compiling draft video"
            mosaic_runs[job_key]["progress"] = 5
            print(f"[{project_id}][Clip {clip_num}] Executing Draft Video pipeline before Mosaic upload...")
            
            os.makedirs("clips", exist_ok=True)
            plan_file_path = os.path.join("projects", project_id, "plan.json")
            
            # Slice fresh audio clip
            cut_cmd = [sys.executable, "ddma.py", "cut", "--audio", audio_path, "--plan-file", plan_file_path, "--out-dir", "clips"]
            res_cut = subprocess.run(cut_cmd, capture_output=True, text=True, cwd=".")
            if res_cut.returncode != 0:
                print(f"[{project_id}][Clip {clip_num}] Warning: Audio cut emitted stderr: {res_cut.stderr}")
                
            # Compile fresh baseline draft video
            comp_draft_cmd = [sys.executable, "ddma.py", "compile-clip", "--num", str(clip_num), "--plan-file", plan_file_path, "--force-draft"]
            res_draft = subprocess.run(comp_draft_cmd, capture_output=True, text=True, cwd=".")
            if res_draft.returncode != 0:
                raise Exception(f"Failed to prepare baseline draft video for Mosaic: {res_draft.stderr}")
            print(f"[{project_id}][Clip {clip_num}] Fresh baseline draft video compiled successfully: {file_path}")
            
            # Step 2: Upload S3
            mosaic_runs[job_key]["status"] = "requesting upload URL"
            mosaic_runs[job_key]["progress"] = 10
            print(f"[{project_id}][Clip {clip_num}] Requesting upload URL from Mosaic...")
            
            # Get upload details
            res = requests.post(f"{base_url}/uploads/video/get_upload_url", headers=headers)
            if res.status_code != 200:
                raise Exception(f"Mosaic get_upload_url failed: {res.text}")
            
            upload_data = res.json()
            upload_url = upload_data.get("upload_url")
            upload_fields = upload_data.get("upload_fields", {})
            video_id = upload_data.get("video_id")
            
            if not upload_url or not video_id:
                raise Exception("Failed to retrieve upload parameters from Mosaic.")
            
            # Post file to S3
            mosaic_runs[job_key]["status"] = "uploading media"
            mosaic_runs[job_key]["progress"] = 30
            print(f"[{project_id}][Clip {clip_num}] Uploading {file_path} to Mosaic S3 storage...")
            
            with open(file_path, "rb") as f:
                files = {
                    "file": (os.path.basename(file_path), f, "video/mp4")
                }
                res_s3 = requests.post(upload_url, data=upload_fields, files=files)
                
            if res_s3.status_code not in (200, 201, 204):
                raise Exception(f"S3 upload failed: Status code {res_s3.status_code}, response: {res_s3.text}")
            
            # Finalize upload
            mosaic_runs[job_key]["status"] = "finalizing upload"
            mosaic_runs[job_key]["progress"] = 50
            print(f"[{project_id}][Clip {clip_num}] Finalizing upload on Mosaic...")
            
            res_finalize = requests.post(
                f"{base_url}/uploads/video/finalize_upload",
                headers=headers,
                json={"video_id": video_id}
            )
            if res_finalize.status_code != 200:
                raise Exception(f"Mosaic finalize_upload failed: {res_finalize.text}")
            
            # Step 3: Trigger Agent Run
            mosaic_runs[job_key]["status"] = "triggering run"
            mosaic_runs[job_key]["progress"] = 60
            print(f"[{project_id}][Clip {clip_num}] Triggering Mosaic agent run...")
            
            update_params = {}
            if mogr_node_id:
                update_params[mogr_node_id] = {
                    "prompt": prompt_content,
                    "model_tier": "pro",
                    "style_video_url": "https://www.youtube.com/shorts/xybpfL1GnEQ",
                    "frequency_per_minute": "auto",
                    "reference_links": "",
                    "only_generate_full_screen_graphics": True
                }
            if captions_node_id:
                update_params[captions_node_id] = {
                    "font1": "Montserrat",
                    "font2": "Besley",
                    "animation_style": "cinematic",
                    "caption_position": "bottom"
                }
            
            run_body = {
                "video_ids": [video_id]
            }
            if update_params:
                run_body["update_params"] = update_params
            
            res_run = requests.post(
                f"{base_url}/agent/{agent_id}/run",
                headers=headers,
                json=run_body
            )
            if res_run.status_code != 200:
                raise Exception(f"Failed to start agent run on Mosaic: {res_run.text}")
            
            run_id = res_run.json().get("run_id")
            if not run_id:
                raise Exception("Failed to retrieve run ID from Mosaic execution response.")

            mosaic_runs[job_key]["run_id"] = run_id

            # Persist mosaic_run_id to plan.json immediately so interrupt/resumes are 100% recoverable
            try:
                plan_path = os.path.join("projects", project_id, "plan.json")
                if os.path.exists(plan_path):
                    with open(plan_path, "r", encoding="utf-8") as f:
                        plan = json.load(f)
                    for c in plan:
                        if int(c.get("num", -1)) == int(clip_num):
                            c["mosaic_run_id"] = run_id
                            break
                    with open(plan_path, "w", encoding="utf-8") as f:
                        json.dump(plan, f, indent=4)
                    print(f"[{project_id}][Clip {clip_num}] Immediately saved mosaic_run_id {run_id} to plan.json for interrupt/resume protection!")
            except Exception as pe:
                print(f"[{project_id}][Clip {clip_num}] Warning: Failed to save initial mosaic_run_id to plan.json: {pe}")

        # Resume / Start Step 4: Polling
        mosaic_runs[job_key]["status"] = "running"
        mosaic_runs[job_key]["progress"] = 70
        print(f"[{project_id}][Clip {clip_num}] Polling Mosaic run {run_id} status every 60 seconds (4 hours max)...")
        
        max_attempts = 240  # 4 hours max at 60-second intervals
        attempt = 0
        final_video_url = None
        
        while attempt < max_attempts:
            attempt += 1
            
            try:
                res_status = requests.get(f"{base_url}/agent_run/{run_id}", headers=headers)
                if res_status.status_code != 200:
                    print(f"[{project_id}][Clip {clip_num}] Error checking Mosaic run status: {res_status.text}")
                    time.sleep(60)
                    continue
                run_info = res_status.json()
            except Exception as poll_ex:
                print(f"[{project_id}][Clip {clip_num}] Warning: Connection glitch while polling Mosaic status: {poll_ex}. Retrying in 60 seconds...")
                time.sleep(60)
                continue
            
            status = run_info.get("status")
            
            print(f"[{project_id}][Clip {clip_num}] Polling Mosaic run status: {status}")
            
            if status == "completed":
                outputs = run_info.get("outputs", [])
                if outputs and outputs[0].get("video_url"):
                    final_video_url = outputs[0]["video_url"]
                    break
                else:
                    raise Exception("Mosaic run completed but no output video URL was returned.")
            elif status in ("failed", "cancelled"):
                err_msg = run_info.get("status_message") or "Unknown run error."
                node_errors = run_info.get("errors", [])
                if node_errors:
                    err_msg += f" Detailed errors: {json.dumps(node_errors)}"
                raise Exception(f"Mosaic run ended with status '{status}': {err_msg}")
            
            # Update progress incrementally while running
            mosaic_runs[job_key]["progress"] = min(70 + int((attempt / max_attempts) * 25), 95)
            time.sleep(60)
        
        if not final_video_url:
            raise Exception("Mosaic run timed out after 4 hours.")
            
        # Step 5: Download finished video
        mosaic_runs[job_key]["status"] = "downloading output"
        mosaic_runs[job_key]["progress"] = 95
        print(f"[{project_id}][Clip {clip_num}] Downloading rendered video from Mosaic S3...")
        
        mosaic_version_path = os.path.join("clips", f"{ep_num}-{clip_num}-mosaic-{run_id}.mp4")
        backup_path = os.path.join("clips", f"{ep_num}-{clip_num}-original.mp4")
        
        # Purge older Mosaic render files for this clip (e.g. clips/245-13-mosaic-*.mp4)
        import glob
        for f_cand in glob.glob(os.path.join("clips", f"{ep_num}-{clip_num}-mosaic-*.mp4")):
            if f_cand != mosaic_version_path:
                try:
                    os.remove(f_cand)
                    print(f"[{project_id}][Clip {clip_num}] Purged older Mosaic render: {f_cand}")
                except Exception as p_err:
                    print(f"Warning: Could not purge older Mosaic render {f_cand}: {p_err}")
        
        res_download = requests.get(final_video_url, stream=True)
        if res_download.status_code != 200:
            raise Exception(f"Failed to download rendered video from Mosaic: {res_download.status_code}")
            
        with open(mosaic_version_path, "wb") as f_out:
            for chunk in res_download.iter_content(chunk_size=8192):
                f_out.write(chunk)
                
        # Copy to backup_path for backwards compatibility
        try:
            shutil.copyfile(mosaic_version_path, backup_path)
        except Exception as copy_ex:
            print(f"Warning: Could not copy to backup_path: {copy_ex}")

        # Persist mosaic_run_id into plan.json AFTER successful download!
        try:
            plan_path = os.path.join("projects", project_id, "plan.json")
            if os.path.exists(plan_path):
                with open(plan_path, "r", encoding="utf-8") as f:
                    plan = json.load(f)
                for c in plan:
                    if int(c.get("num", -1)) == int(clip_num):
                        c["mosaic_run_id"] = run_id
                        break
                with open(plan_path, "w", encoding="utf-8") as f:
                    json.dump(plan, f, indent=4)
                print(f"[{project_id}][Clip {clip_num}] Persisted mosaic_run_id {run_id} to plan.json after successful download!")
        except Exception as pe:
            print(f"[{project_id}][Clip {clip_num}] Warning: Failed to save mosaic_run_id to plan.json: {pe}")
            
        mosaic_runs[job_key] = {"status": "completed", "progress": 100, "run_id": run_id, "error": None}
        print(f"[{project_id}][Clip {clip_num}] Mosaic download completed successfully! Status set to completed.")
        
    except Exception as ex:
        import traceback
        tb_str = traceback.format_exc()
        print(f"Error in run_mosaic_pipeline for clip {clip_num}: {ex}\n{tb_str}")
        mosaic_runs[job_key] = {"status": "failed", "error": str(ex), "progress": 0}
        
        # If run failed or crashed, clean up any unverified mosaic_run_id in plan.json
        try:
            plan_path = os.path.join("projects", project_id, "plan.json")
            if os.path.exists(plan_path):
                with open(plan_path, "r", encoding="utf-8") as f:
                    plan = json.load(f)
                for c in plan:
                    if int(c.get("num", -1)) == int(clip_num) and "mosaic_run_id" in c:
                        del c["mosaic_run_id"]
                        break
                with open(plan_path, "w", encoding="utf-8") as f:
                    json.dump(plan, f, indent=4)
                print(f"[{project_id}][Clip {clip_num}] Cleaned up unverified mosaic_run_id from plan.json on error")
        except Exception as pe:
            print(f"Warning: Failed to clean up mosaic_run_id from plan.json on error: {pe}")

# Helper function to slice and concatenate audio/music segments using FFmpeg (identical to compile_segments)
def compile_segments_helper(segments, output_path, audio_source_path):
    temp_files = []
    try:
        for idx, seg in enumerate(segments):
            temp_file = f"temp_preview_{idx}.wav"
            temp_files.append(temp_file)
            
            if seg["type"] == "audio":
                # Slice audio segment from project audio source with trim & fade
                raw_start = float(seg["start"])
                raw_end = float(seg["end"])
                trim_start = float(seg.get("trim_start", 0.0))
                # Default trim_end for speech audio is 0.1s (cleans trailing Whisper phoneme bleed)
                trim_end = float(seg.get("trim_end", 0.1 if "trim_end" not in seg else seg.get("trim_end")))
                
                effective_start = raw_start + trim_start
                effective_end = max(effective_start + 0.1, raw_end - trim_end)
                eff_dur = effective_end - effective_start

                fade_in = float(seg.get("fade_in", 0.0))
                fade_out = float(seg.get("fade_out", 0.0))
                volume = float(seg.get("volume", 1.0))

                filters = []
                if fade_in > 0:
                    fade_in_dur = min(fade_in, eff_dur / 2.0)
                    filters.append(f"afade=t=in:ss=0:d={fade_in_dur:.3f}:curve=qsin")
                if fade_out > 0:
                    fade_out_dur = min(fade_out, eff_dur / 2.0)
                    st_time = max(0.0, eff_dur - fade_out_dur)
                    filters.append(f"afade=t=out:st={st_time:.3f}:d={fade_out_dur:.3f}:curve=qsin")
                filters.append(f"volume={volume}")
                af_str = ",".join(filters)

                cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{effective_start:.3f}",
                    "-to", f"{effective_end:.3f}",
                    "-i", audio_source_path,
                    "-ar", "48000",
                    "-ac", "2",
                    "-af", af_str,
                    temp_file
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode != 0:
                    raise Exception(f"FFmpeg error slicing audio: {res.stderr.decode('utf-8')}")

            elif seg["type"] == "music":
                # Slice music segment with trim & fade
                music_file = seg.get("music_file", "")
                raw_duration = float(seg.get("duration", 4.5))
                trim_start = float(seg.get("trim_start", 0.0))
                trim_end = float(seg.get("trim_end", 0.0))
                
                eff_dur = max(0.1, raw_duration - trim_start - trim_end)
                fade_in = float(seg.get("fade_in", 0.0))
                # Default fade_out for music stings is 2.0s for DJ ducking
                fade_out = float(seg.get("fade_out", 2.0 if "fade_out" not in seg else seg.get("fade_out")))
                volume = float(seg.get("volume", 1.0))

                music_path = os.path.join("music", music_file) if music_file else ""
                
                if not os.path.exists(music_path) or music_file == "none":
                    # Generate digital silence
                    cmd = [
                        "ffmpeg", "-y",
                        "-f", "lavfi",
                        "-i", f"anullsrc=r=48000:cl=stereo:d={eff_dur:.3f}",
                        temp_file
                    ]
                else:
                    filters = []
                    if fade_in > 0:
                        fade_in_dur = min(fade_in, eff_dur / 2.0)
                        filters.append(f"afade=t=in:ss=0:d={fade_in_dur:.3f}:curve=qsin")
                    if fade_out > 0:
                        fade_out_dur = min(fade_out, eff_dur)
                        st_time = max(0.0, eff_dur - fade_out_dur)
                        filters.append(f"afade=t=out:st={st_time:.3f}:d={fade_out_dur:.3f}:curve=qsin")
                    filters.append(f"volume={volume}")
                    af_str = ",".join(filters)

                    cmd = ["ffmpeg", "-y"]
                    if trim_start > 0:
                        cmd += ["-ss", f"{trim_start:.3f}"]
                    cmd += [
                        "-i", music_path,
                        "-t", f"{eff_dur:.3f}",
                        "-ar", "48000",
                        "-ac", "2",
                        "-af", af_str,
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
                # Construct chained acrossfade filters with quarter-sine curves
                filter_parts = []
                current_src = "[0:a]"
                for i in range(len(temp_files) - 1):
                    cf_dur = crossfades[i]
                    if cf_dur > 0:
                        fade_opts = f"d={cf_dur:.3f}:c1=qsin:c2=qsin"
                    else:
                        fade_opts = "ns=1"
                    
                    next_dest = f"[a{i+1}]" if i < len(temp_files) - 2 else "[out]"
                    filter_parts.append(f"{current_src}[{i+1}:a]acrossfade={fade_opts}{next_dest}")
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

# Background thread helper for running Whisper transcription
def run_transcribe(project_id, audio_path, out_json_path, info_path):
    try:
        print(f"[{project_id}] Background Whisper transcription started on {audio_path}")
        python_exe = sys.executable
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
            
            # Extract episode number if available
            ep_num_match = re.search(r'\d+', project_id)
            if ep_num_match:
                ep_num = int(ep_num_match.group(0))
            else:
                existing_nums = [244]
                if os.path.exists("projects"):
                    for p in os.listdir("projects"):
                        m = re.search(r'\d+', p)
                        if m: existing_nums.append(int(m.group(0)))
                ep_num = max(existing_nums) + 1
            
            # Read project info
            info = {}
            if os.path.exists(info_path):
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
            title = info.get("name", f"Episode {ep_num}")
            
            print(f"[{project_id}] Kicking off automated clip ingestion pipeline...")
            ingest_cmd = [
                python_exe,
                "ddma.py",
                "ingest-episode",
                "--audio", audio_path,
                "--episode", str(ep_num),
                "--title", title
            ]
            subprocess.run(ingest_cmd, check=True)
            print(f"[{project_id}] Background project creation pipeline completed successfully!")

            if os.path.exists(info_path):
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                info["status"] = "ready"
                info["audio_filename"] = info.get("audio_filename") or info.get("audio_file") or os.path.basename(audio_path)
                info["audio_file"] = info["audio_filename"]
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

    # Auto-seed published episodes from docs/episodes/ for fresh git clones
    for ep in ["244", "245"]:
        ep_dir = os.path.join("projects", f"episode_{ep}")
        docs_plan = os.path.join("docs", "episodes", ep, "plan.json")
        if not os.path.exists(ep_dir) and os.path.exists(docs_plan):
            print(f"[AUTO-SEED] Seeding starter project Episode {ep} from docs/episodes/{ep}/...")
            try:
                os.makedirs(ep_dir, exist_ok=True)
                shutil.copy2(docs_plan, os.path.join(ep_dir, "plan.json"))
                shutil.copy2(docs_plan, os.path.join(ep_dir, "plan_snapshot.json"))
                
                audio_name = f"{ep}.m4a"
                info = {
                    "id": f"episode_{ep}",
                    "name": f"Episode {ep}",
                    "title": f"Episode {ep}",
                    "audio_filename": audio_name,
                    "audio_file": audio_name,
                    "status": "ready"
                }
                with open(os.path.join(ep_dir, "project_info.json"), "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=4)
                print(f"[AUTO-SEED] Starter project Episode {ep} successfully seeded!")
            except Exception as seed_err:
                print(f"Warning: Failed to auto-seed Episode {ep}: {seed_err}")


def get_mosaic_default_prompt():
    settings_path = "settings.json"
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as sf:
                s_data = json.load(sf)
                prompt = s_data.get("mosaic_default_prompt")
                if prompt:
                    return prompt
        except Exception as se:
            print(f"Warning: Failed to load settings.json for prompt: {se}")
            
    return (
        "MOTION DESIGN INSTRUCTIONS (YOUTUBE SHORTS - around 150 to 180 seconds long)\n\n"
        "- Cover the full timeline of the video with Dan Koe–style motion graphics. Entire length of Video must be covered with no blanks\n\n"
        "- Plan around 13 to 15 segments of roughly ~ 16 seconds each. Each segment renders a graphic with changing visuals and multiple text reveals.\n\n"
        "- 'front load more aggressive infographics to engage the viewer right up front' or 'use bold Koe style shapes in the first 10 seconds').\n\n"
        "- Assume background video is a blank black glossy screen - so you must keep persistent visuals (animation or text) through out the segments and segments must merge into each other like a relay race.\n\n"
        "--------------------------------------------------\n"
        "PACING & ANIMATION RULES\n"
        "--------------------------------------------------\n"
        "- No static holds beyond 6 seconds. Introduce visual changes every 2–4 seconds.\n"
        "- Use only basic transforms: opacity, position, scale. Keep animations single-property per element.\n"
        "- Prefer step-based reveals over continuous motion. Avoid preset/template animations.\n"
        "- No gaps in infographic coverage. No dependency on external assets."
    )


def get_gemini_default_prompt():
    settings_path = "settings.json"
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as sf:
                s_data = json.load(sf)
                prompt = s_data.get("gemini_remix_prompt_template")
                if prompt:
                    return prompt
        except Exception as se:
            print(f"Warning: Failed to load settings.json for gemini prompt: {se}")
            
    return (
        "You are the Creative Remix Agent for the DeepDive Media Automator (DDMA).\n"
        "Your task is to recast the segments, title, and bridge transition text of Clip {clip_num} in the plan.\n\n"
        "### Creative & Structural Rules:\n"
        "1. **Total Duration**: The total duration of the clip MUST be strictly under 2 minutes and 55 seconds (175 seconds).\n"
        "   Calculated as: `Total = Sum(segment_durations) - Sum(segment_crossfades)`.\n"
        "2. **Storyboard Structure**:\n"
        "   - Begin with a short welcome hook / high-power speech segment (10-15 seconds) from the transcript.\n"
        "   - Followed by a quick music sting (typically 4.0 - 5.0 seconds long, 0.3s crossfade, 1.0 volume).\n"
        "   - Followed by the main audio segment (content/discussion).\n"
        "   - Followed by ending music (music segment at the end that leads into the outro).\n"
        "3. **Bridge Text**: Provide a single bold curiosity-provoking transition question in \"bridge_text\" (a list of string(s)). This question must act as a forward-looking narrative bridge that introduces the topic/theme of the *next* clip in the storyboard (to transition the viewer's interest), rather than summarizing this current clip.\n"
        "4. **Tone & Continuity**: Reference the narrative arc from the preceding locked clips to ensure this clip continues the story logically and maintains engaging hook titles.\n"
        "5. **Standalone Thought Integrity**: Every clip MUST stand on its own as a complete, coherent, and interesting statement. Avoid creating 'part 2' or dependent continuation clips. If the preceding locked clips have already fully covered or resolved a topic, do not repeat or continue discussing it; skip ahead in the neighborhood transcript to a new high-engagement standalone concept.\n"
        "6. **Deep Dive Welcome Music Restrictions**: The welcome music stings (`deepDive-soft-ok.mp3` and `deepDive-strong.mp3`) represent introductory/welcome sounds for the podcast. They can ONLY be used in the first or second clip of the entire episode storyboard (Clip 1 or Clip 2). Under no circumstances may they be used in Clip 3 or any subsequent clips. For subsequent clips, select from the other available music stings."
    )


def get_gemini_episode_default_prompt():
    settings_path = "settings.json"
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as sf:
                s_data = json.load(sf)
                prompt = s_data.get("gemini_episode_remix_prompt_template")
                if prompt:
                    return prompt
        except Exception as se:
            print(f"Warning: Failed to load settings.json for episode gemini prompt: {se}")
            
    return (
        "You are the Executive Producer & AI Storyboard Curator for the DeepDive Media Automator (DDMA).\n"
        "Your task is to analyze the full raw episode transcript and structure it into a sequence of high-engagement, standalone podcast/social video clips (typically 12 to 18 clips per episode).\n\n"
        "### 🎬 EPISODE STORYBOARDING & PRODUCTION RULES:\n"
        "1. **Strict Duration Limits**: Each clip MUST be between 60 seconds (1 minute) and 165 seconds (2 minutes 45 seconds). No clip may ever exceed 2 minutes 55 seconds (175 seconds) to maintain YouTube Shorts & Instagram Reels compliance.\n"
        "2. **Four-Element Clip Structure**: Every clip is structured into a 4-element flow: (1) Intro Title Card (2s), (2) Speech Punchline / Hook (10-15s audio segment), (3) Intro Music Sting (4-5s, full volume 1.0), (4) Main Speech Discussion Audio Segment, and (5) Ending Music Sting (4-5s, full volume 1.0) before the (6) Outro Curiosity Question Card.\n"
        "3. **Selective Forward Chronology & Standalone Integrity**: Scan the transcript chronologically from start to finish. Identify complete, high-impact thematic concepts, metaphors, and logical statements. Every clip MUST stand on its own as a self-contained, coherent, high-value thought without requiring context from previous clips. Do not create dependent \"part 2\" fragments or include unedited filler.\n"
        "4. **Punchy Social Titles**: Assign a concise, high-curiosity title (under 8 words) for each clip. DO NOT include colons, slashes, or quotes in the title text (use dashes or spaces instead) so titles are clean, readable, and safe for media files.\n"
        "5. **Verbatim Word-Level Quote Anchors**: For each clip, output exact 3-7 word verbatim transcript quote fragments (\"start_quote\" and \"end_quote\") matching the spoken transcript text so DDMA can snap clip boundaries sample-accurately to Whisper word timestamps.\n"
        "6. **Curiosity Question Bridge Cards**: Provide a single bold, forward-looking curiosity question under \"bridge_text\" (a 1-element list of strings). This question acts as a narrative bridge introducing the topic of the NEXT clip to retain audience curiosity across transitions.\n"
        "7. **Music Sting Restrictions & Volume**: Music volume must ALWAYS be set to 1.0 (100% full volume).\n"
        "   - **Clip 1 & Clip 2**: Assign introductory welcome stings (`deepDive-soft-ok.mp3` or `deepDive-strong.mp3`).\n"
        "   - **Clip 3+**: Assign standard stings (`deepDive-main.mp3`, `Bluesy Vibes (Sting) - Doug Maxwell_Media Right Productions.mp3`, or `Cartoon Bank Heist (Sting) - Doug Maxwell_Media Right Productions.mp3`). Welcome stings are STRICTLY PROHIBITED on Clip 3+ to prevent repetitive intro audio.\n\n"
        "### 📋 OUTPUT FORMAT (JSON ARRAY ONLY):\n"
        "Return ONLY a valid JSON array of clip objects with no markdown codeblock wrapping or extra conversational text:\n"
        "[\n"
        "  {\n"
        "    \"num\": 1,\n"
        "    \"title\": \"High-Curiosity Two-Line Title\",\n"
        "    \"start_quote\": \"exact 3-7 words from start of clip speech\",\n"
        "    \"end_quote\": \"exact 3-7 words from end of clip speech (70s-150s after start_quote)\",\n"
        "    \"approx_start\": 0.0,\n"
        "    \"approx_end\": 125.5,\n"
        "    \"music\": \"deepDive-soft-ok.mp3\",\n"
        "    \"music_volume\": 1.0,\n"
        "    \"bridge_text\": [\"Curiosity question for next topic?\"]\n"
        "  }\n"
        "]"
    )


def build_gemini_prompt(project_id, clip_num, directive=None):
    project_dir = os.path.join("projects", project_id)
    plan_path = os.path.join(project_dir, "plan.json")
    if not os.path.exists(plan_path):
        raise Exception(f"plan.json not found for project {project_id}.")
    
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_data = json.load(f)
    
    target_clip = None
    preceding_locked_clips = []
    for c in plan_data:
        c_num = int(c.get("num", -1))
        if c_num == int(clip_num):
            target_clip = c
        elif c_num < int(clip_num) and c.get("locked"):
            preceding_locked_clips.append(c)
            
    # Limit context to the last 5 preceding locked clips and reverse their order
    # (so the penultimate/most recent clip appears first in the prompt)
    preceding_locked_clips = preceding_locked_clips[-5:]
    preceding_locked_clips.reverse()
    
    if not target_clip:
        raise Exception(f"Clip {clip_num} not found in project plan.")
    
    trans_path = os.path.join(project_dir, "transcription.json")
    if not os.path.exists(trans_path):
        raise Exception("transcription.json not found in project directory.")
    
    with open(trans_path, "r", encoding="utf-8") as f:
        trans_data = json.load(f)
    
    orig_start = None
    orig_end = None
    for seg in target_clip.get("segments", []):
        if seg.get("type") == "audio":
            s = float(seg.get("start", 0))
            e = float(seg.get("end", 0))
            if orig_start is None or s < orig_start:
                orig_start = s
            if orig_end is None or e > orig_end:
                orig_end = e
    
    if orig_start is None:
        orig_start = 0.0
        orig_end = 120.0
    
    neigh_start = max(0.0, orig_start - 10.0)
    neigh_end = orig_start + 600.0
    
    all_segments = trans_data.get("segments", [])
    neigh_lines = []
    for s in all_segments:
        s_start = float(s.get("start", 0))
        s_end = float(s.get("end", 0))
        if s_start >= neigh_start and s_end <= neigh_end:
            text = s.get("text", "").strip()
            neigh_lines.append(f"[{s_start:.2f} - {s_end:.2f}] {text}")
    neigh_text = "\n".join(neigh_lines)
    
    music_dir = "music"
    music_files = []
    if os.path.exists(music_dir):
        music_files = [f for f in os.listdir(music_dir) if f.lower().endswith(('.mp3', '.wav'))]
    
    base_instructions = get_gemini_default_prompt()
    if "{clip_num}" in base_instructions:
        base_instructions = base_instructions.replace("{clip_num}", str(clip_num))
        
    prompt = f"{base_instructions}\n"
    if directive:
        prompt += f"\n### IMPORTANT - USER REMIX DIRECTIVE (Follow this instruction strictly!):\n- {directive}\n\n"

    prompt += f"""### Preceding Locked Clips (Context):
{json.dumps(preceding_locked_clips, indent=2)}

### Transcript Segments in the Neighborhood:
# Formatted as: [start_time_seconds - end_time_seconds] Text
{neigh_text}

### Available Music Stings:
{json.dumps(music_files, indent=2)}

You MUST respond with a single JSON object for Clip {clip_num} matching the schema below. Do not include markdown code block formatting or explanations outside the JSON object:
{{
  "num": {clip_num},
  "title": "Recasted Clip Title",
  "bridge_text": [
    "Curiosity question?"
  ],
  "segments": [
    {{
      "type": "audio",
      "start": 0.0,
      "end": 45.5,
      "duration": 45.5,
      "text": "Exact text matching transcription segments"
    }},
    {{
      "type": "music",
      "music_file": "Bluesy Vibes (Sting) - Doug Maxwell_Media Right Productions.mp3",
      "duration": 4.5,
      "crossfade": 0.3,
      "volume": 1.0
    }}
  ],
  "locked": false
}}
"""
    return prompt


class RangeHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def compile_segments(self, segments, output_path, audio_source_path):
        compile_segments_helper(segments, output_path, audio_source_path)

    def do_POST(self):
        import re
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        
        if parsed_url.path == '/help-bot':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                if not HAS_GENAI:
                    reply = "Help Error: The 'google-generativeai' library is not installed in the python environment. Run 'pip install google-generativeai' to enable the help panel."
                else:
                    settings_api_key = None
                    if os.path.exists("settings.json"):
                        try:
                            with open("settings.json", "r", encoding="utf-8") as sf:
                                s_data = json.load(sf)
                                settings_api_key = s_data.get("gemini_api_key")
                        except Exception as se:
                            print(f"Warning: Failed to load settings.json: {se}")
                    
                    api_key = settings_api_key or os.environ.get("GEMINI_API_KEY")
                    if not configure_gemini(api_key):
                        reply = "Help Error: Neither 'gemini-creds.json' credentials nor 'GEMINI_API_KEY' in settings are configured. Please set them up in DDMA first!"
                    else:
                        
                        # Load request body
                        req_json = json.loads(post_data.decode('utf-8'))
                        user_message = req_json.get("message", "")
                        history = req_json.get("history", [])
                        
                        # Load context files (cache/read on the fly)
                        context = ""
                        for doc_file in ["README.md", "CREATIVE_PROCESS.md", os.path.join(".agents", "AGENTS.md"), "settings.json"]:
                            if os.path.exists(doc_file):
                                try:
                                    with open(doc_file, "r", encoding="utf-8") as df:
                                        context += f"\n\n=== FILE: {doc_file} ===\n" + df.read()
                                except Exception as fe:
                                    print(f"Warning: Failed to read {doc_file} for help bot: {fe}")
                        
                        system_instruction = (
                            "You are the DDMA Help Assistant, an expert AI chatbot designed to assist users in understanding "
                            "and using the DeepDive Media Automator (DDMA).\n\n"
                            "### IMPORTANT SYSTEM RULE:\n"
                            "- To change or customize default Mosaic prompts (Motion Design Instructions) or Gemini Remix instructions, "
                            "users DO NOT need to edit Python code files. They can simply click the ⚙️ Settings button in the bottom left "
                            "of the Curator UI and customize the prompts directly inside the textareas. These are saved in settings.json.\n\n"
                            "Your goal is to answer UI workflow, architectural, installation, Whisper, and creative curation questions "
                            "accurately and concisely using the documentation and settings structure provided below. Keep your responses "
                            "user-friendly and formatted in clean, concise markdown.\n\n"
                            f"=== DOCUMENTATION CONTEXT ===\n{context}"
                        )
                        
                        # Convert history format
                        contents = []
                        for h in history:
                            contents.append({
                                "role": "user" if h.get("role") == "user" else "model",
                                "parts": [h.get("text", "")]
                            })
                        contents.append({
                            "role": "user",
                            "parts": [user_message]
                        })
                        
                        # Generate content with fallback list of valid models
                        model_names = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.0-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash-latest"]
                        reply = None
                        last_err = None
                        for model_name in model_names:
                            try:
                                model = genai.GenerativeModel(
                                    model_name=model_name,
                                    system_instruction=system_instruction
                                )
                                response = model.generate_content(contents)
                                reply = response.text
                                break
                            except Exception as e:
                                print(f"Co-Pilot model {model_name} failed: {e}")
                                last_err = e
                        if not reply:
                            err_str = str(last_err)
                            if "429" in err_str or "quota" in err_str.lower():
                                reply = "⚠️ Gemini API Quota Exceeded (429). Please set your personal Gemini API Key in ⚙️ Settings -> Co-Pilot Integration, or wait a minute for your quota to reset."
                            else:
                                reply = f"Co-Pilot Error: Failed to generate content. Last error: {last_err}"
                        
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"reply": reply}).encode('utf-8'))
                return
            except Exception as e:
                print(f"Error in help chatbot: {e}")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"reply": f"Co-Pilot Error: {str(e)}"}).encode('utf-8'))
                return
                
        elif parsed_url.path == '/save-project-plan':
            project_id = params.get('id', [None])[0]
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                if not project_id:
                    raise Exception("Missing project id parameter.")
                
                project_dir = os.path.join("projects", project_id)
                if not os.path.exists(project_dir):
                    raise Exception(f"Project directory {project_id} not found.")
                
                # Load the old plan to compare metadata changes
                old_plan = []
                plan_file_path = os.path.join(project_dir, 'plan.json')
                if os.path.exists(plan_file_path):
                    try:
                        with open(plan_file_path, "r", encoding="utf-8") as f:
                            old_plan = json.load(f)
                    except Exception as e:
                        print(f"Warning: Failed to load old plan for comparison: {e}")
                
                json_data = json.loads(post_data.decode('utf-8'))
                
                # Save to project's plan.json
                with open(plan_file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=4)
                
                # Sync to root plan.json
                with open('plan.json', 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=4)
                    
                # Sync to docs/episodes/EP_NUM/plan.json and docs/episodes.json
                ep_match = re.search(r'\d+', project_id)
                ep_str = ep_match.group(0) if ep_match else None
                if ep_str:
                    docs_ep_plan = os.path.join("docs", "episodes", ep_str, "plan.json")
                    if os.path.exists(os.path.dirname(docs_ep_plan)):
                        try:
                            shutil.copy2(plan_file_path, docs_ep_plan)
                        except Exception as e:
                            print(f"Error syncing docs plan.json: {e}")
                    
                    if json_data and len(json_data) > 0 and json_data[0].get("title"):
                        c1_title = json_data[0]["title"]
                        ep_mf_path = os.path.join("docs", "episodes.json")
                        if os.path.exists(ep_mf_path):
                            try:
                                with open(ep_mf_path, "r", encoding="utf-8") as mf:
                                    m_data = json.load(mf)
                                for item in m_data:
                                    if str(item.get("id")) == ep_str or str(item.get("number")) == ep_str:
                                        item["title"] = c1_title
                                        item["fullTitle"] = f"Episode {ep_str}: {c1_title}"
                                with open(ep_mf_path, "w", encoding="utf-8") as mf:
                                    json.dump(m_data, mf, indent=2)
                            except Exception as e:
                                print(f"Error updating episodes.json title: {e}")
                    
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
                
        elif parsed_url.path == '/remix-clip':
            project_id = params.get('id', [None])[0]
            clip_num = int(params.get('num', [-1])[0])
            
            directive = ""
            custom_prompt = ""
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    post_data = self.rfile.read(content_length)
                    body_json = json.loads(post_data.decode('utf-8'))
                    directive = body_json.get("directive", "").strip()
                    custom_prompt = body_json.get("prompt", "").strip()
            except Exception as body_ex:
                print(f"Warning: Failed to parse remix body: {body_ex}")
                
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                if clip_num < 0:
                    raise Exception("Invalid clip number.")
                
                # Check for Gemini API key
                settings_api_key = None
                if os.path.exists("settings.json"):
                    try:
                        with open("settings.json", "r", encoding="utf-8") as sf:
                            s_data = json.load(sf)
                            settings_api_key = s_data.get("gemini_api_key")
                    except Exception as se:
                        print(f"Warning: Failed to load settings.json: {se}")
                
                api_key = settings_api_key or os.environ.get("GEMINI_API_KEY")
                if not api_key and not os.path.exists("gemini-creds.json"):
                    raise Exception("GEMINI_API_KEY settings config is not set, and gemini-creds.json was not found.")
                
                project_dir = os.path.join("projects", project_id)
                plan_path = os.path.join(project_dir, "plan.json")
                if not os.path.exists(plan_path):
                    raise Exception(f"plan.json not found for project {project_id}.")
                
                if custom_prompt:
                    prompt = custom_prompt
                else:
                    prompt = build_gemini_prompt(project_id, clip_num, directive=directive)

                # Call Gemini with fallback chain of valid models
                configure_gemini(api_key)
                model_names = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.0-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash-latest"]
                response = None
                last_err = None
                
                for model_name in model_names:
                    try:
                        print(f"[{project_id}][Clip {clip_num}] Attempting remix with model {model_name}...")
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(
                            prompt,
                            generation_config={"response_mime_type": "application/json"}
                        )
                        if response and response.text:
                            print(f"[{project_id}][Clip {clip_num}] Successful response from model {model_name}!")
                            break
                    except Exception as me:
                        print(f"[{project_id}][Clip {clip_num}] Model {model_name} failed: {me}")
                        last_err = me
                
                if not response or not response.text:
                    err_str = str(last_err)
                    if "429" in err_str or "quota" in err_str.lower():
                        raise Exception("Gemini API Quota Exceeded (429). Please set your personal Gemini API Key in ⚙️ Settings -> Co-Pilot Integration, or wait a minute for your quota to reset.")
                    raise last_err or Exception("All Gemini models failed to generate content.")
                
                def clean_and_parse_json(text):
                    text = text.strip()
                    if text.startswith("```"):
                        lines = text.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].strip() == "```":
                            lines = lines[:-1]
                        text = "\n".join(lines).strip()
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        pass
                    first_brace = text.find("{")
                    if first_brace != -1:
                        brace_count = 0
                        for i in range(first_brace, len(text)):
                            if text[i] == "{":
                                brace_count += 1
                            elif text[i] == "}":
                                brace_count -= 1
                                if brace_count == 0:
                                    candidate = text[first_brace:i+1]
                                    try:
                                        return json.loads(candidate)
                                    except json.JSONDecodeError:
                                        pass
                    temp = text
                    while temp.endswith("}"):
                        try:
                            return json.loads(temp)
                        except json.JSONDecodeError:
                            temp = temp[:-1].strip()
                    return json.loads(text)

                try:
                    recasted_clip = clean_and_parse_json(response.text)
                except Exception as je:
                    raise Exception(f"Failed to parse Gemini response as JSON: {je}\nResponse was:\n{response.text}")
                
                recasted_clip["locked"] = False
                
                if recasted_clip.get("title"):
                    raw_title = recasted_clip["title"]
                    clean_title = re.sub(r'[:\\/*?<>|"]', ' - ', raw_title)
                    clean_title = re.sub(r'\s+-\s+-', ' -', clean_title)
                    recasted_clip["title"] = re.sub(r'\s+', ' ', clean_title).strip(" -")
                
                # Update plan_data
                with open(plan_path, 'r', encoding='utf-8') as f:
                    plan_data = json.load(f)
                    
                for idx, c in enumerate(plan_data):
                    if int(c.get("num", -1)) == clip_num:
                        plan_data[idx] = recasted_clip
                        break
                
                # Save to project's plan.json
                with open(plan_path, 'w', encoding='utf-8') as f:
                    json.dump(plan_data, f, indent=4)
                
                # Sync to root plan.json
                with open('plan.json', 'w', encoding='utf-8') as f:
                    json.dump(plan_data, f, indent=4)
                    
                # Sync to docs/plan.json if it exists
                if os.path.exists("docs"):
                    try:
                        shutil.copy2('plan.json', os.path.join('docs', 'plan.json'))
                    except Exception as sync_err:
                        print(f"Error syncing to docs/plan.json: {sync_err}")
                
                # Auto re-compile title card intro & curiosity question outro for this clip if compiled/draft video exists
                auto_recompile_clip(project_id, clip_num)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "clip": recasted_clip}).encode('utf-8'))
                return
            except Exception as e:
                import traceback
                tb_str = traceback.format_exc()
                try:
                    print(f"Error in remixing clip {clip_num}: {e}\n{tb_str}")
                except Exception:
                    pass
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
                return

        elif parsed_url.path == '/remix-episode':
            project_id = params.get('id', [None])[0]
            custom_prompt = ""
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    post_data = self.rfile.read(content_length)
                    body_json = json.loads(post_data.decode('utf-8'))
                    if not project_id:
                        project_id = body_json.get("project_id") or body_json.get("id")
                    custom_prompt = body_json.get("prompt", "").strip()
            except Exception as ex_body:
                print(f"Warning parsing /remix-episode body: {ex_body}")

            try:
                if not project_id:
                    raise Exception("Missing project id.")

                project_dir = os.path.join("projects", project_id)
                trans_path = os.path.join(project_dir, "transcription.json")
                if not os.path.exists(trans_path):
                    raise Exception(f"transcription.json not found for {project_id}.")

                with open(trans_path, "r", encoding="utf-8") as tf:
                    t_data = json.load(tf)

                words = []
                for seg in t_data.get("segments", []):
                    words.extend(seg.get("words", []))

                if not words:
                    raise Exception("Transcription words list is empty.")

                prompt_template = custom_prompt or get_gemini_episode_default_prompt()
                transcript_summary = "\n".join([f"[{s.get('start', 0):.1f}s - {s.get('end', 0):.1f}s] {s.get('text', '').strip()}" for s in t_data.get("segments", [])])
                full_prompt = f"{prompt_template}\n\nFULL EPISODE TRANSCRIPT:\n{transcript_summary}"

                # Gemini API setup
                settings_api_key = None
                if os.path.exists("settings.json"):
                    try:
                        with open("settings.json", "r", encoding="utf-8") as sf:
                            s_data = json.load(sf)
                            settings_api_key = s_data.get("gemini_api_key")
                    except Exception: pass
                api_key = settings_api_key or os.environ.get("GEMINI_API_KEY")
                if not api_key and not os.path.exists("gemini-creds.json"):
                    raise Exception("Gemini API key is not configured.")

                configure_gemini(api_key)
                model_names = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.0-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash-latest"]
                gemini_res_text = None
                for m_name in model_names:
                    try:
                        print(f"[{project_id}] Attempting Episode Remix with model {m_name}...")
                        g_model = genai.GenerativeModel(m_name)
                        response = g_model.generate_content(full_prompt)
                        if response and response.text:
                            gemini_res_text = response.text.strip()
                            break
                    except Exception as m_ex:
                        print(f"Model {m_name} failed: {m_ex}")

                if not gemini_res_text:
                    raise Exception("Failed to receive response from Gemini models.")

                # Extract JSON array from Gemini response
                import re
                json_match = re.search(r'\[\s*\{.*\}\s*\]', gemini_res_text, re.DOTALL)
                if not json_match:
                    raise Exception("Gemini response did not contain a valid JSON array of clips.")
                
                ai_clips_raw = json.loads(json_match.group(0))
                
                # Match quotes to Whisper word timestamps
                from ddma import snap_quote_to_words
                new_plan = []
                for c_idx, raw_c in enumerate(ai_clips_raw):
                    c_num = c_idx + 1
                    s_quote = raw_c.get("start_quote", "")
                    e_quote = raw_c.get("end_quote", "")
                    approx_start = float(raw_c.get("approx_start", c_idx * 115.0))
                    approx_end = float(raw_c.get("approx_end", approx_start + 115.0))
                    
                    s_time_found, _ = snap_quote_to_words(s_quote, words, search_start_sec=approx_start)
                    _, e_time_found = snap_quote_to_words(e_quote, words, search_start_sec=max(0.0, approx_end - 25.0))
                    
                    s_time = s_time_found if s_time_found is not None else round(approx_start, 3)
                    e_time = e_time_found if e_time_found is not None else round(approx_end, 3)
                    
                    # Safeguard clip duration between 60.0s and 165.0s
                    if e_time <= s_time + 50.0:
                        e_time = round(max(s_time + 90.0, approx_end), 3)
                    if e_time - s_time > 170.0:
                        e_time = round(s_time + 165.0, 3)
                        
                    music_file = raw_c.get("music", "deepDive-soft-ok.mp3" if c_num <= 2 else "deepDive-main.mp3")
                    raw_title = raw_c.get("title", f"Clip {c_num}")
                    clean_title = re.sub(r'[:\\/*?<>|"]', ' - ', raw_title)
                    clean_title = re.sub(r'\s+-\s+-', ' -', clean_title)
                    title = re.sub(r'\s+', ' ', clean_title).strip(" -")
                    
                    # Construct 4-Element Segment Flow: Punchline Hook -> Music Sting -> Main Audio -> Ending Music
                    hook_duration = 12.0
                    hook_end = min(round(s_time + hook_duration, 2), round(e_time - 10.0, 2))
                    
                    if hook_end > s_time + 3.0:
                        segments = [
                            {
                                "type": "audio",
                                "start": s_time,
                                "end": hook_end,
                                "duration": round(hook_end - s_time, 2),
                                "volume": 1.0,
                                "crossfade": 0.0,
                                "text": f"{title} (Punchline Hook)"
                            },
                            {
                                "type": "music",
                                "music_file": music_file,
                                "duration": 5.0,
                                "volume": 1.0,
                                "crossfade": 1.0
                            },
                            {
                                "type": "audio",
                                "start": hook_end,
                                "end": e_time,
                                "duration": round(e_time - hook_end, 2),
                                "volume": 1.0,
                                "crossfade": 0.0,
                                "text": title
                            },
                            {
                                "type": "music",
                                "music_file": music_file,
                                "duration": 5.0,
                                "volume": 1.0,
                                "crossfade": 1.0
                            }
                        ]
                    else:
                        segments = [
                            {
                                "type": "music",
                                "music_file": music_file,
                                "duration": 5.0,
                                "volume": 1.0,
                                "crossfade": 1.0
                            },
                            {
                                "type": "audio",
                                "start": s_time,
                                "end": e_time,
                                "duration": round(e_time - s_time, 2),
                                "volume": 1.0,
                                "crossfade": 0.0,
                                "text": title
                            },
                            {
                                "type": "music",
                                "music_file": music_file,
                                "duration": 5.0,
                                "volume": 1.0,
                                "crossfade": 1.0
                            }
                        ]
                        
                    new_plan.append({
                        "num": c_num,
                        "title": title,
                        "start": s_time,
                        "end": e_time,
                        "locked": False,
                        "music": music_file,
                        "music_volume": 1.0,
                        "bridge_text": raw_c.get("bridge_text", [f"What happens in Part {c_num + 1}?"]),
                        "segments": segments
                    })

                plan_path = os.path.join(project_dir, "plan.json")
                with open(plan_path, "w", encoding="utf-8") as pf:
                    json.dump(new_plan, pf, indent=2)

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "plan": new_plan, "clip_count": len(new_plan)}).encode('utf-8'))
                return
            except Exception as ep_err:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(ep_err)}).encode('utf-8'))
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
                if os.path.exists("docs"):
                    try:
                        shutil.copy2("plan.json", os.path.join("docs", "plan.json"))
                    except Exception as sync_err:
                        print(f"Error syncing snapshot to docs/plan.json: {sync_err}")
                
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
                
        elif parsed_url.path == '/upload-project-audio':
            try:
                project_name = params.get('name', [None])[0]
                original_filename = params.get('filename', ['audio.mp3'])[0]
                
                if not project_name:
                    raise Exception("Missing project name.")
                
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length <= 0:
                    raise Exception("Empty file payload.")
                    
                file_bytes = self.rfile.read(content_length)
                
                # Resolve episode number and uniform project_id (episode_N)
                ep_match = re.search(r'\d+', project_name)
                if ep_match:
                    ep_num = int(ep_match.group(0))
                else:
                    existing_nums = [244]
                    if os.path.exists("projects"):
                        for p in os.listdir("projects"):
                            m = re.search(r'\d+', p)
                            if m: existing_nums.append(int(m.group(0)))
                    ep_num = max(existing_nums) + 1
                
                project_id = f"episode_{ep_num}"
                project_dir = os.path.join("projects", project_id)
                if os.path.exists(project_dir):
                    # Clean up old directory if status was not ready
                    shutil.rmtree(project_dir, ignore_errors=True)
                
                os.makedirs(project_dir, exist_ok=True)
                
                # Save binary audio file
                ext = os.path.splitext(original_filename)[1] or ".m4a"
                dest_audio_name = f"{ep_num}{ext}"
                dest_audio_path = os.path.join(project_dir, dest_audio_name)
                
                with open(dest_audio_path, "wb") as f:
                    f.write(file_bytes)
                    
                info_path = os.path.join(project_dir, "project_info.json")
                info = {
                    "id": project_id,
                    "name": project_name if "Episode" in project_name else f"Episode {ep_num}",
                    "title": project_name,
                    "audio_filename": dest_audio_name,
                    "audio_file": dest_audio_name,
                    "status": "ingesting"
                }
                with open(info_path, "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=4)
                    
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
                self.send_error(500, f"Upload project audio error: {e}")
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
                
                # Resolve episode number and uniform project_id (episode_N)
                ep_match = re.search(r'\d+', project_name)
                if ep_match:
                    ep_num = int(ep_match.group(0))
                else:
                    existing_nums = [244]
                    if os.path.exists("projects"):
                        for p in os.listdir("projects"):
                            m = re.search(r'\d+', p)
                            if m: existing_nums.append(int(m.group(0)))
                    ep_num = max(existing_nums) + 1
                
                project_id = f"episode_{ep_num}"
                project_dir = os.path.join("projects", project_id)
                if os.path.exists(project_dir):
                    shutil.rmtree(project_dir, ignore_errors=True)
                
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
                
                # Register new episode in docs/episodes.json manifest
                try:
                    ep_manifest_path = os.path.join("docs", "episodes.json")
                    if os.path.exists(ep_manifest_path):
                        with open(ep_manifest_path, "r", encoding="utf-8") as mf:
                            mdata = json.load(mf)
                        
                        title_val = json_data.get("title", project_name)
                        new_entry = {
                            "id": str(ep_num),
                            "title": f"Episode {ep_num}: {title_val}",
                            "planPath": f"episodes/{ep_num}/plan.json",
                            "clipsDir": f"episodes/{ep_num}/clips"
                        }
                        
                        mdata = [item for item in mdata if str(item.get("id")) != str(ep_num)]
                        mdata.append(new_entry)
                        
                        with open(ep_manifest_path, "w", encoding="utf-8") as mf:
                            json.dump(mdata, mf, indent=4)
                except Exception as me:
                    print(f"Warning updating episodes.json manifest during create: {me}")

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
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b""
            json_data = {}
            if post_data:
                try:
                    json_data = json.loads(post_data.decode('utf-8'))
                except Exception:
                    pass
            
            project_id = params.get('id', [None])[0] or json_data.get('id') or json_data.get('project_id')
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                
                # 1. Resolve numeric episode ID (e.g. "episode_245" -> "245")
                ep_num_match = re.search(r'\d+', str(project_id))
                ep_num = ep_num_match.group(0) if ep_num_match else None
                
                print(f"[{project_id}] Starting isolated project deletion policy (ep_num={ep_num})...")

                # 2. Delete projects/<id> directory tree
                project_dir = os.path.join("projects", project_id)
                if os.path.exists(project_dir):
                    info_path = os.path.join(project_dir, "project_info.json")
                    if os.path.exists(info_path):
                        try:
                            os.remove(info_path)
                        except Exception:
                            pass
                    try:
                        shutil.rmtree(project_dir)
                    except Exception as rmtree_err:
                        print(f"shutil.rmtree failed on {project_dir}: {rmtree_err}. Cleaning files individually...")
                        for root, dirs, files in os.walk(project_dir, topdown=False):
                            for name in files:
                                try:
                                    os.remove(os.path.join(root, name))
                                except Exception:
                                    pass
                        try:
                            trash_dir = os.path.join("projects", f".trash_{project_id}_{int(time.time())}")
                            os.rename(project_dir, trash_dir)
                        except Exception:
                            pass

                if ep_num:
                    # 3. Clean clips matching pattern "ep_num-*" from clips/
                    clips_dir = "clips"
                    if os.path.exists(clips_dir):
                        for fname in os.listdir(clips_dir):
                            if fname.startswith(f"{ep_num}-"):
                                try:
                                    os.remove(os.path.join(clips_dir, fname))
                                except Exception as e:
                                    print(f"Warning deleting clip {fname}: {e}")

                    # 4. Clean combined long-form videos
                    for comb_name in [f"combined_{ep_num}.mp4", f"combined_episode_{ep_num}.mp4", f"combined_{project_id}.mp4"]:
                        if os.path.exists(comb_name):
                            try:
                                os.remove(comb_name)
                            except Exception as e:
                                print(f"Warning deleting combined video {comb_name}: {e}")

                    # 5. Clean previews matching preview_project_id_* or preview_episode_ep_num_*
                    previews_dir = "previews"
                    if os.path.exists(previews_dir):
                        for pfname in os.listdir(previews_dir):
                            if pfname.startswith(f"preview_{project_id}_") or pfname.startswith(f"preview_episode_{ep_num}_"):
                                try:
                                    os.remove(os.path.join(previews_dir, pfname))
                                except Exception:
                                    pass

                    # 6. Clean web docs assets: docs/episodes/ep_num/
                    docs_ep_dir = os.path.join("docs", "episodes", ep_num)
                    if os.path.exists(docs_ep_dir):
                        try:
                            shutil.rmtree(docs_ep_dir)
                        except Exception as e:
                            print(f"Warning deleting docs episode folder {docs_ep_dir}: {e}")

                    # 7. Update docs/episodes.json manifest
                    ep_manifest_path = os.path.join("docs", "episodes.json")
                    if os.path.exists(ep_manifest_path):
                        try:
                            with open(ep_manifest_path, "r", encoding="utf-8") as mf:
                                manifest = json.load(mf)
                            
                            # Filter out deleted episode
                            updated_manifest = [m for m in manifest if str(m.get("id")) != ep_num and str(m.get("number")) != ep_num]
                            
                            # Ensure at least one default episode remains if manifest is not empty
                            if updated_manifest:
                                has_default = any(m.get("isDefault") for m in updated_manifest)
                                if not has_default:
                                    updated_manifest[0]["isDefault"] = True
                            
                            with open(ep_manifest_path, "w", encoding="utf-8") as mf:
                                json.dump(updated_manifest, mf, indent=2)
                        except Exception as me:
                            print(f"Warning updating episodes.json manifest during delete: {me}")

                print(f"[{project_id}] Isolated project deletion complete.")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                return
            except Exception as e:
                self.send_error(500, f"Error deleting project: {e}")
                return

        elif parsed_url.path == '/update-episode-title':
            project_id = params.get('id', [None])[0]
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                json_data = json.loads(post_data.decode('utf-8'))
                new_title = json_data.get("title", "").strip()
                if not new_title:
                    raise Exception("New episode title is required.")
                
                project_dir = os.path.join("projects", project_id)
                info_path = os.path.join(project_dir, "project_info.json")
                if os.path.exists(info_path):
                    with open(info_path, "r", encoding="utf-8") as f:
                        info = json.load(f)
                    info["title"] = new_title
                    with open(info_path, "w", encoding="utf-8") as f:
                        json.dump(info, f, indent=4)
                
                # Auto-recompile Clip 1 intro card in background
                def run_recompile_clip1(proj_id, p_dir):
                    try:
                        p_file = os.path.join(p_dir, "plan.json")
                        cmd = [sys.executable, "ddma.py", "compile-clip", "--num", "1", "--plan-file", p_file]
                        print(f"[Update-Title][{proj_id}] Recompiling Clip 1 with new episode title: '{new_title}'")
                        subprocess.run(cmd, capture_output=True, text=True, cwd=".")
                    except Exception as ex:
                        print(f"Error recompiling clip 1: {ex}")
                
                threading.Thread(target=run_recompile_clip1, args=(project_id, project_dir), daemon=True).start()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "title": new_title}).encode('utf-8'))
                return
            except Exception as e:
                self.send_error(500, f"Error updating episode title: {e}")
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
                
                # Derive new project ID
                new_id = re.sub(r'[^a-zA-Z0-9_-]', '_', new_name.lower().replace(" ", "_"))
                
                src_dir = os.path.join("projects", project_id)
                dst_dir = os.path.join("projects", new_id)
                
                if new_id != project_id:
                    if os.path.exists(dst_dir):
                        raise Exception(f"A project directory named '{new_id}' already exists. Please delete it first.")
                    
                    # Rename project directory
                    os.rename(src_dir, dst_dir)
                    project_dir = dst_dir
                else:
                    project_dir = src_dir
                
                # Update metadata id and name
                info_path = os.path.join(project_dir, "project_info.json")
                if os.path.exists(info_path):
                    with open(info_path, "r", encoding="utf-8") as f:
                        info = json.load(f)
                    info["id"] = new_id
                    info["name"] = new_name
                    with open(info_path, "w", encoding="utf-8") as f:
                        json.dump(info, f, indent=4)
                
                # Rename matching clip files inside clips/ folder
                if new_id != project_id:
                    old_ep_match = re.search(r'\d+', project_id)
                    new_ep_match = re.search(r'\d+', new_id)
                    if old_ep_match and new_ep_match:
                        old_ep = old_ep_match.group(0)
                        new_ep = new_ep_match.group(0)
                        if old_ep != new_ep:
                            clips_dir = "clips"
                            if os.path.exists(clips_dir):
                                for file in os.listdir(clips_dir):
                                    if file.startswith(f"{old_ep}-"):
                                        old_file_path = os.path.join(clips_dir, file)
                                        # Construct new filename replacing the episode number prefix
                                        new_filename = f"{new_ep}-{file[len(old_ep)+1:]}"
                                        new_file_path = os.path.join(clips_dir, new_filename)
                                        
                                        try:
                                            # Overwrite target if it exists, as requested
                                            if os.path.exists(new_file_path):
                                                os.remove(new_file_path)
                                            os.rename(old_file_path, new_file_path)
                                        except Exception as file_err:
                                            print(f"Error renaming clip file {file} to {new_filename}: {file_err}")
                
                response_data = {
                    "success": True,
                    "new_id": new_id
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
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
                
                audio_file_name = info.get("audio_filename") or info.get("audio_file")
                audio_path = os.path.join(project_dir, audio_file_name) if audio_file_name else None
                if not audio_path or not os.path.exists(audio_path):
                    ep_num = project_id.replace("episode_", "")
                    for ext in [".m4a", ".mp3", ".wav"]:
                        cand = os.path.join(project_dir, f"{ep_num}{ext}")
                        if os.path.exists(cand):
                            audio_path = cand
                            break
                        cand2 = os.path.join(project_dir, f"episode_{ep_num}{ext}")
                        if os.path.exists(cand2):
                            audio_path = cand2
                            break
                if not audio_path or not os.path.exists(audio_path):
                    raise Exception(f"Audio file for project {project_id} not found.")
                
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

        elif parsed_url.path == '/combine-project-audio':
            project_id = params.get('id', [None])[0]
            temp_clip_files = []
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                
                project_dir = os.path.join("projects", project_id)
                info_path = os.path.join(project_dir, "project_info.json")
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                
                audio_file_name = info.get("audio_filename") or info.get("audio_file") or "245.m4a"
                audio_path = os.path.join(project_dir, audio_file_name)
                
                plan_path = os.path.join(project_dir, "plan.json")
                if not os.path.exists(plan_path):
                    raise Exception("plan.json not found.")
                    
                with open(plan_path, "r", encoding="utf-8") as f:
                    clips_list = json.load(f)
                
                # Filter to only pick up locked clips
                locked_clips = [c for c in clips_list if c.get("locked", False)]
                if not locked_clips:
                    raise Exception("No locked clips in plan to combine. Please lock at least one clip first.")
                
                os.makedirs("previews", exist_ok=True)
                
                for c_idx, c in enumerate(locked_clips):
                    c_segments = c.get("segments", [])
                    if not c_segments:
                        continue
                    temp_clip_out = f"temp_combine_clip_{project_id}_{c_idx}.wav"
                    temp_clip_files.append(temp_clip_out)
                    
                    # Compile the segments to a temporary WAV file
                    self.compile_segments(c_segments, temp_clip_out, audio_path)
                    
                    # Scale the volume of the compiled wav if clip volume is customized
                    clip_volume = c.get("volume", 1.0)
                    if clip_volume != 1.0:
                        temp_volume_out = f"temp_combine_clip_vol_{project_id}_{c_idx}.wav"
                        cmd_vol = [
                            "ffmpeg", "-y",
                            "-i", temp_clip_out,
                            "-af", f"volume={clip_volume}",
                            temp_volume_out
                        ]
                        subprocess.run(cmd_vol, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if os.path.exists(temp_volume_out):
                            os.remove(temp_clip_out)
                            os.rename(temp_volume_out, temp_clip_out)
                
                if not temp_clip_files:
                    raise Exception("No valid segments in locked clips to combine.")
                
                output_path = f"previews/combined_{project_id}.mp3"
                cmd = ["ffmpeg", "-y"]
                for tf in temp_clip_files:
                    cmd += ["-i", tf]
                
                # Check for clip-level crossfades
                has_clip_crossfade = False
                clip_crossfades = []
                for idx, c in enumerate(locked_clips[:-1]):
                    cf = float(c.get("crossfade", 0.0))
                    clip_crossfades.append(cf)
                    if cf > 0:
                        has_clip_crossfade = True
                
                if not has_clip_crossfade:
                    filter_complex = "".join(f"[{i}:a]" for i in range(len(temp_clip_files)))
                    filter_complex += f"concat=n={len(temp_clip_files)}:v=0:a=1,loudnorm=I=-16:TP=-1.5:LRA=11[out]"
                else:
                    # Construct chained acrossfade filters
                    filter_parts = []
                    current_src = "[0:a]"
                    for i in range(len(temp_clip_files) - 1):
                        cf_dur = clip_crossfades[i]
                        if cf_dur > 0:
                            fade_opts = f"d={cf_dur}"
                        else:
                            fade_opts = "ns=1"
                        
                        next_dest = f"[a{i+1}]" if i < len(temp_clip_files) - 2 else "[out_raw]"
                        filter_parts.append(f"{current_src}[{i+1}:a]acrossfade={fade_opts}:c1=tri:c2=tri{next_dest}")
                        current_src = f"[a{i+1}]"
                    
                    filter_parts.append("[out_raw]loudnorm=I=-16:TP=-1.5:LRA=11[out]")
                    filter_complex = ";".join(filter_parts)
                
                cmd += [
                    "-filter_complex", filter_complex,
                    "-map", "[out]",
                    "-c:a", "libmp3lame",
                    "-b:a", "192k",
                    output_path
                ]
                
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode != 0:
                    raise Exception(f"FFmpeg combine error: {res.stderr.decode('utf-8')}")
                
                response_data = {
                    "success": True,
                    "combined_url": f"previews/combined_{project_id}.mp3?t={int(time.time() * 1000)}"
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
                self.send_error(500, f"Combine error: {e}")
                return
            finally:
                for tf in temp_clip_files:
                    if os.path.exists(tf):
                        try:
                            os.remove(tf)
                        except:
                            pass

        elif parsed_url.path == '/get-clip-intro':
            project_id = params.get('id', [None])[0]
            clip_num = params.get('num', [None])[0]
            try:
                if not project_id or not clip_num:
                    raise Exception("Missing project id or clip number.")
                clip_num = int(clip_num)
                
                project_dir = os.path.join("projects", project_id)
                plan_path = os.path.join(project_dir, "plan.json")
                if not os.path.exists(plan_path):
                    raise Exception("plan.json not found.")
                
                with open(plan_path, "r", encoding="utf-8") as f:
                    plan_data = json.load(f)
                
                clip = None
                for c in plan_data:
                    if c["num"] == clip_num:
                        clip = c
                        break
                if not clip:
                    raise Exception(f"Clip {clip_num} not found in plan.")
                
                title = clip.get("title", "")
                
                import re
                ep_num_match = re.search(r'\d+', project_id)
                ep_num = ep_num_match.group(0) if ep_num_match else project_id
                
                title_text = title if title else f"Part {clip_num}"
                
                from PIL import Image, ImageDraw, ImageFont
                import glob
                search_pattern = os.path.join("clips", f"*-{clip_num}.mp4")
                master_files = [f for f in glob.glob(search_pattern) if not f.endswith("-original.mp4")]
                
                extracted = False
                temp_extracted = f"temp_preview_frame_{project_id}_{clip_num}.png"
                if master_files:
                    master_path = master_files[0]
                    base_name = os.path.splitext(os.path.basename(master_path))[0]
                    backup_path = os.path.join("clips", f"{base_name}-original.mp4")
                    target_video = backup_path if os.path.exists(backup_path) else master_path
                    
                    cmd_extract = [
                        "ffmpeg", "-y",
                        "-ss", "00:00:01.000",
                        "-i", target_video,
                        "-vframes", "1",
                        temp_extracted
                    ]
                    try:
                        res = subprocess.run(cmd_extract, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if res.returncode == 0 and os.path.exists(temp_extracted):
                            extracted = True
                    except Exception as extract_err:
                        print(f"Warning: Could not extract preview frame: {extract_err}")
                
                if extracted:
                    img = Image.open(temp_extracted).convert("RGBA")
                    width, height = img.size
                else:
                    width, height = 740, 740
                    img = Image.new("RGBA", (width, height), (18, 18, 18, 255))
                
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)
                
                def find_system_fonts():
                    candidates = [
                        (r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\segoeui.ttf"),
                        (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf"),
                    ]
                    for bold, reg in candidates:
                        if os.path.exists(bold) and os.path.exists(reg):
                            return bold, reg
                    return None, None
                
                font_bold, font_reg = find_system_fonts()
                if font_bold and font_reg:
                    font_title = ImageFont.truetype(font_bold, 40)
                    font_sub = ImageFont.truetype(font_reg, 24)
                else:
                    font_title = ImageFont.load_default()
                    font_sub = ImageFont.load_default()
                
                box_width = int(width * 0.85)
                box_height = 280
                x0 = (width - box_width) // 2
                y0 = height // 2 - 160
                x1 = x0 + box_width
                y1 = y0 + box_height
                draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=15, fill=(18, 18, 18, 200))
                
                sub_text = f"EPISODE {ep_num}" if clip_num == 1 else f"EPISODE {ep_num} • PART {clip_num}"
                title_text = title if title else f"Part {clip_num}"
                
                bbox_sub = draw.textbbox((0, 0), sub_text, font=font_sub)
                w_sub = bbox_sub[2] - bbox_sub[0]
                draw.text(((width - w_sub) // 2, y0 + 35), sub_text, font=font_sub, fill=(150, 150, 150, 255))
                
                def split_title(text):
                    if "\n" in text:
                        return [line.strip() for line in text.split("\n")]
                    if " : " in text:
                        return [p.strip() for p in text.split(" : ", 1)]
                    words = text.split()
                    if len(words) <= 1:
                        return [text]
                    best_diff = float('inf')
                    best_idx = 1
                    for i in range(1, len(words)):
                        part1 = " ".join(words[:i])
                        part2 = " ".join(words[i:])
                        diff = abs(len(part1) - len(part2))
                        if diff < best_diff:
                            best_diff = diff
                            best_idx = i
                    return [" ".join(words[:best_idx]), " ".join(words[best_idx:])]
                
                title_lines = split_title(title_text)
                
                line_spacing = 10
                line_heights = []
                total_title_h = 0
                for line in title_lines:
                    bbox_l = draw.textbbox((0, 0), line, font=font_title)
                    h_l = bbox_l[3] - bbox_l[1]
                    line_heights.append(h_l)
                    total_title_h += h_l
                total_title_h += line_spacing * (len(title_lines) - 1)
                
                box_content_h = y1 - y0 - 120
                start_y = y0 + 80 + (box_content_h - total_title_h) // 2
                if start_y < y0 + 80:
                    start_y = y0 + 80
                
                curr_y = start_y
                for idx, line in enumerate(title_lines):
                    bbox_line = draw.textbbox((0, 0), line, font=font_title)
                    w_line = bbox_line[2] - bbox_line[0]
                    draw.text(((width - w_line) // 2, curr_y), line, font=font_title, fill=(255, 255, 255, 255))
                    curr_y += line_heights[idx] + line_spacing
                
                line_y = y1 - 35
                line_w = 120
                draw.line([((width - line_w) // 2, line_y), ((width - line_w) // 2 + line_w, line_y)], fill=(80, 80, 80, 255), width=2)
                
                final_img = Image.alpha_composite(img, overlay).convert("RGB")
                temp_png = f"temp_intro_preview_{project_id}_{clip_num}.png"
                final_img.save(temp_png)
                
                if os.path.exists(temp_extracted):
                    try:
                        os.remove(temp_extracted)
                    except:
                        pass
                
                os.makedirs("previews", exist_ok=True)
                out_path = f"previews/intro_{project_id}_{clip_num}.mp4"
                
                music_file = None
                segments = clip.get("segments", [])
                if segments and isinstance(segments, list):
                    for seg in segments:
                        if seg.get("type") == "music" and seg.get("music_file"):
                            m_candidate = seg["music_file"].split('/').pop().split('\\').pop()
                            m_path = os.path.join("music", m_candidate)
                            if os.path.exists(m_path):
                                music_file = m_path
                                break
                            elif os.path.exists(seg["music_file"]):
                                music_file = seg["music_file"]
                                break
                
                if not music_file and clip.get("music"):
                    m_candidate = str(clip["music"]).split('/').pop().split('\\').pop()
                    m_path = os.path.join("music", m_candidate)
                    if os.path.exists(m_path):
                        music_file = m_path

                if not music_file or not os.path.exists(music_file):
                    fallback_music = [
                        "title-card-music.mp3",
                        os.path.join("music", "deepDive-soft-ok.mp3"),
                        os.path.join("music", "deepDive-strong.mp3"),
                        os.path.join("music", "deepDive-main.mp3")
                    ]
                    for cand in fallback_music:
                        if os.path.exists(cand):
                            music_file = cand
                            break
                cmd_ffmpeg = [
                    "ffmpeg", "-y",
                    "-loop", "1",
                    "-r", "30",
                    "-i", temp_png,
                    "-i", music_file,
                    "-c:v", "libx264",
                    "-tune", "stillimage",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-ar", "48000",
                    "-ac", "2",
                    "-pix_fmt", "yuv420p",
                    "-t", "2.0",
                    out_path
                ]
                res_ffmpeg = subprocess.run(cmd_ffmpeg, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                if os.path.exists(temp_png):
                    try:
                        os.remove(temp_png)
                    except:
                        pass
                        
                if res_ffmpeg.returncode != 0:
                    raise Exception(f"FFmpeg render failed: {res_ffmpeg.stderr.decode('utf-8')}")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "preview_url": f"/previews/intro_{project_id}_{clip_num}.mp4?t={int(time.time() * 1000)}"
                }).encode('utf-8'))
                return
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
                return

        elif parsed_url.path == '/get-clip-outro':
            project_id = params.get('id', [None])[0]
            clip_num = params.get('num', [None])[0]
            try:
                if not project_id or not clip_num:
                    raise Exception("Missing project id or clip number.")
                clip_num = int(clip_num)
                
                project_dir = os.path.join("projects", project_id)
                plan_path = os.path.join(project_dir, "plan.json")
                if not os.path.exists(plan_path):
                    plan_path = "plan.json"
                if not os.path.exists(plan_path):
                    raise Exception("plan.json not found.")
                
                with open(plan_path, "r", encoding="utf-8") as f:
                    plan_data = json.load(f)
                
                clip = None
                for c in plan_data:
                    if c["num"] == clip_num:
                        clip = c
                        break
                if not clip:
                    raise Exception(f"Clip {clip_num} not found in plan.")
                
                sorted_clips = sorted(plan_data, key=lambda x: x["num"])
                is_last_clip = (sorted_clips[-1]["num"] == clip_num)
                
                if is_last_clip:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": False, 
                        "error": "This is the last clip of the episode, so it does not have an outro transition card."
                    }).encode('utf-8'))
                    return
                
                bridge_text_input = clip.get("bridge_text", "")
                if isinstance(bridge_text_input, list):
                    bridge_text = " ".join(bridge_text_input)
                else:
                    bridge_text = str(bridge_text_input).strip()
                
                if not bridge_text:
                    bridge_text = "Next question is coming up..."
                
                os.makedirs("previews", exist_ok=True)
                temp_compiled_audio = f"previews/temp_compiled_audio_{project_id}_{clip_num}.mp3"
                
                info_path = os.path.join(project_dir, "project_info.json")
                with open(info_path, "r", encoding="utf-8") as inf_f:
                    info_data = json.load(inf_f)
                full_audio_path = os.path.join(project_dir, info_data["audio_filename"])
                
                segments = clip.get("segments")
                if not segments or not isinstance(segments, list):
                    segments = []
                    if clip.get("music"):
                        segments.append({
                            "type": "music",
                            "music_file": clip.get("music"),
                            "duration": 5.0,
                            "volume": clip.get("music_volume", 1.0),
                            "crossfade": 1.0
                        })
                    segments.append({
                        "type": "audio",
                        "start": clip.get("start", 0.0),
                        "end": clip.get("end", 0.0),
                        "duration": clip.get("end", 0.0) - clip.get("start", 0.0),
                        "volume": 1.0,
                        "crossfade": 0.0,
                        "text": clip.get("title", "")
                    })
                
                self.compile_segments(segments, temp_compiled_audio, full_audio_path)
                audio_source = temp_compiled_audio
                
                duration = 5.0
                try:
                    dur_cmd = [
                        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_source
                    ]
                    dur_res = subprocess.run(dur_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if dur_res.returncode == 0:
                        duration = float(dur_res.stdout.strip())
                except:
                    pass
                
                start_time = max(0.0, duration - 5.0)
                
                from PIL import Image, ImageDraw, ImageFont
                v_width, v_height = 740, 740
                
                img_outro = Image.new("RGB", (v_width, v_height), color=(0, 0, 0))
                draw_outro = ImageDraw.Draw(img_outro)
                
                font_path = "C:\\Windows\\Fonts\\segoeuib.ttf"
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, 34)
                else:
                    font = ImageFont.load_default()
                
                def wrap_text_outro(text, font_obj, max_w):
                    lines = []
                    for paragraph in text.split("\n"):
                        words = paragraph.split()
                        if not words:
                            lines.append("")
                            continue
                        curr = []
                        for word in words:
                            test_line = " ".join(curr + [word])
                            bbox = draw_outro.textbbox((0, 0), test_line, font=font_obj)
                            w = bbox[2] - bbox[0]
                            if w <= max_w:
                                curr.append(word)
                            else:
                                if curr:
                                    lines.append(" ".join(curr))
                                curr = [word]
                        if curr:
                            lines.append(" ".join(curr))
                    return lines
                
                lines = wrap_text_outro(bridge_text, font, v_width - 160)
                
                line_spacing = 18
                line_heights = []
                total_h = 0
                for line in lines:
                    bbox = draw_outro.textbbox((0, 0), line, font=font)
                    h = bbox[3] - bbox[1]
                    line_heights.append(h)
                    total_h += h
                total_h += line_spacing * (len(lines) - 1)
                
                curr_y = (v_height - total_h) // 2
                for idx, line in enumerate(lines):
                    bbox = draw_outro.textbbox((0, 0), line, font=font)
                    w = bbox[2] - bbox[0]
                    draw_outro.text(((v_width - w) // 2, curr_y), line, font=font, fill=(255, 255, 255))
                    curr_y += line_heights[idx] + line_spacing
                
                temp_png_outro = f"temp_outro_preview_{project_id}_{clip_num}.png"
                img_outro.save(temp_png_outro)
                
                os.makedirs("previews", exist_ok=True)
                out_path = f"previews/outro_{project_id}_{clip_num}.mp4"
                
                cmd_ffmpeg_outro = [
                    "ffmpeg", "-y",
                    "-loop", "1",
                    "-r", "30",
                    "-i", temp_png_outro,
                    "-ss", f"{start_time:.6f}",
                    "-i", audio_source,
                    "-map", "0:v",
                    "-map", "1:a",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-af", "afade=t=out:st=0:d=5.0",
                    "-c:a", "aac",
                    "-ar", "48000",
                    "-ac", "2",
                    "-t", "5.0",
                    out_path
                ]
                res_ffmpeg = subprocess.run(cmd_ffmpeg_outro, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                if os.path.exists(temp_png_outro):
                    try:
                        os.remove(temp_png_outro)
                    except:
                        pass
                
                temp_audio_gen = f"previews/temp_compiled_audio_{project_id}_{clip_num}.mp3"
                if os.path.exists(temp_audio_gen):
                    try:
                        os.remove(temp_audio_gen)
                    except:
                        pass
                
                if res_ffmpeg.returncode != 0:
                    raise Exception(f"FFmpeg render failed: {res_ffmpeg.stderr.decode('utf-8')}")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "preview_url": f"/previews/outro_{project_id}_{clip_num}.mp4?t={int(time.time() * 1000)}"
                }).encode('utf-8'))
                return
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
                return

        elif parsed_url.path == '/combine-project-video':
            project_id = params.get('id', [None])[0]
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                
                project_dir = os.path.join("projects", project_id)
                plan_path = os.path.join(project_dir, "plan.json")
                if not os.path.exists(plan_path):
                    raise Exception("plan.json not found.")
                
                # Extract number from project_id (e.g. "episode_244" -> "244")
                import re
                ep_num_match = re.search(r'\d+', project_id)
                if not ep_num_match:
                    raise Exception("Could not resolve episode number from project ID.")
                ep_num = ep_num_match.group(0)
                
                os.makedirs("previews", exist_ok=True)
                out_file = f"previews/combined_{project_id}.mp4"
                
                # Run the combine_clips_demuxer.py script
                cmd = [
                    sys.executable,
                    "scratch/combine_clips_demuxer.py",
                    "--episode", ep_num,
                    "--plan-file", plan_path,
                    "--out-file", out_file
                ]
                
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode != 0:
                    raise Exception(f"Combine clips script failed: {res.stderr or res.stdout}")
                
                response_data = {
                    "success": True,
                    "combined_url": f"/previews/combined_{project_id}.mp4?t={int(time.time() * 1000)}"
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
                self.send_error(500, f"Combine video error: {e}")
                return

        elif parsed_url.path == '/review-episode-bridges':
            project_id = params.get('id', [None])[0]
            content_length = int(self.headers.get('Content-Length', 0))
            custom_prompt = None
            if content_length > 0:
                try:
                    post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
                    custom_prompt = post_data.get('custom_prompt')
                except Exception:
                    pass

            try:
                if not project_id:
                    raise Exception("Missing project id.")
                
                project_dir = os.path.join("projects", project_id)
                plan_path = os.path.join(project_dir, "plan.json")
                if not os.path.exists(plan_path):
                    raise Exception("plan.json not found.")
                
                sys.path.insert(0, ".")
                from scratch.review_episode_bridges import review_episode_bridges
                success = review_episode_bridges(plan_path, custom_prompt=custom_prompt)
                if not success:
                    raise Exception("Gemini episode bridge review failed.")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": "Episode bridge cards successfully reviewed and updated by AI!"}).encode('utf-8'))
                return
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
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

        elif parsed_url.path == '/export-to-mosaic':
            project_id = params.get('id', [None])[0]
            clip_num = params.get('num', [None])[0]
            try:
                if not project_id or not clip_num:
                    raise Exception("Missing project id or clip number.")
                
                content_length = int(self.headers.get('Content-Length', 0))
                custom_instructions = ""
                custom_prompt = ""
                if content_length > 0:
                    body = self.rfile.read(content_length).decode('utf-8')
                    try:
                        post_data = json.loads(body)
                        custom_instructions = post_data.get('directive', '').strip()
                        custom_prompt = post_data.get('prompt', '').strip()
                    except Exception:
                        pass
                
                # Check settings
                settings_path = "settings.json"
                settings = {}
                if os.path.exists(settings_path):
                    with open(settings_path, "r", encoding="utf-8") as f:
                        settings = json.load(f)
                
                api_key = settings.get("mosaic_api_key")
                agent_id = settings.get("mosaic_agent_id")
                if not api_key or not agent_id:
                    raise Exception("Mosaic API Key and Agent ID must be configured in System Settings first.")
                
                # Retrieve clip text and title from project plan.json
                project_dir = os.path.join("projects", project_id)
                
                info_path = os.path.join(project_dir, "project_info.json")
                if not os.path.exists(info_path):
                    raise Exception(f"project_info.json for project {project_id} not found.")
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                    
                plan_path = os.path.join(project_dir, "plan.json")
                if not os.path.exists(plan_path):
                    raise Exception(f"plan.json for project {project_id} not found.")
                
                with open(plan_path, "r", encoding="utf-8") as f:
                    plan = json.load(f)
                
                # Find matching clip
                target_clip = None
                for clip in plan:
                    if int(clip.get("num", -1)) == int(clip_num):
                        target_clip = clip
                        break
                
                if not target_clip:
                    raise Exception(f"Clip number {clip_num} not found in plan.")
                
                # Concatenate segment texts to get complete script
                speech_texts = []
                for seg in target_clip.get("segments", []):
                    if seg.get("type") == "audio" and seg.get("text"):
                        speech_texts.append(seg.get("text").strip())
                transcript = " ".join(speech_texts)
                
                # Generate custom prompt with user's baseline guidelines
                title = target_clip.get("title", f"Clip {clip_num}")
                mogr_base_rules = get_mosaic_default_prompt()
                
                if custom_prompt:
                    prompt_content = custom_prompt
                else:
                    # Append clip context to base guidelines
                    prompt_content = f"{mogr_base_rules}\n\n--------------------------------------------------\nDYNAMIC CLIP CONTEXT\n--------------------------------------------------\n- Animate visuals to explain this Clip Title: {title}"
                    if transcript:
                        prompt_content += f"\n- Spoken Transcript Text: {transcript}"
                    if custom_instructions:
                        prompt_content += f"\n- SPECIAL MOTION GRAPHICS INSTRUCTIONS: {custom_instructions}"
                    
                    if len(prompt_content) > 1200:
                        prompt_content = prompt_content[:1197] + "..."
                
                # Check if already running
                job_key = (project_id, int(clip_num))
                if job_key in mosaic_runs and mosaic_runs[job_key].get("status") in ("starting", "requesting upload URL", "uploading media", "finalizing upload", "triggering run", "running", "downloading output"):
                    raise Exception("An export is already in progress for this clip.")
                
                # Check for existing run ID in plan.json (cache/resume support)
                force_param = params.get('force', ['false'])[0].lower() == 'true'
                existing_run_id = target_clip.get("mosaic_run_id")
                
                if existing_run_id and not force_param:
                    base_url = "https://api.mosaic.so"
                    headers = {"Authorization": f"Bearer {api_key}"}
                    try:
                        res_status = requests.get(f"{base_url}/agent_run/{existing_run_id}", headers=headers)
                        if res_status.status_code == 200:
                            run_info = res_status.json()
                            status = run_info.get("status")
                            print(f"[{project_id}][Clip {clip_num}] Found existing run {existing_run_id} on Mosaic. API Status: {status}")
                            
                            if status == "completed":
                                # Resume completed run to download video
                                audio_path = os.path.join(project_dir, info["audio_filename"])
                                segments = target_clip.get("segments", [])
                                t = threading.Thread(
                                    target=run_mosaic_pipeline,
                                    args=(project_id, int(clip_num), settings, prompt_content, segments, audio_path, existing_run_id),
                                    daemon=True
                                )
                                t.start()
                                
                                self.send_response(200)
                                self.send_header('Content-type', 'application/json')
                                self.send_header('Access-Control-Allow-Origin', '*')
                                self.end_headers()
                                self.wfile.write(json.dumps({"success": True, "message": "Resuming completed run to download video."}).encode('utf-8'))
                                return
                            elif status in ("running", "starting"):
                                # Resume active run polling
                                audio_path = os.path.join(project_dir, info["audio_filename"])
                                segments = target_clip.get("segments", [])
                                t = threading.Thread(
                                    target=run_mosaic_pipeline,
                                    args=(project_id, int(clip_num), settings, prompt_content, segments, audio_path, existing_run_id),
                                    daemon=True
                                )
                                t.start()
                                
                                self.send_response(200)
                                self.send_header('Content-type', 'application/json')
                                self.send_header('Access-Control-Allow-Origin', '*')
                                self.end_headers()
                                self.wfile.write(json.dumps({"success": True, "message": "Resuming active run polling."}).encode('utf-8'))
                                return
                            else:
                                print(f"[{project_id}][Clip {clip_num}] Existing run {existing_run_id} has failed or cancelled. Clearing to start fresh.")
                        else:
                            print(f"[{project_id}][Clip {clip_num}] Existing run {existing_run_id} not found on Mosaic API. Clearing to start fresh.")
                    except Exception as poll_ex:
                        print(f"[{project_id}][Clip {clip_num}] Warning: Failed to query existing run status: {poll_ex}")
                
                # If force rerun, or if the existing run has failed/is missing, clear it in plan.json
                if existing_run_id:
                    try:
                        for c in plan:
                            if int(c.get("num", -1)) == int(clip_num):
                                if "mosaic_run_id" in c:
                                    del c["mosaic_run_id"]
                                break
                        with open(plan_path, "w", encoding="utf-8") as f:
                            json.dump(plan, f, indent=4)
                        print(f"[{project_id}][Clip {clip_num}] Cleared previous mosaic_run_id from plan.json")
                    except Exception as clear_ex:
                        print(f"Warning: Failed to clear mosaic_run_id: {clear_ex}")

                # Load segments and audio source path for automatic draft video generation if needed
                audio_path = os.path.join(project_dir, info["audio_filename"])
                segments = target_clip.get("segments", [])

                # Kick off new thread
                t = threading.Thread(
                    target=run_mosaic_pipeline,
                    args=(project_id, int(clip_num), settings, prompt_content, segments, audio_path),
                    daemon=True
                )
                t.start()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": "Mosaic run started."}).encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                return

        elif parsed_url.path == '/compile-clip':
            project_id = params.get('id', [None])[0]
            clip_num = params.get('num', [None])[0]
            is_draft = params.get('draft', ['false'])[0].lower() in ('true', '1')
            try:
                if not project_id or not clip_num:
                    raise Exception("Missing project id or clip number.")
                
                plan_path = os.path.join("projects", project_id, "plan.json")
                if not os.path.exists(plan_path):
                    plan_path = "plan.json"

                # 1. First re-slice fresh audio from plan.json for this clip to capture any recent user edits
                info_path = os.path.join("projects", project_id, "project_info.json")
                audio_file = None
                if os.path.exists(info_path):
                    with open(info_path, "r", encoding="utf-8") as f_info:
                        p_info = json.load(f_info)
                        audio_file = p_info.get("audio_file") or p_info.get("audio_filename")
                if audio_file and not os.path.exists(audio_file):
                    audio_file = os.path.join("projects", project_id, audio_file)
                if not audio_file or not os.path.exists(audio_file):
                    ep_num = project_id.replace('episode_', '')
                    for candidate_ext in [f"{ep_num}.m4a", f"{ep_num}.mp3", f"episode_{ep_num}.m4a", f"episode_{ep_num}.mp3"]:
                        candidate_path = os.path.join("projects", project_id, candidate_ext)
                        if os.path.exists(candidate_path):
                            audio_file = candidate_path
                            break

                if audio_file and os.path.exists(audio_file):
                    cut_cmd = [sys.executable, "ddma.py", "cut", "--audio", audio_file, "--plan-file", plan_path, "--out-dir", "clips"]
                    print(f"[{project_id}][Clip {clip_num}] Re-slicing fresh audio for Clip {clip_num}: {' '.join(cut_cmd)}")
                    res_cut = subprocess.run(cut_cmd, capture_output=True, text=True, cwd=".")
                    if res_cut.returncode != 0:
                        print(f"[{project_id}][Clip {clip_num}] Warning: Audio re-slicing emitted stderr: {res_cut.stderr}")

                # 2. Synchronously compile intro card, equalized master body, and outro curiosity card
                cmd = [sys.executable, "ddma.py", "compile-clip", "--num", str(clip_num), "--plan-file", plan_path]
                if is_draft:
                    cmd.append("--force-draft")
                print(f"[{project_id}][Clip {clip_num}] Starting synchronous compilation: {' '.join(cmd)}")
                proc = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
                if proc.returncode != 0:
                    raise Exception(f"Compile-clip failed with return code {proc.returncode}: {proc.stderr}")
                print(f"[{project_id}][Clip {clip_num}] Synchronous compilation completed successfully!")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": "Compilation completed successfully."}).encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
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
            
        elif parsed_url.path == '/get-project-audio':
            project_id = params.get('id', [None])[0]
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                project_dir = os.path.join("projects", project_id)
                info_path = os.path.join(project_dir, "project_info.json")
                if not os.path.exists(info_path):
                    raise Exception(f"Project info for {project_id} not found.")
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                audio_file_name = info.get("audio_filename") or info.get("audio_file")
                audio_path = os.path.join(project_dir, audio_file_name) if audio_file_name else None
                if not audio_path or not os.path.exists(audio_path):
                    ep_num = project_id.replace("episode_", "")
                    for ext in [".m4a", ".mp3", ".wav"]:
                        cand = os.path.join(project_dir, f"{ep_num}{ext}")
                        if os.path.exists(cand):
                            audio_path = cand
                            break
                if not audio_path or not os.path.exists(audio_path):
                    self.send_error(404, f"Audio file for project {project_id} not found.")
                    return
                
                # Delegate to super().do_GET() with path set to static audio file
                # This automatically provides full HTTP 206 Range request support for seeking!
                self.path = "/" + audio_path.replace("\\", "/")
                return super().do_GET()
            except Exception as e:
                self.send_error(500, f"Error getting project audio: {e}")
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
            
        elif parsed_url.path == '/get-mosaic-prompt':
            project_id = params.get('id', [None])[0]
            clip_num = params.get('num', [None])[0]
            try:
                if not project_id or not clip_num:
                    raise Exception("Missing project id or clip number.")
                
                project_dir = os.path.join("projects", project_id)
                plan_path = os.path.join(project_dir, "plan.json")
                if not os.path.exists(plan_path):
                    raise Exception(f"plan.json for project {project_id} not found.")
                
                with open(plan_path, "r", encoding="utf-8") as f:
                    plan = json.load(f)
                
                target_clip = None
                for clip in plan:
                    if int(clip.get("num", -1)) == int(clip_num):
                        target_clip = clip
                        break
                
                if not target_clip:
                    raise Exception(f"Clip number {clip_num} not found in plan.")
                
                speech_texts = []
                for seg in target_clip.get("segments", []):
                    if seg.get("type") == "audio" and seg.get("text"):
                        speech_texts.append(seg.get("text").strip())
                transcript = " ".join(speech_texts)
                
                title = target_clip.get("title", f"Clip {clip_num}")
                mogr_base_rules = get_mosaic_default_prompt()
                
                prompt_content = f"{mogr_base_rules}\n\n--------------------------------------------------\nDYNAMIC CLIP CONTEXT\n--------------------------------------------------\n- Animate visuals to explain this Clip Title: {title}"
                if transcript:
                    prompt_content += f"\n- Spoken Transcript Text: {transcript}"
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "prompt": prompt_content}).encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
                return

        elif parsed_url.path == '/get-bridge-review-prompt':
            project_id = params.get('id', [None])[0]
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                project_dir = os.path.join("projects", project_id)
                plan_path = os.path.join(project_dir, "plan.json")
                if not os.path.exists(plan_path):
                    raise Exception("plan.json not found.")
                
                sys.path.insert(0, ".")
                from scratch.review_episode_bridges import build_bridge_review_prompt
                prompt_content = build_bridge_review_prompt(plan_path)
                if not prompt_content:
                    raise Exception("Could not build episode bridge review prompt.")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "prompt": prompt_content}).encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
                return
            
        elif parsed_url.path == '/get-gemini-prompt':
            project_id = params.get('id', [None])[0]
            clip_num = params.get('num', [None])[0]
            try:
                if not project_id or not clip_num:
                    raise Exception("Missing project id or clip number.")
                
                prompt_content = build_gemini_prompt(project_id, int(clip_num))
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "prompt": prompt_content}).encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
                return

        elif parsed_url.path == '/get-episode-gemini-prompt':
            project_id = params.get('id', [None])[0]
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                
                prompt_template = get_gemini_episode_default_prompt()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "prompt": prompt_template}).encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
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
                    with open(plan_path, "r", encoding="utf-8-sig") as f:
                        plan_data = json.load(f)
                    try:
                        shutil.copy2(plan_path, "plan.json")
                        if os.path.exists("docs"):
                            shutil.copy2("plan.json", os.path.join("docs", "plan.json"))
                    except Exception as copy_err:
                        print(f"Error syncing project plan to root/docs: {copy_err}")
                        
                trans_data = None
                if os.path.exists(trans_path):
                    with open(trans_path, "r", encoding="utf-8") as f:
                        trans_data = json.load(f)
                
                has_snapshot = os.path.exists(os.path.join(project_dir, "plan_snapshot.json"))
                
                # Scan for compiled videos matching this project (e.g. episode 244 -> "244-*.mp4")
                compiled_videos_dict = {}
                import re
                ep_num_match = re.search(r'\d+', project_id)

                # Self-healing & Auto-Resume check: ensure clips with mosaic_run_id are being polled / downloaded
                plan_modified = False
                if ep_num_match and plan_data:
                    ep_num = ep_num_match.group(0)
                    for clip in plan_data:
                        if "mosaic_run_id" in clip:
                            c_num = clip.get("num")
                            run_id = clip["mosaic_run_id"]
                            orig_file = os.path.join("clips", f"{ep_num}-{c_num}-original.mp4")
                            main_file = os.path.join("clips", f"{ep_num}-{c_num}.mp4")
                            job_key = (project_id, int(c_num))
                            if not os.path.exists(orig_file) and not os.path.exists(main_file):
                                if job_key not in mosaic_runs or mosaic_runs[job_key].get("status") == "failed":
                                    print(f"[{project_id}][Clip {c_num}] Auto-resuming Mosaic polling thread for run_id {run_id}...")
                                    st_data = load_settings()
                                    t = threading.Thread(
                                        target=run_mosaic_pipeline,
                                        args=(project_id, c_num, st_data, "", clip.get("segments", []), os.path.join("audio", f"{ep_num}.mp3"), run_id),
                                        daemon=True
                                    )
                                    t.start()
                    if plan_modified:
                        try:
                            with open(plan_path, "w", encoding="utf-8") as f:
                                json.dump(plan_data, f, indent=4)
                        except Exception as w_err:
                            print(f"Error saving self-healed plan.json: {w_err}")
                if ep_num_match:
                    ep_num = ep_num_match.group(0)
                    clips_dir = "clips"
                    if os.path.exists(clips_dir):
                        # Sort files so that named files (e.g., 244-1-Title.mp4) are processed first,
                        # and direct standard files (e.g., 244-1.mp4) are processed last, overwriting/prioritizing them.
                        for file in sorted(os.listdir(clips_dir)):
                            if file.startswith(f"{ep_num}-") and file.endswith(".mp4") and not file.endswith("-original.mp4"):
                                try:
                                    parts = file.split("-")
                                    if len(parts) >= 2:
                                        clip_num_str = parts[1]
                                        if "." in clip_num_str:
                                            clip_num_str = clip_num_str.split(".")[0]
                                        clip_num = int(clip_num_str)
                                        
                                        # Prioritize the direct standard filename (e.g. 244-2.mp4) over named templates (e.g. 244-2-Title.mp4)
                                        is_direct = (len(parts) == 2 or (len(parts) == 3 and parts[2] == ""))
                                        if is_direct or clip_num not in compiled_videos_dict:
                                            compiled_videos_dict[clip_num] = {
                                                "num": clip_num,
                                                "filename": file,
                                                "url": f"/clips/{file}"
                                            }
                                except Exception:
                                    pass
                compiled_videos = list(compiled_videos_dict.values())
                
                # Scan for status indicators for all clip numbers
                clip_statuses = {}
                if ep_num_match and os.path.exists(clips_dir):
                    ep_num = ep_num_match.group(0)
                    for file in os.listdir(clips_dir):
                        if file.startswith(f"{ep_num}-"):
                            try:
                                parts = file.split("-")
                                if len(parts) >= 2:
                                    clip_num_str = parts[1]
                                    if "." in clip_num_str:
                                        clip_num_str = clip_num_str.split(".")[0]
                                    clip_num = int(clip_num_str)
                                    
                                    if clip_num not in clip_statuses:
                                        clip_statuses[clip_num] = {"has_audio": False, "video_state": "none", "has_mosaic_file": False}
                                    
                                    if file.endswith(".mp3"):
                                        clip_statuses[clip_num]["has_audio"] = True
                                    elif file.endswith("-original.mp4"):
                                        clip_statuses[clip_num]["video_state"] = "compiled"
                                        clip_statuses[clip_num]["has_mosaic_file"] = True
                                    elif file.endswith(".mp4"):
                                        if clip_statuses[clip_num].get("video_state") != "compiled":
                                            clip_statuses[clip_num]["video_state"] = "draft"
                            except Exception:
                                pass
                                
                    if isinstance(plan_data, list):
                        for c in plan_data:
                            c_num = c.get("num")
                            if c_num and c.get("mosaic_run_id"):
                                mp4_file = os.path.join(clips_dir, f"{ep_num}-{c_num}.mp4")
                                if os.path.exists(mp4_file):
                                    if c_num not in clip_statuses:
                                        clip_statuses[c_num] = {"has_audio": False, "video_state": "compiled", "has_mosaic_file": True}
                                    else:
                                        clip_statuses[c_num]["video_state"] = "compiled"
                                        clip_statuses[c_num]["has_mosaic_file"] = True

                    # Purge stale/auto_compile jobs from mosaic_runs (4 hours / 14400s max)
                    now = time.time()
                    stale_keys = [
                        k for k, v in list(mosaic_runs.items()) 
                        if v.get("run_id") == "auto_compile" or not v.get("start_time") or (now - v.get("start_time", 0) > 14400)
                    ]
                    for k in stale_keys:
                        del mosaic_runs[k]

                    # Scan active background jobs in mosaic_runs to override status to 'processing'
                    for job_key, job in mosaic_runs.items():
                        if job_key[0] == project_id:
                            job_clip_num = job_key[1]
                            job_status = job.get("status")
                            if job_status in ("starting", "compiling draft video", "requesting upload URL", "uploading media", "finalizing upload", "triggering run", "running", "downloading output", "compiling intro card", "processing", "compiling"):
                                if job_clip_num not in clip_statuses:
                                    clip_statuses[job_clip_num] = {"has_audio": False, "video_state": "none"}
                                if not clip_statuses[job_clip_num].get("has_mosaic_file"):
                                    clip_statuses[job_clip_num]["video_state"] = "processing"
                                    clip_statuses[job_clip_num]["progress"] = job.get("progress", 0)
                                    clip_statuses[job_clip_num]["status"] = job_status
                                
                ingestion_progress = None
                progress_file = os.path.join(project_dir, "ingestion_progress.json")
                if os.path.exists(progress_file):
                    try:
                        with open(progress_file, "r", encoding="utf-8") as pf:
                            ingestion_progress = json.load(pf)
                    except Exception:
                        pass

                payload = {
                    "info": info,
                    "plan": plan_data,
                    "transcription": trans_data,
                    "has_snapshot": has_snapshot,
                    "compiled_videos": compiled_videos,
                    "clip_statuses": clip_statuses,
                    "ingestion_progress": ingestion_progress
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

        elif parsed_url.path == '/get-ingestion-progress':
            project_id = params.get('id', [None])[0]
            try:
                if not project_id:
                    raise Exception("Missing project id.")
                project_dir = os.path.join("projects", project_id)
                progress_file = os.path.join(project_dir, "ingestion_progress.json")
                data = {"status": "none", "percent": 0}
                if os.path.exists(progress_file):
                    with open(progress_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode('utf-8'))
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
                
        elif parsed_url.path == '/get-mosaic-status':
            project_id = params.get('id', [None])[0]
            clip_num = params.get('num', [None])[0]
            try:
                if not project_id or not clip_num:
                    raise Exception("Missing project id or clip number.")
                
                job_key = (project_id, int(clip_num))
                job = mosaic_runs.get(job_key)
                
                if not job:
                    # Self-healing check: check if a run was already registered in plan.json
                    project_dir = os.path.join("projects", project_id)
                    plan_path = os.path.join(project_dir, "plan.json")
                    mosaic_run_id = None
                    target_clip = None
                    if os.path.exists(plan_path):
                        try:
                            with open(plan_path, "r", encoding="utf-8") as f:
                                plan = json.load(f)
                            for c in plan:
                                if int(c.get("num", -1)) == int(clip_num):
                                    mosaic_run_id = c.get("mosaic_run_id")
                                    target_clip = c
                                    break
                        except Exception as pe:
                            print(f"Warning: Failed to parse plan.json for run recovery: {pe}")
                    
                    if mosaic_run_id:
                        print(f"[{project_id}][Clip {clip_num}] Found persisted mosaic_run_id {mosaic_run_id}. Restoring pipeline run...")
                        
                        # Load settings
                        settings_path = "settings.json"
                        settings = {}
                        if os.path.exists(settings_path):
                            with open(settings_path, "r", encoding="utf-8") as f:
                                settings = json.load(f)
                        
                        # Load project info for audio
                        info_path = os.path.join(project_dir, "project_info.json")
                        info = {}
                        if os.path.exists(info_path):
                            with open(info_path, "r", encoding="utf-8") as f:
                                info = json.load(f)
                        
                        audio_path = os.path.join(project_dir, info.get("audio_filename", ""))
                        segments = target_clip.get("segments", [])
                        
                        # Construct prompt
                        title = target_clip.get("title", f"Clip {clip_num}")
                        speech_texts = []
                        for seg in segments:
                            if seg.get("type") == "audio" and seg.get("text"):
                                speech_texts.append(seg.get("text").strip())
                        transcript = " ".join(speech_texts)
                        
                        mogr_base_rules = get_mosaic_default_prompt()
                        prompt_content = f"{mogr_base_rules}\n\n--------------------------------------------------\nDYNAMIC CLIP CONTEXT\n--------------------------------------------------\n- Animate visuals to explain this Clip Title: {title}"
                        if transcript:
                            prompt_content += f"\n- Spoken Transcript Text: {transcript}"
                        if len(prompt_content) > 1200:
                            prompt_content = prompt_content[:1197] + "..."
                        
                        # Spawn background thread to resume polling/download
                        t = threading.Thread(
                            target=run_mosaic_pipeline,
                            args=(project_id, int(clip_num), settings, prompt_content, segments, audio_path, mosaic_run_id),
                            daemon=True
                        )
                        t.start()
                        
                        job = {"status": "running", "progress": 70, "error": None, "run_id": mosaic_run_id}
                        mosaic_runs[job_key] = job
                    else:
                        job = {"status": "idle", "progress": 0, "error": None}
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(job).encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
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

    def end_headers(self):
        if self.path.endswith('.html') or self.path.endswith('.js') or 'curator' in self.path:
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def translate_path(self, path):
        translated = super().translate_path(path)
        clean_path = path.split('?')[0]
        if not os.path.exists(translated) and "/clips/" in clean_path:
            # Fallback 1: Strip 'episode_' prefix (e.g. /clips/episode_245-1.mp4 -> /clips/245-1.mp4)
            if "/clips/episode_" in clean_path:
                alt_clean = clean_path.replace("/clips/episode_", "/clips/")
                alt_trans = super().translate_path(alt_clean)
                if os.path.exists(alt_trans):
                    return alt_trans
            # Fallback 2: Check for any matching file in clips directory (e.g. 245-1-Title.mp4)
            clips_dir = "clips"
            if os.path.exists(clips_dir):
                base_name = os.path.basename(clean_path)
                import re
                ep_match = re.search(r'(\d+)-(\d+)', base_name)
                if ep_match:
                    ep_n = ep_match.group(1)
                    c_n = ep_match.group(2)
                    for f in os.listdir(clips_dir):
                        if f.startswith(f"{ep_n}-{c_n}.") or f.startswith(f"{ep_n}-{c_n}-"):
                            if f.endswith(".mp4") and not f.endswith("-original.mp4"):
                                return os.path.join(os.getcwd(), clips_dir, f)
        return translated

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

        clean_path = self.path.split('?')[0]
        size = os.path.getsize(self.translate_path(clean_path))
        start = int(match.group(1))
        end = match.group(2)
        end = int(end) if end else size - 1

        length = end - start + 1
        buffer_size = 256 * 1024
        while length > 0:
            chunk = source.read(min(buffer_size, length))
            if not chunk:
                break
            outputfile.write(chunk)
            length -= len(chunk)

    def log_message(self, format, *args):
        pass

def start_server():
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    try:
        with socketserver.ThreadingTCPServer(("", PORT), RangeHTTPRequestHandler) as httpd:
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

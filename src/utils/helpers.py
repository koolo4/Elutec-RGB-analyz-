import os
import cv2
import numpy as np
import time
import socket
import subprocess
import threading
import re

from ..config import LOW_LATENCY_FFMPEG_OPTIONS, get_default_save_folder
from .ffmpeg_utils import find_ffmpeg_exe, ffmpeg_missing_message

                                                                 
VIDEO_FILE_EXTENSIONS = {
    ".mp4", ".avi", ".mkv", ".mov", ".m4v", ".wmv", ".webm", ".mpeg", ".mpg"
}


def is_video_file_path(source):
    """Проверяет расширение файла (даже если файл ещё не создан или перемещён)."""
    if not source:
        return False
    try:
        clean = str(source).strip().strip('"').strip("'")
        if not clean:
            return False
        return os.path.splitext(clean)[1].lower() in VIDEO_FILE_EXTENSIONS
    except Exception:
        return False


def is_video_file_source(source):
    """Проверяет, что путь ведёт к существующему видеофайлу."""
    if not source:
        return False
    try:
        clean = str(source).strip().strip('"').strip("'")
        if not clean:
            return False
        value = os.path.abspath(os.path.expanduser(clean))
        return os.path.isfile(value) and os.path.splitext(value)[1].lower() in VIDEO_FILE_EXTENSIONS
    except Exception:
        return False


def is_network_source(source):
    if not source:
        return False
    source_str = str(source).strip().strip('"').strip("'").lower()
    return source_str.startswith(("rtsp://", "http://", "https://"))


def is_rtsp_source(source):
    if not source:
        return False
    return str(source).strip().strip('"').strip("'").lower().startswith("rtsp://")

def apply_low_latency_ffmpeg_options():
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = LOW_LATENCY_FFMPEG_OPTIONS


def get_short_path_name(path):
    """
    Возвращает короткий 8.3 путь Windows для надёжного открытия
    файлов с кириллицей, пробелами и спецсимволами в OpenCV.
    """
    if not path or not os.path.exists(path):
        return path
    if os.name == 'nt':
        try:
            import ctypes
            from ctypes import wintypes
            _GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
            _GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
            _GetShortPathNameW.restype = wintypes.DWORD

            buf = ctypes.create_unicode_buffer(260)
            res = _GetShortPathNameW(str(path), buf, 260)
            if res > 260:
                buf = ctypes.create_unicode_buffer(res)
                res = _GetShortPathNameW(str(path), buf, res)
            if res > 0 and buf.value:
                return buf.value
        except Exception:
            pass
    return path


def verify_capture_can_read(cap):
    """Проверяет, что capture объект действительно открыт и может декодировать кадры."""
    if cap is None or not cap.isOpened():
        return False
    try:
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            try:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            except Exception:
                pass
            return True
    except Exception:
        pass
    return False


def repair_video_file_if_needed(file_path):
    """
    Автоматическое восстановление повреждённого MP4/MOV видеофайла
    (включая ошибку 'moov atom not found', возникающую при аварийной остановке записи).
    Пробует FFmpeg remuxing, прямое извлечение NAL/H.264/MPEG4 потока из mdat-атома
    и упаковку в MKV.
    """
    try:
        if not file_path:
            return None
        raw_str = str(file_path).strip().strip('"').strip("'")
        norm_path = os.path.normpath(os.path.abspath(os.path.expanduser(raw_str)))
        if not os.path.isfile(norm_path) or os.path.getsize(norm_path) < 64:
            return None

        base, ext = os.path.splitext(norm_path)
        repaired_path = f"{base}_repaired.mkv"
        recovered_h264 = f"{base}_recovered.h264"
        recovered_m4v = f"{base}_recovered.m4v"

        if os.path.isfile(repaired_path) and os.path.getsize(repaired_path) > 1024:
            return repaired_path

        ffmpeg_exe = find_ffmpeg_exe()
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

        # 1. Попытка FFmpeg прямого ремукса с игнорированием ошибок
        if ffmpeg_exe:
            try:
                cmd1 = [
                    ffmpeg_exe, '-y', '-hide_banner', '-loglevel', 'error',
                    '-err_detect', 'ignore_err',
                    '-i', norm_path,
                    '-c', 'copy',
                    repaired_path
                ]
                subprocess.run(cmd1, capture_output=True, timeout=12, creationflags=flags)
                if os.path.isfile(repaired_path) and os.path.getsize(repaired_path) > 1024:
                    print(f"🔧 Видеофайл успешно восстановлен через FFmpeg remux: {repaired_path}")
                    return repaired_path
            except Exception:
                pass

        # 2. Попытка извлечения сырого mdat-потока (H.264 / MPEG4)
        try:
            with open(norm_path, 'rb') as f_in:
                data = f_in.read()

            mdat_idx = data.find(b'mdat')
            if mdat_idx != -1:
                stream_start = mdat_idx + 4
                raw_payload = data[stream_start:]
                if len(raw_payload) > 1024:
                    # Поиск H.264 start codes (00 00 00 01 или 00 00 01)
                    if b'\x00\x00\x00\x01' in raw_payload or b'\x00\x00\x01' in raw_payload:
                        with open(recovered_h264, 'wb') as f_out:
                            f_out.write(raw_payload)
                        if os.path.isfile(recovered_h264) and os.path.getsize(recovered_h264) > 1024:
                            if ffmpeg_exe:
                                cmd_h264 = [
                                    ffmpeg_exe, '-y', '-hide_banner', '-loglevel', 'error',
                                    '-f', 'h264', '-i', recovered_h264,
                                    '-c', 'copy', repaired_path
                                ]
                                subprocess.run(cmd_h264, capture_output=True, timeout=12, creationflags=flags)
                                if os.path.isfile(repaired_path) and os.path.getsize(repaired_path) > 1024:
                                    print(f"🔧 H.264 поток упакован в MKV: {repaired_path}")
                                    try:
                                        os.remove(recovered_h264)
                                    except Exception:
                                        pass
                                    return repaired_path
                    else:
                        with open(recovered_m4v, 'wb') as f_out:
                            f_out.write(raw_payload)
                        if os.path.isfile(recovered_m4v) and os.path.getsize(recovered_m4v) > 1024:
                            if ffmpeg_exe:
                                cmd_m4v = [
                                    ffmpeg_exe, '-y', '-hide_banner', '-loglevel', 'error',
                                    '-f', 'm4v', '-i', recovered_m4v,
                                    '-c', 'copy', repaired_path
                                ]
                                subprocess.run(cmd_m4v, capture_output=True, timeout=12, creationflags=flags)
                                if os.path.isfile(repaired_path) and os.path.getsize(repaired_path) > 1024:
                                    print(f"🔧 MPEG-4 поток упакован в MKV: {repaired_path}")
                                    try:
                                        os.remove(recovered_m4v)
                                    except Exception:
                                        pass
                                    return repaired_path
        except Exception:
            pass

    except Exception:
        pass
    return None


def open_video_file_capture(file_path):
    """
    Надёжное открытие видеофайла с автоматическим преобразованием в 8.3 путь (для кириллицы),
    перебором бэкендов OpenCV (CAP_ANY, CAP_MSMF, CAP_FFMPEG, CAP_DSHOW), прямым чтением через
    FFmpeg pipe (FFMpegFileCapture) и авто-восстановлением через FFmpeg.
    """
    if not file_path:
        return None
    raw_str = str(file_path).strip().strip('"').strip("'")
    norm_path = os.path.normpath(os.path.abspath(os.path.expanduser(raw_str)))
    if not os.path.isfile(norm_path):
        return None

    short_path = get_short_path_name(norm_path)
    path_candidates = [norm_path]
    if short_path and short_path != norm_path and os.path.isfile(short_path):
        path_candidates.insert(0, short_path)

    backends = []
    if hasattr(cv2, 'CAP_FFMPEG'):
        backends.append(cv2.CAP_FFMPEG)
    if hasattr(cv2, 'CAP_MSMF'):
        backends.append(cv2.CAP_MSMF)
    if hasattr(cv2, 'CAP_ANY'):
        backends.append(cv2.CAP_ANY)
    if not backends:
        backends.append(None)

    # 1. Пробуем открыть файл перебором путей и бэкендов OpenCV
    for p in path_candidates:
        for backend in backends:
            try:
                cap = cv2.VideoCapture(p, backend) if backend is not None else cv2.VideoCapture(p)
                if verify_capture_can_read(cap):
                    return cap
                if cap is not None:
                    cap.release()
            except Exception:
                pass

    # 2. Если файл повреждён (например, moov atom not found), пробуем восстановить через FFmpeg / mdat
    repaired = repair_video_file_if_needed(norm_path)
    if repaired and os.path.isfile(repaired):
        rep_short = get_short_path_name(repaired)
        rep_paths = [rep_short, repaired] if (rep_short and rep_short != repaired) else [repaired]
        for p in rep_paths:
            for backend in backends:
                try:
                    cap = cv2.VideoCapture(p, backend) if backend is not None else cv2.VideoCapture(p)
                    if verify_capture_can_read(cap):
                        return cap
                    if cap is not None:
                        cap.release()
                except Exception:
                    pass
            try:
                from ..analysis.ffmpeg_capture import FFMpegFileCapture
                cap = FFMpegFileCapture(p)
                if verify_capture_can_read(cap):
                    return cap
                if cap is not None:
                    cap.release()
            except Exception:
                pass

    # 3. Пробуем прямое чтение через внешний ffmpeg (FFMpegFileCapture)
    try:
        from ..analysis.ffmpeg_capture import FFMpegFileCapture
        for p in path_candidates:
            cap = FFMpegFileCapture(p)
            if verify_capture_can_read(cap):
                return cap
            if cap is not None:
                cap.release()
    except Exception:
        pass

    return None


def is_miicam_source(source):
    s = str(source).strip().lower()
    return s.startswith("miicam") or s.startswith("rgb_detector") or s == "detector"


def scan_miicam_cameras():
    """Сканирует подключенные научные USB/CMOS RGB-детекторы MiiCam / ToupCam."""
    try:
        from .miicam_wrapper import is_miicam_available, enumerate_miicam_devices
        if not is_miicam_available():
            return []
        devs = enumerate_miicam_devices()
        results = []
        for d in devs:
            src = d.get('source', f"miicam:{d.get('index', 0)}")
            label = f"💡 RGB-детектор MiiCam: {d.get('displayname', 'Sensor')} ({d.get('width', 1920)}x{d.get('height', 1080)})"
            results.append((src, label))
        return results
    except Exception as e:
        print(f"⚠️ Ошибка сканирования MiiCam: {e}")
        return []


def open_camera_device(index, width=None, height=None, max_attempts=15):
    """
    Надёжно открывает камеру по индексу с перебором бэкендов DirectShow -> MSMF -> ANY,
    прогревом DirectShow-графа и верификацией реального поступления кадров.
    """
    if is_miicam_source(index):
        try:
            from .miicam_wrapper import MiiCamCapture
            cap = MiiCamCapture(index, width=width, height=height)
            if cap.isOpened():
                for _ in range(max_attempts):
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.size > 0:
                        return cap, frame, "MIICAM"
                    time.sleep(0.04)
                try:
                    cap.release()
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️ Ошибка open_camera_device (MiiCam): {e}")
        return None, None, "FAILED"

    backend_candidates = []
    if hasattr(cv2, 'CAP_DSHOW'):
        backend_candidates.append((cv2.CAP_DSHOW, "DSHOW"))
    if hasattr(cv2, 'CAP_MSMF'):
        backend_candidates.append((cv2.CAP_MSMF, "MSMF"))
    if hasattr(cv2, 'CAP_ANY'):
        backend_candidates.append((cv2.CAP_ANY, "ANY"))
    if not backend_candidates:
        backend_candidates.append((None, "DEFAULT"))

    for backend, b_name in backend_candidates:
        cap = None
        try:
            cap = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
        except Exception:
            cap = None

        if cap is None or not cap.isOpened():
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            continue

        # Uncap high FPS for USB webcams by setting MJPG fourcc and 30/60 FPS
        try:
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            cap.set(cv2.CAP_PROP_FOURCC, fourcc)
            cap.set(cv2.CAP_PROP_FPS, 30.0)
        except Exception:
            pass

        # Пытаемся задать разрешение, если указано
        if width and height:
            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            except Exception:
                pass

        # Даем DirectShow/MSMF время на инициализацию потока
        frame = None
        for _ in range(max_attempts):
            try:
                ret, f = cap.read()
                if ret and f is not None and f.size > 0:
                    frame = f
                    break
            except Exception:
                pass
            time.sleep(0.035)

        if frame is not None:
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            return cap, frame, b_name

        # Если с принудительным разрешением кадры не пошли, пробуем без смены разрешения
        if width and height:
            try:
                cap.release()
            except Exception:
                pass
            time.sleep(0.04)
            try:
                cap = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
                if cap is not None and cap.isOpened():
                    for _ in range(max_attempts):
                        try:
                            ret, f = cap.read()
                            if ret and f is not None and f.size > 0:
                                frame = f
                                break
                        except Exception:
                            pass
                        time.sleep(0.035)
                    if frame is not None:
                        try:
                            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        except Exception:
                            pass
                        return cap, frame, b_name
            except Exception:
                pass

        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
            time.sleep(0.04)

    # Крайний fallback: VideoCapture(index)
    try:
        cap = cv2.VideoCapture(index)
        if cap is not None and cap.isOpened():
            for _ in range(max_attempts):
                try:
                    ret, f = cap.read()
                    if ret and f is not None and f.size > 0:
                        return cap, f, "AUTO"
                except Exception:
                    pass
                time.sleep(0.035)
            return cap, None, "AUTO"
    except Exception:
        pass

    return None, None, "FAILED"



MIN_CAMERA_WIDTH = 640
MIN_CAMERA_HEIGHT = 480


def filter_supported_resolutions(modes, min_width=MIN_CAMERA_WIDTH, min_height=MIN_CAMERA_HEIGHT):
    """Normalise camera modes: unique ``(width, height)`` pairs, sorted ascending.

    Modes below the supported minimum (640x480) are dropped.  The result is
    sorted by pixel count (then width) so the first item is the smallest
    usable mode and the last item is the maximum the device reported.
    """
    cleaned = set()
    for mode in modes or []:
        try:
            width, height = int(mode[0]), int(mode[1])
        except (TypeError, ValueError, IndexError):
            continue
        if width >= int(min_width) and height >= int(min_height):
            cleaned.add((width, height))
    return sorted(cleaned, key=lambda item: (item[0] * item[1], item[0], item[1]))


def recommended_resolution(modes):
    """Return the recommended (balanced) mode for *modes* or ``(None, None)``.

    The recommended mode is the largest mode that still fits the balanced
    1280x720 budget (good detail without choking USB bandwidth / preview
    rendering).  If every mode is larger than that, the smallest available
    mode is the safest recommendation; if every mode is smaller, the largest
    available mode is recommended.
    """
    ordered = filter_supported_resolutions(modes)
    if not ordered:
        return None, None
    balanced = [mode for mode in ordered if mode[0] <= 1280 and mode[1] <= 720]
    if balanced:
        return balanced[-1]
    if ordered[0][0] > 1280 or ordered[0][1] > 720:
        return ordered[0]
    return ordered[-1]


def choose_resolution(modes, choice="auto"):
    """Resolve a saved resolution choice against the modes a device offers.

    ``"auto"`` (and any choice the device no longer offers) resolves to the
    recommended mode, so the recommended mode is always the fallback.
    """
    ordered = filter_supported_resolutions(modes)
    if str(choice or "auto").strip().lower() != "auto":
        try:
            width, height = [int(part) for part in str(choice).lower().replace("×", "x").split("x")]
            if (width, height) in ordered:
                return width, height
        except (TypeError, ValueError):
            pass
    return recommended_resolution(ordered)


MAX_PREVIEW_UPSCALE = 3.0


def preview_view_geometry(label_width, label_height, frame_width, frame_height,
                          max_upscale=MAX_PREVIEW_UPSCALE):
    """Geometry that maps camera pixels onto the preview label.

    The preview keeps the frame aspect ratio and is drawn centred inside the
    label, so mouse coordinates must be shifted by the letterbox offset before
    being divided by the scale.  Both values are returned here so the render
    loop and the ROI mouse handlers always agree.

    Returns a dict with ``scale``, ``offset_x``, ``offset_y``, ``disp_w``,
    ``disp_h``, ``frame_w`` and ``frame_h``.
    """
    try:
        label_width = float(label_width)
        label_height = float(label_height)
        frame_width = float(frame_width)
        frame_height = float(frame_height)
    except (TypeError, ValueError):
        return None
    if label_width <= 1 or label_height <= 1 or frame_width <= 0 or frame_height <= 0:
        return None

    scale = min(label_width / frame_width, label_height / frame_height)
    if not np.isfinite(scale) or scale <= 0:
        return None
    # Small sensors are allowed to fill the card, but only up to a sane limit
    # (a 320x240 stream must not be blown up 6x).
    scale = min(scale, float(max_upscale))
    disp_w = max(1, int(round(frame_width * scale)))
    disp_h = max(1, int(round(frame_height * scale)))
    return {
        'scale': scale,
        'offset_x': max(0.0, (label_width - disp_w) / 2.0),
        'offset_y': max(0.0, (label_height - disp_h) / 2.0),
        'disp_w': disp_w,
        'disp_h': disp_h,
        'frame_w': int(round(frame_width)),
        'frame_h': int(round(frame_height)),
    }


def preview_point_to_frame(view, x, y, clamp=False):
    """Convert label pixels to camera pixels using :func:`preview_view_geometry`.

    Returns ``(x, y)`` in frame coordinates, or ``None`` when the point falls
    on the empty margin next to the letterboxed image (unless *clamp* is set,
    which is what dragging uses when the pointer leaves the image).
    """
    if not view:
        return None
    scale = float(view.get('scale') or 0.0)
    frame_w = float(view.get('frame_w') or 0.0)
    frame_h = float(view.get('frame_h') or 0.0)
    if scale <= 0.0 or frame_w <= 0.0 or frame_h <= 0.0:
        return None
    fx = (float(x) - float(view.get('offset_x', 0.0))) / scale
    fy = (float(y) - float(view.get('offset_y', 0.0))) / scale
    if clamp:
        fx = min(max(fx, 0.0), frame_w)
        fy = min(max(fy, 0.0), frame_h)
    elif fx < 0.0 or fy < 0.0 or fx > frame_w or fy > frame_h:
        return None
    return int(round(fx)), int(round(fy))


def preview_handle_tolerance(scale, min_tolerance=12, target_px=9, roi_size=None):
    """Resize-handle tolerance in frame pixels for a comfortable screen hit area.

    On a 3072x2048 sensor shown at ~0.11x a fixed 12 px tolerance is barely one
    screen pixel, so the tolerance grows as the preview shrinks.  It is capped
    (optionally by *roi_size*) so the interior of a small ROI stays draggable.
    """
    try:
        min_tolerance = int(min_tolerance)
        target_px = float(target_px)
        scale = float(scale)
    except (TypeError, ValueError):
        return 12
    if scale <= 0.0 or not np.isfinite(scale):
        return min_tolerance
    # Round up: the tolerance must always cover *target_px* screen pixels.
    tolerance = max(min_tolerance, int(np.ceil(target_px / scale)))
    if roi_size:
        try:
            tolerance = min(tolerance, max(min_tolerance, int(float(roi_size) * 0.25)))
        except (TypeError, ValueError):
            pass
    return tolerance


def probe_supported_camera_resolutions(index, max_attempts=3):
    """Probe common camera modes through real frame capture.

    OpenCV cannot enumerate every UVC mode on all Windows backends. This
    returns only candidate sizes that produced a frame at the requested size.
    The camera is opened and released for each candidate.
    """
    candidates = [
        (640, 480), (800, 600), (1024, 768), (1280, 720), (1280, 960),
        (1280, 1024), (1600, 1200), (1920, 1080), (1920, 1440),
        (2560, 1440), (2592, 1944), (3840, 2160),
    ]
    supported = []
    for width, height in candidates:
        cap = None
        try:
            cap, frame, _backend = open_camera_device(
                index, width=width, height=height, max_attempts=min(2, max(1, max_attempts))
            )
            if cap is not None and frame is not None:
                actual_h, actual_w = frame.shape[:2]
                if (actual_w, actual_h) == (width, height):
                    supported.append((width, height))
        except Exception:
            pass
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
    return filter_supported_resolutions(supported)


def create_video_capture(source, width=None, height=None):
    try:
        from ..analysis import ffmpeg_capture
    except ImportError:
        from src.analysis import ffmpeg_capture
    source_str = str(source).strip().strip('"').strip("'")

    if is_miicam_source(source_str):
        try:
            from .miicam_wrapper import MiiCamCapture
            return MiiCamCapture(source_str, width=width, height=height)
        except Exception as e:
            print(f"⚠️ Ошибка создания MiiCamCapture: {e}")
            return None
    elif is_video_file_source(source_str) or is_video_file_path(source_str):
        return open_video_file_capture(source_str)
    elif is_rtsp_source(source_str):
        return ffmpeg_capture.FFMpegLatestFrameCapture(source_str, width=width, height=height)
    elif is_network_source(source_str):
        apply_low_latency_ffmpeg_options()
        return cv2.VideoCapture(source_str, cv2.CAP_FFMPEG)
    else:
        try:
            index = int(source_str)
            cap, _frame, _backend = open_camera_device(index, width, height, max_attempts=15)
            return cap
        except (ValueError, TypeError):
            return cv2.VideoCapture(source_str)


def warmup_capture(cap, frames=8):
    if cap is None:
        return
    for _ in range(frames):
        try:
            cap.grab()
        except Exception:
            break


def read_valid_frame(cap, attempts=30):
    if cap is None:
        return False, None
    for _ in range(attempts):
        try:
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                return True, frame
        except Exception:
            pass
        time.sleep(0.02)
    return False, None

def _run_hidden(cmd):
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=20, creationflags=flags)

def get_windows_camera_names():
    names = []
    seen = set()

    # FFmpeg DirectShow names are much closer to the actual capture-device
    # order than a generic PnP enumeration. Filter out alternative names and audio devices.
    try:
        ffmpeg = find_ffmpeg_exe()
        if ffmpeg:
            result = _run_hidden(
                [ffmpeg, "-hide_banner", "-f", "dshow", "-list_devices", "true", "-i", "dummy"]
            )
            text = (result.stderr or "") + "\n" + (result.stdout or "")
            in_video_section = True
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if "DirectShow audio devices" in line:
                    in_video_section = False
                    continue
                if "DirectShow video devices" in line:
                    in_video_section = True
                    continue
                if not in_video_section:
                    continue
                if "Alternative name" in line or "@device" in line:
                    continue
                m = re.search(r'"([^"]+)"', line)
                if not m:
                    continue
                name = m.group(1).strip()
                if not name or name.lower() in ("dummy", "default"):
                    continue
                if name.startswith("@device_"):
                    continue
                if name not in seen:
                    seen.add(name)
                    names.append(name)
    except Exception:
        pass

    if names:
        return names

    # Fallback: PnP names.
    try:
        ps = (
            "Get-PnpDevice -Status OK | Where-Object { "
            "$_.Class -in @('Camera','Image') -or "
            "$_.FriendlyName -match 'cam|webcam|ivcam|iriun|video' "
            "} | ForEach-Object { $_.FriendlyName } | Where-Object { $_ }"
        )
        result = _run_hidden(["powershell", "-NoProfile", "-Command", ps])
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and line not in seen and not line.startswith("@device_"):
                seen.add(line)
                names.append(line)
    except Exception:
        pass
    return names


def is_ivcam_name(name):
    n = name.lower()
    return 'ivcam' in n or 'e2esoft' in n

def is_iriun_name(name):
    return 'iriun' in name.lower()

def camera_priority(name):
    has_stream = "нет видеопотока" not in name
    if is_ivcam_name(name) and has_stream:
        return 0
    if is_ivcam_name(name):
        return 1
    if has_stream and not is_iriun_name(name):
        return 2
    if has_stream:
        return 3
    if is_iriun_name(name):
        return 5
    return 4

def is_placeholder_frame(frame):
    if frame is None or frame.size == 0:
        return True
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if gray.mean() > 25:
        return False
    # Completely black dummy buffer (0 or near 0 max pixel)
    if float(frame.max()) < 2.0:
        return True
    _, bright = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(bright) > 500

def camera_label(index, width, height, backend, has_stream=True, win_names=None):
    win_name = None
    if win_names and index < len(win_names):
        win_name = win_names[index]
    if win_name:
        base = f"{win_name} ({width}x{height}, {backend})"
    else:
        base = f"Камера {index} ({width}x{height}, {backend})"
    if not has_stream:
        base += " — нет видеопотока"
    return base

def scan_cameras(max_index=6):
    available = []
    _cv_log_level = None
    try:
        if hasattr(cv2, "getLogLevel"):
            _cv_log_level = cv2.getLogLevel()
        if hasattr(cv2, "setLogLevel"):
            cv2.setLogLevel(2)  # suppress harmless FFmpeg/DirectShow WARN noise during enumeration
    except Exception:
        pass
    win_names = get_windows_camera_names()
    print("🔍 Сканирование камер...")
    if win_names:
        print("📷 Устройства Windows:", ", ".join(win_names))

    def _probe_index(i):
        try:
            cap, frame, backend = open_camera_device(i, width=None, height=None, max_attempts=4)
            if cap is not None and cap.isOpened():
                if frame is not None and frame.size > 0:
                    h, w = frame.shape[:2]
                    has_stream = not is_placeholder_frame(frame)
                    label = camera_label(i, w, h, backend, has_stream, win_names)
                    try:
                        cap.release()
                    except Exception:
                        pass
                    return (str(i), label, has_stream)
                else:
                    label = camera_label(i, 640, 480, backend, False, win_names)
                    try:
                        cap.release()
                    except Exception:
                        pass
                    return (str(i), label, False)
        except Exception as e:
            print(f"⚠️ Ошибка проверки камеры [{i}]: {e}")
        return None

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, max(1, max_index))) as executor:
        futures = {executor.submit(_probe_index, i): i for i in range(max_index)}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res is not None:
                src_str, lbl, has_stream = res
                available.append((src_str, lbl))
                if has_stream:
                    print(f"✅ [{src_str}] {lbl}")
                else:
                    print(f"⚠️ [{src_str}] {lbl}")

    available.sort(key=lambda item: (camera_priority(item[1]), int(item[0]) if item[0].isdigit() else 99))
    try:
        if _cv_log_level is not None and hasattr(cv2, "setLogLevel"):
            cv2.setLogLevel(_cv_log_level)
    except Exception:
        pass
    return available

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "192.168.1.1"

def scan_ip_cameras():
    found = []
    local_ip = get_local_ip()
    subnet = '.'.join(local_ip.split('.')[:3])
    ports = [8080, 80, 554, 4747, 7070]
    print(f"📱 Сканирование сети {subnet}.x...")
    
    def check_host(ip, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            result = sock.connect_ex((ip, port))
            sock.close()
            if result == 0:
                url = f"http://{ip}:{port}/video"
                test_cap = cv2.VideoCapture(url)
                if test_cap.isOpened():
                    ret, _ = test_cap.read()
                    test_cap.release()
                    if ret:
                        found.append((url, f"IP Camera: {ip}:{port}"))
                        print(f"✅ Найдена IP-камера: {ip}:{port}")
        except:
            pass
    
    threads = []
    for i in range(1, 50):
        ip = f"{subnet}.{i}"
        for port in ports:
            t = threading.Thread(target=check_host, args=(ip, port))
            t.start()
            threads.append(t)
    
    for t in threads:
        t.join()
    
    return found

def ivcam_setup_hint():
    return (
        "Запустите iVCam:\n"
        "1. На ПК — клиент e2eSoft iVCam (должен быть запущен)\n"
        "2. На телефоне — приложение iVCam\n"
        "3. Подключите телефон и ПК к одной Wi‑Fi сети (или USB)\n"
        "4. В списке камер выберите «e2eSoft iVCam»"
    )

                                                                   
_ROI_MASK_CACHE = {}

def compute_roi_means(frame, config):
    x = config['roi_x']
    y = config['roi_y']
    w = config['roi_w']
    h = config['roi_h']

    h_f, w_f = frame.shape[:2]
    safe_x = max(0, min(x, w_f - 1))
    safe_y = max(0, min(y, h_f - 1))
    safe_w = max(10, min(w, w_f - safe_x))
    safe_h = max(10, min(h, h_f - safe_y))

    roi = frame[safe_y:safe_y + safe_h, safe_x:safe_x + safe_w]

    if config.get('roi_shape', 'rect') == 'circle':
        mask_key = (int(safe_w), int(safe_h))
        mask = _ROI_MASK_CACHE.get(mask_key)
        if mask is None:
            mask = np.zeros((safe_h, safe_w), dtype=np.uint8)
            radius = min(safe_w, safe_h) // 2
            center = (safe_w // 2, safe_h // 2)
            cv2.circle(mask, center, radius, 255, -1)
            if len(_ROI_MASK_CACHE) >= 32:
                _ROI_MASK_CACHE.pop(next(iter(_ROI_MASK_CACHE)))
            _ROI_MASK_CACHE[mask_key] = mask
        mean_b, mean_g, mean_r, _ = cv2.mean(roi, mask=mask)
    else:
        mean_b, mean_g, mean_r, _ = cv2.mean(roi)

    # Optional software color calibration gains (White Balance normalization)
    wb_r_mult = float(config.get('wb_r_mult', 1.0))
    wb_g_mult = float(config.get('wb_g_mult', 1.0))
    wb_b_mult = float(config.get('wb_b_mult', 1.0))
    if wb_r_mult != 1.0 or wb_g_mult != 1.0 or wb_b_mult != 1.0:
        mean_r = max(0.0, min(255.0, mean_r * wb_r_mult))
        mean_g = max(0.0, min(255.0, mean_g * wb_g_mult))
        mean_b = max(0.0, min(255.0, mean_b * wb_b_mult))

    return mean_b, mean_g, mean_r, safe_x, safe_y, safe_w, safe_h, h_f, w_f

def detect_green_circle_roi(frame):
    """
    Автоматическое обнаружение нарисованного зеленого круга ROI на видеокадре.
    Возвращает кортеж (cx, cy, radius) пиксель в пиксель или None.
    """
    if frame is None or frame.size == 0:
        return None

    # 1. Поиск ярко-зеленых пикселей (в HSV и BGR)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask_hsv = cv2.inRange(hsv, np.array([30, 45, 45]), np.array([90, 255, 255]))

    b = frame[:, :, 0].astype(np.int32)
    g = frame[:, :, 1].astype(np.int32)
    r = frame[:, :, 2].astype(np.int32)
    mask_bgr = ((g > 75) & (g > r + 20) & (g > b + 20)).astype(np.uint8) * 255

    mask = cv2.bitwise_or(mask_hsv, mask_bgr)
    cnts, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None

    candidates = []
    for c in cnts:
        arc = cv2.arcLength(c, True)
        if arc < 25 or len(c) < 15:
            continue
        pts = c.reshape(-1, 2).astype(np.float64)
        x = pts[:, 0]
        y = pts[:, 1]
        A = np.column_stack([x, y, np.ones_like(x)])
        f = x**2 + y**2
        try:
            sol, _, _, _ = np.linalg.lstsq(A, f, rcond=None)
            cx = sol[0] / 2.0
            cy = sol[1] / 2.0
            r_sq = sol[2] + cx**2 + cy**2
            if r_sq > 0:
                r_calc = np.sqrt(r_sq)
                if 8 <= r_calc <= max(frame.shape[:2]):
                    residuals = np.abs(np.hypot(x - cx, y - cy) - r_calc)
                    mean_err = np.mean(residuals)
                    if mean_err < max(5.0, 0.22 * r_calc):
                        score = mean_err / r_calc
                        candidates.append((score, len(c), int(round(cx)), int(round(cy)), int(round(r_calc))))
        except Exception:
            pass

    if candidates:
        candidates.sort(key=lambda item: (item[0], -item[1]))
        best = candidates[0]
        return best[2], best[3], best[4]
    return None


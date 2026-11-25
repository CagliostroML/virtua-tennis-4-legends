#!/usr/bin/env python3
"""
Standalone 3DDFA_V2 ONNX 3DMM Fitter (Zero PyTorch Dependency).

Uses:
  - MediaPipe FaceLandmarker for fast accurate face bounding box
  - scratch/3DDFA_V2/weights/mb1_120x120.onnx via onnxruntime
  - scratch/3DDFA_V2/configs/bfm_noneck_v3.pkl + param_mean_std_62d_120x120.pkl

Exposes:
  fit_bfm3d(rgb_img) -> dict with:
    - alpha_shp     : (40,) float32 pure identity shape coefficients
    - alpha_exp     : (10,) float32 expression coefficients
    - R             : (3, 3) float32 rotation matrix
    - offset        : (3, 1) float32 translation vector
    - roi_box       : [sx, sy, ex, ey] crop box
    - verts_neutral : (38365, 3) float32 canonical neutral 3D mesh (alpha_exp = 0!)
    - verts_posed   : (38365, 3) float32 image-aligned 3D mesh
    - lm68          : (68, 3) float32 image-space 3D facial landmarks
    - tri           : (76073, 3) int32 BFM triangle indices
    - keypoints     : (68,) int64 BFM vertex indices for the 68 landmarks
"""
import os
import pickle
import sys
import time
import cv2
import numpy as np
import onnxruntime as ort
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TDDFA_DIR = os.path.join(REPO_ROOT, "scratch", "3DDFA_V2")
ONNX_PATH = os.path.join(TDDFA_DIR, "weights", "mb1_120x120.onnx")
BFM_PATH = os.path.join(TDDFA_DIR, "configs", "bfm_noneck_v3.pkl")
TRI_PATH = os.path.join(TDDFA_DIR, "configs", "tri.pkl")
MEAN_STD_PATH = os.path.join(TDDFA_DIR, "configs", "param_mean_std_62d_120x120.pkl")
MP_TASK_PATH = os.path.join(REPO_ROOT, "scratch", "real_alcaraz_3d", "face_landmarker.task")

_CACHE = {}


def _get_models():
    if "loaded" in _CACHE:
        return _CACHE
    sess_opts = ort.SessionOptions()
    sess_opts.inter_op_num_threads = 1
    sess_opts.intra_op_num_threads = 4
    sess = ort.InferenceSession(ONNX_PATH, sess_opts, providers=["CPUExecutionProvider"])

    with open(BFM_PATH, "rb") as f:
        bfm = pickle.load(f)
    with open(TRI_PATH, "rb") as f:
        tri = pickle.load(f).T.astype(np.int32).copy()
    with open(MEAN_STD_PATH, "rb") as f:
        ms = pickle.load(f)

    u = bfm["u"].astype(np.float32).reshape(-1, 1)         # (3*38365, 1)
    w_shp = bfm["w_shp"].astype(np.float32)[:, :40]        # (3*38365, 40)
    w_exp = bfm["w_exp"].astype(np.float32)[:, :10]        # (3*38365, 10)
    keypoints = bfm["keypoints"].astype(np.int64)          # (204,) -> 68*3

    detector = mp_vision.FaceLandmarker.create_from_options(
        mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MP_TASK_PATH),
            num_faces=1,
        )
    )

    _CACHE.update({
        "loaded": True,
        "sess": sess,
        "u": u,
        "w_shp": w_shp,
        "w_exp": w_exp,
        "tri": tri,
        "keypoints": keypoints,
        "param_mean": ms["mean"].astype(np.float32),
        "param_std": ms["std"].astype(np.float32),
        "detector": detector,
    })
    return _CACHE


def _parse_roi_box_from_landmarks(lms, w, h):
    xs = np.array([lm.x * w for lm in lms], dtype=np.float32)
    ys = np.array([lm.y * h for lm in lms], dtype=np.float32)
    left, right = float(xs.min()), float(xs.max())
    top, bottom = float(ys.min()), float(ys.max())
    old_size = (right - left + bottom - top) / 2.0
    center_x = right - (right - left) / 2.0
    center_y = bottom - (bottom - top) / 2.0 + old_size * 0.14
    size = int(old_size * 1.58)
    return [
        center_x - size / 2.0,
        center_y - size / 2.0,
        center_x + size / 2.0,
        center_y + size / 2.0,
    ]


def _crop_img(img, roi_box):
    h, w = img.shape[:2]
    sx, sy, ex, ey = [int(round(v)) for v in roi_box]
    dh, dw = ey - sy, ex - sx
    res = np.zeros((dh, dw, 3), dtype=img.dtype)
    dsx = max(0, -sx)
    dex = dw - max(0, ex - w)
    dsy = max(0, -sy)
    dey = dh - max(0, ey - h)
    ssx, sex = max(0, sx), min(w, ex)
    ssy, sey = max(0, sy), min(h, ey)
    if sex > ssx and sey > ssy:
        res[dsy:dey, dsx:dex] = img[ssy:sey, ssx:sex]
    return res


def _similar_transform(pts3d, roi_box, size=120):
    pts = pts3d.copy()
    pts[0, :] -= 1.0
    pts[2, :] -= 1.0
    pts[1, :] = size - pts[1, :]
    sx, sy, ex, ey = roi_box
    scale_x = (ex - sx) / size
    scale_y = (ey - sy) / size
    pts[0, :] = pts[0, :] * scale_x + sx
    pts[1, :] = pts[1, :] * scale_y + sy
    s = (scale_x + scale_y) / 2.0
    pts[2, :] *= s
    pts[2, :] -= np.min(pts[2, :])
    return pts.astype(np.float32)


def reconstruct_neutral_bfm(alpha_shp):
    """Return canonical neutral 38365x3 BFM vertices (alpha_exp = 0)."""
    m = _get_models()
    a = np.asarray(alpha_shp, dtype=np.float32).reshape(40, 1)
    v = (m["u"] + m["w_shp"] @ a).reshape(-1, 3)
    return v


def fit_bfm3d(rgb_img, bbox=None):
    """
    Fit 3DDFA_V2 3DMM to an RGB uint8 numpy image (H, W, 3).
    If bbox is None, uses MediaPipe FaceLandmarker to locate the face.
    """
    m = _get_models()
    arr = np.asarray(rgb_img)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError("Expected RGB image (H, W, 3)")
    if arr.shape[2] == 4:
        arr = arr[:, :, :3]
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    h, w = arr.shape[:2]

    if bbox is None:
        mp_im = mp.Image(image_format=mp.ImageFormat.SRGB, data=arr)
        res = m["detector"].detect(mp_im)
        if not res.face_landmarks:
            raise RuntimeError("No face detected by MediaPipe for BFM3D fit")
        roi_box = _parse_roi_box_from_landmarks(res.face_landmarks[0], w, h)
    else:
        left, top, right, bottom = bbox
        old_size = (right - left + bottom - top) / 2.0
        cx = right - (right - left) / 2.0
        cy = bottom - (bottom - top) / 2.0 + old_size * 0.14
        sz = int(old_size * 1.58)
        roi_box = [cx - sz / 2.0, cy - sz / 2.0, cx + sz / 2.0, cy + sz / 2.0]

    crop = _crop_img(arr, roi_box)
    # 3DDFA_V2 expects BGR input normalized by (x - 127.5) / 128.0
    bgr = cv2.resize(crop[:, :, ::-1], (120, 120), interpolation=cv2.INTER_LINEAR)
    inp = ((bgr.astype(np.float32).transpose(2, 0, 1)[np.newaxis, ...]) - 127.5) / 128.0

    raw_param = m["sess"].run(None, {"input": inp})[0].flatten().astype(np.float32)
    param = raw_param * m["param_std"] + m["param_mean"]

    R_ = param[:12].reshape(3, 4)
    R = R_[:, :3].copy()
    offset = R_[:, 3:4].copy()
    alpha_shp = param[12:52].reshape(40, 1).copy()
    alpha_exp = param[52:62].reshape(10, 1).copy()

    # Neutral canonical 3D mesh (alpha_exp = 0!)
    verts_neutral = (m["u"] + m["w_shp"] @ alpha_shp).reshape(-1, 3)

    # Full posed 3D mesh in image coordinates
    verts_3d_local = (m["u"] + m["w_shp"] @ alpha_shp + m["w_exp"] @ alpha_exp).reshape(-1, 3).T
    verts_cam = R @ verts_3d_local + offset
    verts_posed = _similar_transform(verts_cam, roi_box, 120).T

    kp_idx = m["keypoints"][0::3] // 3
    lm68 = verts_posed[kp_idx].copy()

    return {
        "alpha_shp": alpha_shp.flatten(),
        "alpha_exp": alpha_exp.flatten(),
        "R": R,
        "offset": offset,
        "roi_box": roi_box,
        "verts_neutral": verts_neutral,
        "verts_posed": verts_posed,
        "lm68": lm68,
        "tri": m["tri"],
        "kp_idx": kp_idx,
    }


if __name__ == "__main__":
    from PIL import Image
    test_img = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        REPO_ROOT, "scratch", "real_alcaraz_3d", "refs_neutral", "front_neutral.jpg"
    )
    im = np.array(Image.open(test_img).convert("RGB"))
    _ = fit_bfm3d(im)  # warm up
    t0 = time.perf_counter()
    out = fit_bfm3d(im)
    dt_ms = (time.perf_counter() - t0) * 1000.0
    nans = int(np.isnan(out["verts_neutral"]).sum() + np.isnan(out["verts_posed"]).sum())
    print(f"bfm3d_fit PASS: {test_img}")
    print(f"  inference_ms={dt_ms:.1f}ms | nans={nans}")
    print(f"  verts_neutral={out['verts_neutral'].shape} | lm68={out['lm68'].shape} | tri={out['tri'].shape}")
    print(f"  alpha_shp[:6]={np.round(out['alpha_shp'][:6], 3)}")
    print(f"  alpha_exp[:6]={np.round(out['alpha_exp'][:6], 3)}")

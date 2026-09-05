"""七牛云 Kodo 上传（国内托管，10GB 永久免费额度）"""

import os
from pathlib import Path
from typing import List

try:
    from qiniu import Auth, put_file
    QINIU_OK = True
except ImportError:
    QINIU_OK = False


def upload_site(site_dir: Path, prefix: str = "site") -> List[str]:
    """把 site/ 下所有文件上传到七牛云。环境变量：QINIU_AK / QINIU_SK / QINIU_BUCKET。"""
    ak = os.environ.get("QINIU_AK", "")
    sk = os.environ.get("QINIU_SK", "")
    bucket = os.environ.get("QINIU_BUCKET", "")
    if not (ak and sk and bucket):
        print("[七牛云] 缺少 QINIU_AK/QINIU_SK/QINIU_BUCKET，跳过上传")
        return []
    if not QINIU_OK:
        print("[七牛云] 未安装 qiniu 库，跳过上传（pip install qiniu）")
        return []

    auth = Auth(ak, sk)
    uploaded = []
    for path in sorted(site_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(site_dir)
            key = f"{prefix}/{rel.as_posix()}" if prefix else rel.as_posix()
            token = auth.upload_token(bucket, key, 3600)
            ret, info = put_file(token, key, str(path))
            if info.status_code in (200, 401):  # 401 表示文件内容未变（七牛返回 401=no change）
                uploaded.append(key)
            else:
                print(f"[七牛云] 上传失败 {key}: {info}")
    print(f"[七牛云] 上传完成 {len(uploaded)} 个文件 → {bucket}/{prefix}")
    return uploaded

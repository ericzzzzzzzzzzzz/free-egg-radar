"""腾讯云 COS 上传（备选托管，新用户 6 个月免费）"""

import os
from pathlib import Path
from typing import List

try:
    from qcloud_cos import CosConfig, CosS3Client
    COS_OK = True
except ImportError:
    COS_OK = False


def upload_site(site_dir: Path, prefix: str = "site") -> List[str]:
    """把 site/ 下所有文件上传到 COS。环境变量：COS_SECRET_ID / COS_SECRET_KEY / COS_BUCKET / COS_REGION。"""
    sid = os.environ.get("COS_SECRET_ID", "")
    skey = os.environ.get("COS_SECRET_KEY", "")
    bucket = os.environ.get("COS_BUCKET", "")
    region = os.environ.get("COS_REGION", "ap-guangzhou")
    if not (sid and skey and bucket):
        print("[腾讯云COS] 缺少 COS_SECRET_ID/COS_SECRET_KEY/COS_BUCKET，跳过上传")
        return []
    if not COS_OK:
        print("[腾讯云COS] 未安装 cos-python-sdk-v5，跳过上传")
        return []

    config = CosConfig(Region=region, SecretId=sid, SecretKey=skey)
    client = CosS3Client(config)
    uploaded = []
    for path in sorted(site_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(site_dir)
            key = f"{prefix}/{rel.as_posix()}" if prefix else rel.as_posix()
            try:
                client.upload_file(Bucket=bucket, Key=key, LocalFilePath=str(path), EnableMD5=False, progress_callback=None)
                uploaded.append(key)
            except Exception as e:
                print(f"[腾讯云COS] 上传失败 {key}: {e}")
    print(f"[腾讯云COS] 上传完成 {len(uploaded)} 个文件 → {bucket}/{prefix}")
    return uploaded

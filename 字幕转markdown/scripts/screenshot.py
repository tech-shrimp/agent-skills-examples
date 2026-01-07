import argparse
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

def write_note(filename: str, markdown: str) -> Path:
    path = Path(f"output/{filename}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    logging.info("Saved note backup: %s", path)
    return path


# ---------- 截图 ----------

def extract_screenshot_markers(markdown: str) -> List[Tuple[str, int]]:
    """
    找到 Screenshot-00:03:12 或 Screenshot-[00:03:12] 形式的标记。
    """
    pattern = r"(?:\*?)Screenshot-(?:\[(\d{2}):(\d{2}):(\d{2})\]|(\d{2}):(\d{2}):(\d{2}))"
    results: List[Tuple[str, int]] = []
    for match in re.finditer(pattern, markdown):
        hh = match.group(1) or match.group(4)
        mm = match.group(2) or match.group(5)
        ss = match.group(3) or match.group(6)
        total_seconds = int(mm) * 60 + int(ss)
        results.append((match.group(0), total_seconds))
    return results


def generate_screenshot(video_path: Path, output_dir: Path, timestamp: int) -> Path:
    """
    调用 ffmpeg 截图，返回图片路径。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    mm = timestamp // 60
    ss = timestamp % 60
    filename = f"screenshot_{mm:02d}_{ss:02d}.jpg"
    output_path = output_dir / filename

    cmd = [
        "ffmpeg",
        "-ss",
        str(timestamp),
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
        "-y",
    ]
    logging.info("生成截图：time=%s, file=%s", timestamp, output_path)
    subprocess.run(cmd, check=False, capture_output=True)
    return output_path


def replace_screenshots(
    markdown: str,
    video_path: Optional[Path],
    output_dir: Path,
    image_base_url: str,
) -> str:
    """
    将 Screenshot 标记替换为实际图片链接；没有视频时保持原样。
    返回修改后的 markdown。
    """
    if not video_path:
        logging.info("未提供视频文件，保留 Screenshot 标记不变。")
        return markdown

    matches = extract_screenshot_markers(markdown)
    
    for idx, (marker, ts) in enumerate(matches):
        try:
            img_path = generate_screenshot(video_path, output_dir, ts)
            url = f"{image_base_url.rstrip('/')}/{img_path.name}"
            markdown = markdown.replace(marker, f"![]({url})", 1)
        except Exception as exc:  # pylint: disable=broad-except
            logging.warning("生成截图失败（%s）：%s", marker, exc)
    return markdown

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    parser = argparse.ArgumentParser(description="将 SRT/视频转换为 Markdown 笔记")
    args = parser.parse_args()

    logging.info("环境变量加载完成。")

    #从当前工作目录自动查找对应的 SRT 和 MP4 文件
    cwd = Path.cwd()
    md_path: Path
    video_path: Path
    # 附件文件夹
    image_base_url = "assets"
    screenshots_path = Path(f"output/{image_base_url}")

    md_candidates = sorted(cwd.glob("*.md"))
    if not md_candidates:
        raise RuntimeError("当前目录没有找到任何 .md 文件，请把字幕文件夹导出并且放到根目录下。")
    if len(md_candidates) > 1:
        logging.warning("当前目录中发现多个 .srt，将使用第一个：%s", md_candidates[0])
    md_path = md_candidates[0]

    mp4_candidates = sorted(cwd.glob("*.mp4"))
    if mp4_candidates:
        preferred: Optional[Path] = None
        video_path = preferred or mp4_candidates[0]
        if len(mp4_candidates) > 1 and preferred is None:
            logging.warning("当前目录中发现多个 .mp4，将使用第一个：%s", video_path)
    else:
        logging.info("当前目录未发现 .mp4，将保留 Markdown 中的 Screenshot 标记不变。")
        video_path = None

    # 读取 markdown 文件内容
    markdown = md_path.read_text(encoding="utf-8")
    logging.info("读取 Markdown 文件：%s", md_path)

    processed_md = replace_screenshots(markdown, video_path=video_path, output_dir=screenshots_path, image_base_url=image_base_url)

    logging.info("截图处理完成")
    
    # 备份替换后的 Markdown 内容
    output = write_note("note_processed", processed_md)

    info = {
        "output": str(output),
        "screenshots_dir": str(screenshots_path),
        "video_used_for_screenshot": str(video_path)
    }
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
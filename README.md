# Photo Slideshow · 照片幻灯片生成器

把一批照片自动排版成拼图、幻灯片和视频：2×3 / 3×2 横竖版拼图、`.pptx` 相册、以及配好转场的 `.mp4`。

## 脚本

| 脚本 | 作用 |
| --- | --- |
| `make_2x3.py` | 2×3 拼图 |
| `make_3x2.py` / `make_3x2_landscape.py` | 3×2 拼图（竖版 / 横版） |
| `make_slides.py` | 生成 pptx 幻灯片 |
| `make_video.py` | 用 ffmpeg 合成 mp4 |
| `print_layout_compare.py` | 打印排版对比图 |

## 使用

```bash
python make_slides.py
python make_video.py
```

需要 Python 3.10+、Pillow、python-pptx、ffmpeg。仓库不包含任何示例照片。

## License

MIT

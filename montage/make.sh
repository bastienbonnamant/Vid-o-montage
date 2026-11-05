#!/bin/bash
# Usage: make.sh <scratch_dir>   (contient src/*.mp4 et vo/*.wav)
S=${1:?}; D=$(dirname "$0")
python3 "$D/audio.py" "$S" && python3 "$D/video.py" "$S" "$S/video.mp4" 2>/dev/null
ffmpeg -v error -y -i "$S/video.mp4" -i "$S/mix.wav" -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$D/../reel_arrache.mp4"
